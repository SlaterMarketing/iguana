"""What the club is actually taking, and where it is being lost.

Two kinds of night sit side by side here and they are not the same business. An open mic seat is free, so its
"revenue" is the drinks ordered with it and at the table; a ticketed show is a straight sale. Adding them into
one number hides both, so they are counted separately and the page says which is which.

The funnel is the point. Meta reports a cost per reservation but not what happened after the click, and the
question worth answering at a glance is the one that column answers: of the people who reached the checkout,
how many finished, and how many of those bought a drink. Everything else is a vanity number.

Staff only, on the API domain, so it shares the admin session rather than inventing a login.
"""

from collections import OrderedDict
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from catalog.models import Event
from crm.models import TrackedEvent
from sales.models import Order, OrderItem, TableOrder

DEFAULT_DAYS = 30


def _money(cents, currency='mxn'):
    return f'{cents / 100:,.2f} {currency.upper()}'


def _daily(queryset, field, days, value=None):
    """A continuous day series, zeros filled, so a gap reads as a quiet day and not as missing data."""
    end = timezone.localtime().date()
    start = end - timedelta(days=days - 1)
    buckets = OrderedDict((start + timedelta(days=i), 0) for i in range((end - start).days + 1))
    rows = (queryset.annotate(day=TruncDate(field)).values('day')
            .annotate(n=Sum(value) if value else Count('id')).order_by('day'))
    for row in rows:
        if row['day'] in buckets:
            buckets[row['day']] = row['n'] or 0
    return buckets


@staff_member_required
def revenue(request):
    try:
        days = max(1, min(365, int(request.GET.get('days', DEFAULT_DAYS))))
    except (TypeError, ValueError):
        days = DEFAULT_DAYS
    since = timezone.now() - timedelta(days=days)

    completed = Order.objects.filter(status=Order.COMPLETED, completed_at__gte=since)
    started = Order.objects.filter(created_at__gte=since)

    # Online money only. A pay-at-the-door reservation is a real booking and worth optimising for, but it is
    # worth nothing yet, and counting it as revenue would flatter every number on this page.
    online_cents = sum(max(o.total_amount_cents - o.pay_at_door_cents, 0) for o in completed)
    door_cents = sum(o.pay_at_door_cents for o in completed)

    seats = (OrderItem.objects.filter(order__in=completed, is_addon=False)
             .aggregate(n=Sum('quantity'))['n'] or 0)
    drink_items = OrderItem.objects.filter(order__in=completed, is_addon=True)
    drinks = drink_items.aggregate(n=Sum('quantity'))['n'] or 0
    drinks_cents = sum(i.quantity * i.unit_price_cents for i in drink_items)
    orders_with_drinks = completed.filter(items__is_addon=True).distinct().count()

    # The funnel. `checkout_engaged` is written when somebody starts filling the checkout in; an order row
    # exists from the moment the details are submitted, so the gap between the two is the form itself.
    reached = TrackedEvent.objects.filter(kind='checkout', name='checkout_engaged', created_at__gte=since).count()
    began = started.count()
    finished = completed.count()
    # The counter was added after these orders were taken, so for a while the top of the funnel is narrower than
    # the bottom. Say so rather than print an impossible percentage.
    partial = reached < began

    # Per show, newest first. A night nobody has booked is still worth a row: an empty upcoming show is the
    # thing this page exists to make visible.
    shows = []
    for event in Event.objects.filter(date__gte=timezone.now() - timedelta(days=days)).order_by('date'):
        rows = OrderItem.objects.filter(order__event=event, order__status=Order.COMPLETED)
        show_seats = rows.filter(is_addon=False).aggregate(n=Sum('quantity'))['n'] or 0
        show_drinks = rows.filter(is_addon=True)
        capacity = sum(t.capacity for t in event.ticket_types.filter(active=True, is_addon=False)
                       if t.capacity is not None)
        paid = sum(max(o.total_amount_cents - o.pay_at_door_cents, 0)
                   for o in Order.objects.filter(event=event, status=Order.COMPLETED))
        free_night = not any(t.price_cents for t in event.ticket_types.filter(active=True, is_addon=False))
        shows.append({
            'event': event,
            'free': free_night,
            'capacity': capacity,
            'seats': show_seats,
            'left': max(0, capacity - show_seats) if capacity else None,
            'full': round(show_seats / capacity * 100) if capacity else None,
            'drinks': show_drinks.aggregate(n=Sum('quantity'))['n'] or 0,
            'revenue': _money(paid, event.currency),
            'revenue_cents': paid,
        })

    daily_orders = _daily(completed, 'completed_at', min(days, 60))

    tables = TableOrder.objects.filter(created_at__gte=since)
    table_cents = tables.aggregate(n=Sum('total_cents'))['n'] or 0

    return render(request, 'embed/revenue.html', {
        'days': days,
        'ranges': (7, 30, 90),
        'online': _money(online_cents),
        'door': _money(door_cents),
        'tables_total': _money(table_cents),
        'tables_count': tables.count(),
        'seats': seats,
        'drinks': drinks,
        'drinks_money': _money(drinks_cents),
        'orders_with_drinks': orders_with_drinks,
        # The number the open mic lives or dies on: a free seat only pays if it comes with a drink.
        'attach_rate': round(orders_with_drinks / finished * 100) if finished else 0,
        'partial_funnel': partial,
        'funnel': [
            ('Started filling the checkout', reached, None),
            ('Submitted their details', began, None if partial else (round(began / reached * 100) if reached else None)),
            ('Finished', finished, round(finished / began * 100) if began else None),
        ],
        'shows': shows,
        'today': timezone.localtime().date(),
        'daily_orders': daily_orders,
        # The tallest bar, so `widthratio` has something to scale against. Never zero: a day with no bookings
        # must draw a flat line rather than divide by nothing.
        'max_daily': max(list(daily_orders.values()) + [1]),
        'recent': completed.select_related('event').order_by('-completed_at')[:15],
        'open_tables': tables.filter(status=TableOrder.OPEN).order_by('-created_at')[:10],
    })
