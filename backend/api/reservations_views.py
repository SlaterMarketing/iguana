"""Who is coming, night by night.

The question this answers is the one asked before every show: how many have we got. `/revenue/` answers what
the week was worth and the admin answers what a single order was, but neither lays the room out night by night,
and the number that decides whether to push an ad today is "47 of 60 on Tuesday".

It doubles as the door list, because nobody is scanning the QR codes: 0 of 24 tickets on 2026-09-23 and 0 of 16
the night before. Until that changes, a list of names somebody can read off a phone is the only check-in there
is, so every night shows its guests with the seats they booked and whether they have been checked in.

Staff only, sharing the admin session like the bar board. Email addresses are held back from plain staff and
shown to whoever can already see orders, because the door needs a name and does not need a mailing list.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from catalog.models import Event
from sales.demand import demand_for
from sales.i18n import lang_from_request
from sales.models import Order
from sales.services import format_money

CANCUN = ZoneInfo('America/Cancun')
PAST_NIGHTS = 8
AHEAD_DAYS = 60


def _nights(events, can_see_email, lang):
    pressure = demand_for(events)
    nights = []
    for event in events:
        orders = [o for o in event.orders.all() if o.status == Order.COMPLETED]
        guests, seats, checked_in, online_cents, door_cents = [], 0, 0, 0, 0
        for order in sorted(orders, key=lambda o: o.created_at):
            tickets = list(order.tickets.all())
            here = sum(1 for t in tickets if t.checked_in_at)
            seats += len(tickets)
            checked_in += here
            online_cents += order.total_amount_cents - order.pay_at_door_cents
            door_cents += order.pay_at_door_cents
            guests.append({
                'name': order.customer_name or order.customer_email,
                'email': order.customer_email if can_see_email else '',
                'seats': len(tickets),
                'checked_in': here,
                'booked_at': order.created_at.astimezone(CANCUN),
                'token': order.public_view_token,
            })
        pressure_row = pressure.get(event.id) or {}
        capacity = pressure_row.get('capacity') or 0
        nights.append({
            'event': event,
            'name': event.label(lang),
            'when': event.date.astimezone(CANCUN) if event.date else None,
            'guests': guests,
            'bookings': len(guests),
            'seats': seats,
            'checked_in': checked_in,
            'capacity': capacity,
            'left': max(capacity - pressure_row.get('taken', seats), 0) if capacity else None,
            'percent': round(min(pressure_row.get('taken', seats) / capacity, 1) * 100) if capacity else 0,
            'elsewhere': max(pressure_row.get('taken', seats) - seats, 0),
            'online': format_money(online_cents, event.currency) if online_cents else '',
            'at_door': format_money(door_cents, event.currency) if door_cents else '',
        })
    return nights


@staff_member_required
def reservations(request):
    lang = lang_from_request(request)
    can_see_email = request.user.is_superuser or request.user.has_perm('sales.view_order')
    today = timezone.now().astimezone(CANCUN).date()
    window = (Event.objects.filter(date__date__gte=today - timedelta(days=PAST_NIGHTS),
                                   date__date__lte=today + timedelta(days=AHEAD_DAYS))
              .exclude(status=Event.DRAFT)
              .select_related('venue')
              .prefetch_related('orders__tickets', 'ticket_types')
              .order_by('date'))
    events = list(window)
    nights = _nights(events, can_see_email, lang)
    upcoming = [n for n in nights if n['when'] and n['when'].date() >= today]
    past = [n for n in reversed(nights) if n['when'] and n['when'].date() < today]
    return render(request, 'embed/reservations.html', {
        'lang': lang,
        'today': today,
        'upcoming': upcoming,
        'past': past,
        'seats_ahead': sum(n['seats'] for n in upcoming),
        'can_see_email': can_see_email,
    })
