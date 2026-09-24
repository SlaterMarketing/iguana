"""The bar's board: who has ordered, from which table, and what they owe.

Read during a show, on a phone, in a dark room, by someone holding a tray. So: big numbers, colour that means
one thing, and one button per table. A table with nothing on it is still listed, because "table 7 is quiet" is
information too and an empty screen looks broken.

Closing a table marks its open orders delivered. It is the only action, it cannot be undone from here by
accident (the admin can), and the table drops off the board the moment it is closed.

Staff only, on the API domain, sharing the admin session rather than inventing a login.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from sales.i18n import lang_from_request, normalize
from sales.models import TableOrder
from sales.services import format_money

from .menu_views import MAX_TABLE

# What the board lays out when the room is quiet. The club has fewer tables than the 100 a QR can name, and a
# board of a hundred empty squares is unreadable; the rest appear the moment somebody orders from one.
TABLES_ON_SHOW = 12
CANCUN = ZoneInfo('America/Cancun')


def service_start(now=None):
    """When tonight's service began, in Cancun: 6am today, or 6am yesterday if it is still the small hours.

    A show starting at nine runs past midnight, and a tab that crosses midnight is one tab. Counting by
    calendar day would hand the bar a table that owes nothing at 00:05 while the people are still sitting at it.
    """
    local = (now or timezone.now()).astimezone(CANCUN)
    day = local.date() if local.hour >= 6 else local.date() - timedelta(days=1)
    return datetime.combine(day, time(6, 0), tzinfo=CANCUN)


def _board(lang):
    open_orders = (TableOrder.objects.filter(status=TableOrder.OPEN)
                   .prefetch_related('items').order_by('created_at'))
    by_table = {}
    for order in open_orders:
        row = by_table.setdefault(order.table_number, {'number': order.table_number, 'orders': [],
                                                       'cents': 0, 'currency': order.currency})
        row['orders'].append(order)
        row['cents'] += order.total_cents

    # What the table owes for the night, not just what is waiting to be carried over. Payment happens at the
    # end, so a round already delivered is still money on that table, and the board was the only place anybody
    # would look for it.
    tab = {}
    for order in (TableOrder.objects.filter(created_at__gte=service_start())
                  .exclude(status=TableOrder.CANCELLED)):
        row = tab.setdefault(order.table_number, {'cents': 0, 'currency': order.currency, 'rounds': 0})
        row['cents'] += order.total_cents
        row['rounds'] += 1

    numbers = sorted(set(by_table) | set(tab) | set(range(1, TABLES_ON_SHOW + 1)))
    tables = []
    for number in numbers:
        row = by_table.get(number)
        waited = None
        if row:
            waited = int((timezone.now() - row['orders'][0].created_at).total_seconds() // 60)
        running = tab.get(number)
        tables.append({
            'number': number,
            'orders': row['orders'] if row else [],
            'items': ', '.join(o.summary for o in row['orders']) if row else '',
            'due': format_money(row['cents'], row['currency']) if row else '',
            'cents': row['cents'] if row else 0,
            # The whole tab for the night, delivered rounds included. Shown even when nothing is waiting,
            # because a table that has stopped ordering still has to pay.
            'tab': format_money(running['cents'], running['currency']) if running else '',
            'tab_cents': running['cents'] if running else 0,
            'rounds': running['rounds'] if running else 0,
            'waited': waited,
            # Amber once it has been sitting a while: the number that matters to somebody holding a tray is not
            # how much, it is how long.
            'late': waited is not None and waited >= 10,
        })
    return tables


@staff_member_required
def tables(request):
    lang = lang_from_request(request)
    board = _board(lang)
    return render(request, 'embed/tables.html', {
        'lang': lang,
        'tables': board,
        'open_count': sum(1 for t in board if t['orders']),
        'max_table': MAX_TABLE,
    })


@staff_member_required
@require_POST
def close_table(request, number):
    """Everything open on this table has been delivered."""
    closed = (TableOrder.objects.filter(table_number=number, status=TableOrder.OPEN)
              .update(status=TableOrder.DELIVERED, delivered_at=timezone.now()))
    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({'closed': closed, 'table': number})
    return redirect('tables')
