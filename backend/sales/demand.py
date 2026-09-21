"""How full a night is, and how fast it is filling, for the line above the reserve button.

Urgency only works when it is true. Everything here is counted from completed orders, and the claim shown to a
visitor is chosen to match the numbers rather than the numbers being chosen to suit a claim:

  - the window for "N reserved recently" is the TIGHTEST of an hour, six hours or a day that genuinely holds
    enough bookings to be worth saying. If two people booked in the last hour it says the last hour; if they
    booked yesterday it says the last day. It never says "the last hour" about something that took a day.
  - nothing is shown at all below a floor, because "1 reserved in the last day" is an advert for an empty room.
  - the progress bar appears only once a third of the seats have gone. A bar showing 2 of 60 tells somebody the
    room will be empty, which is the opposite of the thing we are trying to say, and it would be true.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from catalog.models import TicketType
from sales.models import Order, OrderItem

# Tightest first. Each is (hours, the key the widget translates).
WINDOWS = ((1, 'in the last hour'), (6, 'in the last few hours'), (24, 'in the last day'))
# Below this a count is not social proof, it is an admission.
MIN_RECENT = 2
# A bar this empty discourages; above it, it persuades.
BAR_FROM = 0.33


def _seats(rows):
    """Seats only. A round of drinks is not a seat and must never inflate how full the room looks."""
    total = rows.exclude(ticket_type__is_addon=True).aggregate(n=Sum('quantity'))['n']
    return total or 0


def demand(event):
    """{'capacity', 'taken', 'left', 'recent', 'recentWindow'} or None when the night tracks no capacity."""
    if event is None:
        return None
    capacity = sum(t.capacity for t in event.ticket_types.filter(active=True, is_addon=False)
                   if t.capacity is not None)
    if not capacity:
        return None

    completed = OrderItem.objects.filter(order__event=event, order__status=Order.COMPLETED)
    taken = _seats(completed)

    recent, window = 0, ''
    now = timezone.now()
    for hours, label in WINDOWS:
        count = _seats(completed.filter(order__completed_at__gte=now - timedelta(hours=hours)))
        if count >= MIN_RECENT:
            recent, window = count, label
            break

    return {
        'capacity': capacity,
        'taken': taken,
        'left': max(0, capacity - taken),
        # Only once the room is visibly filling; before that the honest picture is a discouraging one.
        'showBar': taken / capacity >= BAR_FROM,
        'recent': recent,
        'recentWindow': window,
    }


def demand_for(events):
    """The same thing for a whole listing page, in two queries rather than two per row.

    The events index shows a dozen nights. Calling demand() per row would be a dozen round trips to say the
    same thing, which is how a listing page quietly becomes the slowest page on the site.
    """
    events = [e for e in events if e is not None]
    if not events:
        return {}

    capacities = {}
    for t in TicketType.objects.filter(event__in=events, active=True, is_addon=False):
        if t.capacity is not None:
            capacities[t.event_id] = capacities.get(t.event_id, 0) + t.capacity

    now = timezone.now()
    taken, recent = {}, {h: {} for h, _ in WINDOWS}
    rows = (OrderItem.objects
            .filter(order__event__in=events, order__status=Order.COMPLETED)
            .exclude(ticket_type__is_addon=True)
            .values_list('order__event_id', 'quantity', 'order__completed_at'))
    for event_id, quantity, completed in rows:
        taken[event_id] = taken.get(event_id, 0) + quantity
        for hours, _ in WINDOWS:
            if completed and completed >= now - timedelta(hours=hours):
                recent[hours][event_id] = recent[hours].get(event_id, 0) + quantity

    out = {}
    for event in events:
        capacity = capacities.get(event.id, 0)
        if not capacity:
            continue
        got = taken.get(event.id, 0)
        count, window = 0, ''
        for hours, label in WINDOWS:
            if recent[hours].get(event.id, 0) >= MIN_RECENT:
                count, window = recent[hours][event.id], label
                break
        out[event.id] = {
            'capacity': capacity, 'taken': got, 'left': max(0, capacity - got),
            'showBar': got / capacity >= BAR_FROM, 'recent': count, 'recentWindow': window,
        }
    return out
