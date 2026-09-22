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
from django.contrib.auth.decorators import user_passes_test
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


def _with_money(rows, cents_field, attribute):
    """Hang a formatted amount on each row. A template filter cannot see the row's own currency, and printing
    the raw cents beside a currency code reads ten dollars as "1000 USD"."""
    rows = list(rows)
    for row in rows:
        setattr(row, attribute, _money(getattr(row, cents_field), getattr(row, 'currency', 'mxn')))
    return rows


def _amounts(by_currency):
    """'300.00 MXN · 10.00 USD', never one number.

    The English nights sell in dollars and the Spanish ones in pesos. Adding the cents together and printing one
    currency is not a rounding problem, it is a wrong number, and it is the kind that gets believed.
    """
    rows = [(c, n) for c, n in sorted(by_currency.items()) if n]
    return ' · '.join(_money(n, c) for c, n in rows) if rows else '0.00 MXN'


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


# 🚨 `staff_member_required` alone is NOT enough here, and that is not obvious.
#
# It checks `is_staff` and nothing else, so every staff account reaches every page guarded by it. The bar has
# its own account with a password its staff can type on a phone in a dark room, and that account has no business
# reading customer names, email addresses or what the club is taking. This page asks for more: a superuser, or
# somebody explicitly given `sales.view_order`.
#
# The board at /tables/ deliberately keeps the weaker gate, because it shows table numbers and drinks and no
# person at all.
def can_see_the_money(user):
    return user.is_active and user.is_staff and (user.is_superuser or user.has_perm('sales.view_order'))


@user_passes_test(can_see_the_money, login_url='/admin/login/')
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
    #
    # Split by currency and never added up. The English nights are priced in USD and the Spanish ones in MXN,
    # so one total is not a total: it read "10.00 MXN" for an order that was ten dollars.
    online, door = {}, {}
    for order in completed:
        currency = (order.currency or 'mxn').upper()
        online[currency] = online.get(currency, 0) + max(order.total_amount_cents - order.pay_at_door_cents, 0)
        door[currency] = door.get(currency, 0) + order.pay_at_door_cents

    seats = (OrderItem.objects.filter(order__in=completed, is_addon=False)
             .aggregate(n=Sum('quantity'))['n'] or 0)
    drink_items = OrderItem.objects.filter(order__in=completed, is_addon=True).select_related('order')
    drinks = drink_items.aggregate(n=Sum('quantity'))['n'] or 0
    drinks_money = {}
    for item in drink_items:
        currency = (item.order.currency or 'mxn').upper()
        drinks_money[currency] = drinks_money.get(currency, 0) + item.quantity * item.unit_price_cents
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
        # Per show, and by currency for the same reason as the headline: an event can carry orders in both if
        # its price was ever changed, and one total would be a wrong number rather than a rounded one.
        paid = {}
        for order in Order.objects.filter(event=event, status=Order.COMPLETED):
            currency = (order.currency or event.currency or 'mxn').upper()
            paid[currency] = paid.get(currency, 0) + max(order.total_amount_cents - order.pay_at_door_cents, 0)
        free_night = not any(t.price_cents for t in event.ticket_types.filter(active=True, is_addon=False))
        shows.append({
            'event': event,
            'free': free_night,
            'capacity': capacity,
            'seats': show_seats,
            'left': max(0, capacity - show_seats) if capacity else None,
            'full': round(show_seats / capacity * 100) if capacity else None,
            'drinks': show_drinks.aggregate(n=Sum('quantity'))['n'] or 0,
            'revenue': _amounts(paid),
            'earned': any(paid.values()),
        })

    daily_orders = _daily(completed, 'completed_at', min(days, 60))

    tables = TableOrder.objects.filter(created_at__gte=since)
    table_money = {}
    for order in tables:
        currency = (order.currency or 'mxn').upper()
        table_money[currency] = table_money.get(currency, 0) + order.total_cents

    return render(request, 'embed/revenue.html', {
        'days': days,
        'ranges': (7, 30, 90),
        'online': _amounts(online),
        'door': _amounts(door),
        'tables_total': _amounts(table_money),
        'tables_count': tables.count(),
        'seats': seats,
        'drinks': drinks,
        'drinks_money': _amounts(drinks_money),
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
        'recent': _with_money(completed.select_related('event').order_by('-completed_at')[:15],
                              'total_amount_cents', 'paid'),
        'open_tables': _with_money(tables.filter(status=TableOrder.OPEN).order_by('-created_at')[:10],
                                   'total_cents', 'money'),
    })
