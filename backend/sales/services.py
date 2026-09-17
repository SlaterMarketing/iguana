from dataclasses import dataclass, field

import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from api.serializers import remaining
from catalog.models import TicketType
from crm.models import Contact
from sales.models import Membership, Order, OrderItem, Ticket


class CheckoutError(Exception):
    pass


def format_money(cents, currency):
    """5000, 'mxn' -> '50 MXN'; 550, 'usd' -> '5.50 USD'."""
    amount = f'{cents / 100:,.2f}'
    if amount.endswith('.00'):
        amount = amount[:-3]
    return f'{amount} {currency.upper()}'


def stripe_enabled():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLISHABLE_KEY)


def stripe_client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def current_membership(contact):
    if contact is None:
        return None
    for m in contact.memberships.select_related('plan').filter(status=Membership.ACTIVE):
        if m.is_current:
            return m
    return None


def upsert_contact(email, source, first_name='', last_name='', phone=''):
    email = email.strip().lower()
    contact, created = Contact.objects.get_or_create(
        email=email, defaults={'source': source, 'first_name': first_name, 'last_name': last_name, 'phone': phone}
    )
    if not created:
        changed = False
        for attr, value in (('first_name', first_name), ('last_name', last_name), ('phone', phone)):
            if value and not getattr(contact, attr):
                setattr(contact, attr, value)
                changed = True
        if changed:
            contact.save()
    return contact


def member_unit_price(ticket_type, membership):
    if membership and ticket_type.member_price_cents is not None:
        return ticket_type.member_price_cents
    return ticket_type.price_cents


@dataclass
class PricedCart:
    lines: list = field(default_factory=list)  # (ticket_type, quantity, unit_price_cents)
    subtotal_cents: int = 0
    discount_cents: int = 0
    free_tickets: int = 0

    @property
    def total_cents(self):
        return max(0, self.subtotal_cents - self.discount_cents)


def price_cart(event, requested, contact):
    """requested: {ticket_type_id: quantity}. Server-side source of truth for every checkout total."""
    membership = current_membership(contact)
    cart = PricedCart()
    types = {t.id: t for t in event.ticket_types.filter(active=True)}
    for type_id, qty in requested.items():
        ticket_type = types.get(type_id)
        if ticket_type is None:
            raise CheckoutError('That ticket type is no longer available.')
        if not isinstance(qty, int) or qty < 0 or qty > 20:
            raise CheckoutError('Choose between 0 and 20 tickets.')
        if qty == 0:
            continue
        limit = ticket_type.max_per_order or 20
        if qty > limit:
            raise CheckoutError(f'You can book up to {limit} {ticket_type.name} per order.')
        if ticket_type.member_access == 'MEMBERS_ONLY' and not membership:
            raise CheckoutError(f'{ticket_type.name} is for members only.')
        if ticket_type.member_access == 'NON_MEMBERS' and membership:
            raise CheckoutError(f'{ticket_type.name} is not available to members.')
        left = remaining(ticket_type)
        if left is not None and qty > left:
            raise CheckoutError(f'Only {left} {ticket_type.name} tickets left.' if left else f'{ticket_type.name} is sold out.')
        cart.lines.append((ticket_type, qty, member_unit_price(ticket_type, membership)))
    if not cart.lines:
        raise CheckoutError('Choose at least one ticket.')
    cart.subtotal_cents = sum(qty * unit for _, qty, unit in cart.lines)

    if membership and event.members_eligible:
        plan = membership.plan
        # Free tickets go to the priciest seats first, then the guest discount applies to the rest.
        units = sorted((unit for _, qty, unit in cart.lines for _ in range(qty)), reverse=True)
        free = units[: plan.free_tickets_per_order]
        rest = units[plan.free_tickets_per_order:]
        cart.free_tickets = len(free)
        cart.discount_cents = sum(free) + round(sum(rest) * plan.guest_discount_percent / 100)
    return cart


@transaction.atomic
def create_order(event, cart, *, name, email, phone, contact, attribution=None):
    first, _, last = name.strip().partition(' ')
    contact = contact or upsert_contact(email, 'ORDER', first, last, phone)
    order = Order.objects.create(
        event=event,
        event_name=event.name,
        contact=contact,
        customer_name=name.strip(),
        customer_email=email.strip().lower(),
        customer_phone=phone.strip(),
        currency=event.currency,
        total_amount_cents=cart.total_cents,
        discount_amount_cents=cart.discount_cents,
        attribution=attribution or {},
    )
    for ticket_type, qty, unit in cart.lines:
        OrderItem.objects.create(order=order, ticket_type=ticket_type, name=ticket_type.name, quantity=qty, unit_price_cents=unit)
    return order


@transaction.atomic
def reserve_at_door(event, cart, *, name, email, phone, contact, attribution=None):
    """Book pay-at-the-door seats. The order completes now, nothing is charged, and the door collects the total."""
    if not all(ticket_type.pay_at_door for ticket_type, _, _ in cart.lines):
        raise CheckoutError('Reserve pay-at-the-door seats in their own order.')
    # price_cart already checked capacity, but without a lock two people booking at once could both take the last
    # seat. Re-check under a row lock on the ticket types.
    locked = {t.id: t for t in TicketType.objects.select_for_update().filter(pk__in=[t.id for t, _, _ in cart.lines])}
    for ticket_type, qty, _ in cart.lines:
        left = remaining(locked[ticket_type.id])
        if left is not None and qty > left:
            raise CheckoutError(f'Only {left} {ticket_type.name} left.' if left else f'{ticket_type.name} is fully booked.')
    email = email.strip().lower()
    # Nothing is paid up front, so one reservation per email per night stops one person holding every seat.
    if Order.objects.filter(event=event, customer_email=email, status=Order.COMPLETED,
                            items__ticket_type__pay_at_door=True).exists():
        raise CheckoutError('You already have a reservation for this night. Check your email for your seats.')
    order = create_order(event, cart, name=name, email=email, phone=phone, contact=contact, attribution=attribution)
    order.pay_at_door_cents = cart.total_cents
    order.save(update_fields=['pay_at_door_cents'])
    order, _ = complete_order(order)
    return order


@transaction.atomic
def complete_order(order, charge_id=''):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.COMPLETED:
        return order, False
    order.status = Order.COMPLETED
    order.completed_at = timezone.now()
    if charge_id:
        order.stripe_charge_id = charge_id
    order.save()
    for item in order.items.all():
        for _ in range(item.quantity):
            Ticket.objects.create(order=order, ticket_type_name=item.name)
    transaction.on_commit(lambda: send_order_confirmation(order))
    return order, True


def send_order_confirmation(order):
    link = f'{settings.BACKEND_URL}/orders/{order.public_view_token}/'
    event = order.event
    when = event.date.astimezone(timezone.get_current_timezone()).strftime('%A %d %B %Y') if event else ''
    lines = [
        f'Hi {order.customer_name or "there"},',
        '',
        f'You are booked for {order.event_name}{" on " + when if when else ""}.',
    ]
    if event and event.show_time:
        lines.append(f'Doors {event.doors_open or ""} · Show {event.show_time}'.replace('Doors  · ', ''))
    if event and (event.venue or event.venue_label):
        lines.append(f'Venue: {event.venue.name if event.venue else event.venue_label}')
    items = list(order.items.select_related('ticket_type'))
    # What the ticket includes and any house rules (a free drink, arrive by doors) live on the ticket type.
    descriptions = sorted({i.ticket_type.description for i in items if i.ticket_type and i.ticket_type.description})
    if descriptions:
        lines += [''] + descriptions
    if order.pay_at_door_cents:
        seats = sum(i.quantity for i in items)
        lines += ['', f'Pay {format_money(order.pay_at_door_cents, order.currency)} at the door for your '
                      f'{seats} seat{"s" if seats != 1 else ""}. Nothing was charged online.']
        label, subject = 'Your seats', f'Your reservation: {order.event_name}'
    else:
        label, subject = 'Your tickets', f'Your tickets: {order.event_name}'
    lines += ['', f'{label} (show this at the door): {link}', '', 'See you there,', 'Iguana Comedy', 'iguanacomedy.com']
    send_mail(subject, '\n'.join(lines), settings.DEFAULT_FROM_EMAIL, [order.customer_email])
