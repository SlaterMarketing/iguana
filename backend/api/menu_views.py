"""The bar menu, and a round ordered from a table.

The table's QR carries its number, so an order knows where it is going. That is the whole feature: during a set
nobody wants to stand up, and catching a waiter's eye in a dark room is the thing the club loses drink sales to.

Payment stays at the table, where it already is. This replaces the waiting, not the till, which is also why an
order needs no card details and cannot fail halfway.
"""

import json

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import MenuCategory, MenuItem
from sales.i18n import normalize, tr
from sales.models import TableOrder, TableOrderItem
from sales.services import format_money

from .auth import api_view

# The room's tables. A QR is printed once and stuck to a table, so this is a fixed range rather than a count of
# rows in a table nobody maintains: table 7's code has to keep working whether or not anyone has told us it exists.
MAX_TABLE = 100
# One person can order a lot for a table, but not a hundred of anything.
MAX_PER_ITEM = 20


def valid_table(number):
    return isinstance(number, int) and 1 <= number <= MAX_TABLE


@api_view()
def menu(request):
    lang = normalize(request.GET.get('locale'))
    rows = (MenuCategory.objects.filter(active=True)
            .prefetch_related('items'))
    return JsonResponse({
        'maxTable': MAX_TABLE,
        'categories': [
            {
                'id': category.id,
                'name': category.label(lang),
                'items': [
                    {
                        'id': item.id,
                        'name': item.label(lang),
                        'description': item.details(lang),
                        'priceCents': item.price_cents,
                        'currency': item.currency.upper(),
                    }
                    for item in category.items.all() if item.available
                ],
            }
            for category in rows
            if any(item.available for item in category.items.all())
        ],
    })


@api_view(methods=('POST',))
@require_POST
def table_order(request):
    body = request.json if isinstance(getattr(request, 'json', None), dict) else {}
    lang = normalize(body.get('lang'))
    table = body.get('table')
    try:
        table = int(table)
    except (TypeError, ValueError):
        table = None
    if not valid_table(table):
        return JsonResponse({'error': tr(lang, 'That table number does not exist.')}, status=400)

    wanted = body.get('items') if isinstance(body.get('items'), dict) else {}
    quantities = {}
    for key, value in wanted.items():
        try:
            qty = int(value)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            quantities[str(key)] = min(qty, MAX_PER_ITEM)
    if not quantities:
        return JsonResponse({'error': tr(lang, 'Choose something first.')}, status=400)

    items = {i.id: i for i in MenuItem.objects.filter(id__in=quantities, available=True)}
    if not items:
        return JsonResponse({'error': tr(lang, 'Those items are not available right now.')}, status=400)

    with transaction.atomic():
        order = TableOrder.objects.create(
            table_number=table, locale=lang, note=str(body.get('note') or '')[:300],
            currency=(next(iter(items.values())).currency or 'mxn'),
        )
        total = 0
        for item_id, qty in quantities.items():
            item = items.get(item_id)
            if not item:
                continue
            TableOrderItem.objects.create(order=order, menu_item=item, name=item.label(lang), quantity=qty,
                                          unit_price_cents=item.price_cents)
            total += item.price_cents * qty
        order.total_cents = total
        order.save(update_fields=['total_cents'])

    # After commit and never blocking: an order the bar can see is worth more than an email, and a mail server
    # having a bad night must not lose the round.
    transaction.on_commit(lambda: notify_table_order(order))
    return JsonResponse({
        'id': order.id,
        'table': order.table_number,
        'totalCents': order.total_cents,
        'currency': order.currency.upper(),
        'message': tr(lang, 'Order sent to the bar. Someone will bring it to table {0}.', str(table)),
    })


def notify_table_order(order):
    """Tell the bar. The subject line carries the table and the round, because that is all a phone shows."""
    if not settings.NOTIFY_EMAILS:
        return 0
    from django.core.mail import EmailMessage

    subject = f'Table {order.table_number}: {order.summary}'
    lines = [
        f'Table {order.table_number}',
        f'Ordered: {order.summary}',
        f'Total: {format_money(order.total_cents, order.currency)} (to collect at the table)',
        f'Placed: {timezone.localtime(order.created_at):%H:%M}',
    ]
    if order.note:
        lines += ['', f'Note: {order.note}']
    lines += ['', f'{settings.BACKEND_URL}/admin/sales/tableorder/{order.id}/change/']
    try:
        return EmailMessage(subject, '\n'.join(lines), settings.DEFAULT_FROM_EMAIL,
                            list(settings.NOTIFY_EMAILS)).send(fail_silently=True)
    except Exception:
        return 0
