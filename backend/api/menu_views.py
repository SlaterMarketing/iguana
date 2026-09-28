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
from sales.links import public_base
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

    # Since 2026-09-28 a QR round lands on the table's check in the point of sale (pos.services), UNSENT, so the
    # waiter confirms it and sends it to the bar; the map flashes the table orange until they do.
    from django.db import transaction as _tx

    from pos.services import PosError, customer_order

    try:
        with _tx.atomic():
            cuenta, lines = customer_order(table, quantities, note=str(body.get('note') or ''),
                                           name=str(body.get('name') or ''))
    except PosError:
        return JsonResponse({'error': tr(lang, 'Those items are not available right now.')}, status=400)
    total = sum(l.total_cents for l in lines)
    _notify_pos_order(table, lines, total, str(body.get('note') or ''))
    return JsonResponse({
        'id': cuenta.id,
        'table': table,
        'totalCents': total,
        'currency': 'MXN',
        'message': tr(lang, 'Order sent to the bar. Someone will bring it to table {0}.', str(table)),
    })


def _notify_pos_order(table, lines, total, note):
    """The bar's email for a QR order, now pointing at the point of sale."""
    if not settings.NOTIFY_EMAILS or not lines:
        return 0
    from django.core.mail import EmailMessage

    summary = ', '.join(f'{l.quantity} {l.name}' for l in lines)
    body = [f'Table {table}', f'Ordered: {summary}', f'Total: {format_money(total, "mxn")}',
            'Confirm and send it from the point of sale.']
    if note:
        body += ['', f'Note: {note}']
    body += ['', f'{public_base()}/pos/']
    try:
        return EmailMessage(f'Table {table}: {summary}'[:150], '\n'.join(body), settings.DEFAULT_FROM_EMAIL,
                            list(settings.NOTIFY_EMAILS)).send(fail_silently=True)
    except Exception:
        return 0


# How far past the tables we have a number may reach and still be believed. A club adds a table or two at a
# time, so a 15 when the board says 12 is a table somebody carried in; an 87 is a typo, and auto-growing to it
# would draw 75 empty cards and make the board useless. Past this the round still arrives and still shows,
# because the board unions in any table that has one; only the count of EMPTY cards is left alone.
AUTO_ADD_REACH = 6


def create_round(table, quantities, items, lang='es', note='', notify=True, guest_name=''):
    """Put a round on a table's bill. One function, because there are two ways in and they must agree.

    The customer scans the QR and orders; a waiter takes it verbally and enters it at `/mesas/`. Those are the
    same event as far as the bar, the bill and the store room are concerned, so they build the same row: the
    name and unit price are snapshotted here, and the night is stamped now rather than worked out later,
    because which night a round belongs to is obvious while it is being poured and guesswork afterwards.
    """
    from .tables_views import current_show

    with transaction.atomic():
        order = TableOrder.objects.create(
            table_number=table, locale=lang, note=str(note or '')[:300],
            guest_name=str(guest_name or '').strip()[:80],
            currency=(next(iter(items.values())).currency or 'mxn'),
            event=current_show(),
        )
        _stretch_to_fit(table)
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

    if notify:
        # After commit and never blocking: an order the bar can see is worth more than an email, and a mail
        # server having a bad night must not lose the round.
        transaction.on_commit(lambda: notify_table_order(order))
    return order


def _stretch_to_fit(table):
    """Somebody ordered from a table the board does not have, so add it.

    The bar carries a table in and nobody stops to update a setting first: the round arrives from table 15
    while the board says twelve. It showed up anyway (the board unions in any table with a round) but the
    empty cards stopped at twelve, so the next table to be used was invisible until it ordered too.

    Bounded by `AUTO_ADD_REACH` because the same field takes typos. 15 against 12 is a table; 87 is a slip,
    and growing to it would draw 75 empty cards.
    """
    from catalog.models import FloorSettings

    row = FloorSettings.load()
    if row.tables < table <= row.tables + AUTO_ADD_REACH:
        row.tables = table
        row.updated_by = 'auto'
        row.save(update_fields=['tables', 'updated_at', 'updated_by'])


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
    lines += ['', f'{public_base()}/tables/']
    try:
        return EmailMessage(subject, '\n'.join(lines), settings.DEFAULT_FROM_EMAIL,
                            list(settings.NOTIFY_EMAILS)).send(fail_silently=True)
    except Exception:
        return 0
