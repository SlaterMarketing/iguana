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

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import Event
from sales.demand import demand_for
from sales.i18n import lang_from_request
from sales.models import Order

from sales.services import format_money

from .floor import floor_required

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
                'id': order.id,
                # What they bought, so a VIP is obvious on the list the door reads.
                'tier': ', '.join(sorted({t.ticket_type_name for t in tickets if t.ticket_type_name})),
                # A promoter's guest carries THEIR QR, which our scanner cannot read: this row is the only
                # way that person gets admitted, so it has to say so.
                'promoter': order.source or '',
                'all_here': here >= len(tickets) and bool(tickets),
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


@floor_required
@require_POST
def check_in_order(request, order_id):
    """Admit everybody on one booking from the guest list, without a scan.

    🚨 This is the only way in for two kinds of guest, and both are common here: anybody whose ticket a guest
    promoter sold carries THEIR QR, which our scanner can never read, and any door phone running iOS has no
    barcode reader at all. A list that could only be looked at, never ticked, left the door with a piece of
    paper and a pen.

    It admits the whole booking rather than a seat at a time, because a booking arrives together. `?undo=1`
    puts it back: it is one tap on a phone in a queue, and a guest wrongly marked as already inside is an
    argument at the door.
    """
    order = Order.objects.filter(pk=order_id, status=Order.COMPLETED).first()
    if order is not None:
        undo = request.GET.get('undo') or request.POST.get('undo')
        now = None if undo else timezone.now()
        order.tickets.filter(checked_in_at__isnull=bool(not undo)).update(checked_in_at=now)
    back = '/mesas/reservas/' if request.path.startswith('/mesas') else '/reservations/'
    return redirect(f'{back}#o{order_id}')


@floor_required
def reservations(request):
    """The guest list, which is also the door list because nobody scans the QR codes.

    Open to the floor accounts as well as the admin: the door is one of the two people who log in at `/mesas/`,
    and a door with no list is the one job on this page. Names only for them.

    🚨 Email addresses stay behind `can_see_the_money`, and that is the whole reason this page can be shared.
    The door needs to know whether somebody is on the list; it does not need the mailing list, and a phone
    behind a bar is the least private screen in the building.
    """
    lang = 'es' if request.path.startswith('/mesas') else lang_from_request(request)
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
        'floor': request.path.startswith('/mesas'),
        'today': today,
        'upcoming': upcoming,
        'past': past,
        'seats_ahead': sum(n['seats'] for n in upcoming),
        'can_see_email': can_see_email,
    })
