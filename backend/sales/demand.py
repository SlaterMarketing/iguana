"""How full a night is, and how fast it is filling, for the line above the reserve button.

Urgency only works when it is true. Everything here is counted from completed orders, and the claim shown to a
visitor is chosen to match the numbers rather than the numbers being chosen to suit a claim:

  - "N reserved recently" is counted over an hour, six hours and a day, and the window shown is the one that
    holds the MOST bookings, ties going to the tighter one. All three are true statements about the same
    orders, so this picks the most informative of them rather than the most flattering: a window can never
    claim more than its own count, so "the last hour" can never describe something that took a day. Preferring
    the tightest instead used to throw bookings away, and across two nights it threw them away twice: four
    Tuesday seats and three Wednesday ones were being advertised as "5 in the last few hours" because
    Tuesday's own window had narrowed to the hour. The real number was 7.
  - nothing is shown at all below a floor, because "1 reserved in the last day" is an advert for an empty room.
  - the progress bar appears only once a third of the seats have gone. A bar showing 2 of 60 tells somebody the
    room will be empty, which is the opposite of the thing we are trying to say, and it would be true.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from catalog.models import TicketType
from sales.models import Order, OrderItem

# Tightest first, which is also the tie-break order. Each is (hours, the key the widget translates).
WINDOWS = ((1, 'in the last hour'), (6, 'in the last few hours'), (24, 'in the last day'))
# Below this a count is not social proof, it is an admission.
MIN_RECENT = 2
# A bar this empty discourages; above it, it persuades.
BAR_FROM = 0.33


def _sold_elsewhere(event):
    return sum(t.sold_elsewhere or 0 for t in event.ticket_types.filter(active=True, is_addon=False))


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
    # Seats sold through a guest promoter are seats in this room. Leaving them out told a visitor the night was
    # emptier than it is, which is the opposite of what this line exists to do.
    taken = _seats(completed) + _sold_elsewhere(event)

    now = timezone.now()
    by_window = {label: _seats(completed.filter(order__completed_at__gte=now - timedelta(hours=hours)))
                 for hours, label in WINDOWS}
    recent, window = _best_window(by_window)

    return {
        'capacity': capacity,
        'taken': taken,
        'left': max(0, capacity - taken),
        # Only once the room is visibly filling; before that the honest picture is a discouraging one.
        'showBar': taken / capacity >= BAR_FROM,
        'recent': recent,
        'recentWindow': window,
        # All three, so a page showing several nights can add them up over the SAME window. Summing each
        # night's own chosen window and labelling the total with the widest of them undercounts, which is how
        # 7 bookings were being advertised as 5.
        'recentByWindow': by_window,
    }


def _best_window(by_window):
    """The window carrying the most bookings, ties to the tighter one, or nothing if none clears the floor."""
    best, label = 0, ''
    for _, candidate in WINDOWS:
        count = by_window.get(candidate, 0)
        if count >= MIN_RECENT and count > best:
            best, label = count, candidate
    return best, label


def demand_for(events):
    """The same thing for a whole listing page, in two queries rather than two per row.

    The events index shows a dozen nights. Calling demand() per row would be a dozen round trips to say the
    same thing, which is how a listing page quietly becomes the slowest page on the site.
    """
    events = [e for e in events if e is not None]
    if not events:
        return {}

    capacities, elsewhere = {}, {}
    for t in TicketType.objects.filter(event__in=events, active=True, is_addon=False):
        if t.capacity is not None:
            capacities[t.event_id] = capacities.get(t.event_id, 0) + t.capacity
        elsewhere[t.event_id] = elsewhere.get(t.event_id, 0) + (t.sold_elsewhere or 0)

    now = timezone.now()
    taken, recent = {}, {label: {} for _, label in WINDOWS}
    rows = (OrderItem.objects
            .filter(order__event__in=events, order__status=Order.COMPLETED)
            .exclude(ticket_type__is_addon=True)
            .values_list('order__event_id', 'quantity', 'order__completed_at'))
    for event_id, quantity, completed in rows:
        taken[event_id] = taken.get(event_id, 0) + quantity
        for hours, label in WINDOWS:
            if completed and completed >= now - timedelta(hours=hours):
                recent[label][event_id] = recent[label].get(event_id, 0) + quantity

    out = {}
    for event in events:
        capacity = capacities.get(event.id, 0)
        if not capacity:
            continue
        got = taken.get(event.id, 0) + elsewhere.get(event.id, 0)
        by_window = {label: recent[label].get(event.id, 0) for _, label in WINDOWS}
        count, window = _best_window(by_window)
        out[event.id] = {
            'capacity': capacity, 'taken': got, 'left': max(0, capacity - got),
            'showBar': got / capacity >= BAR_FROM, 'recent': count, 'recentWindow': window,
            'recentByWindow': by_window,
        }
    return out
