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


def current_show(now=None):
    """The show this service belongs to: the one whose date falls inside the 6am-to-6am window.

    One show a night at the moment, so this is unambiguous. If two ever land on one night it takes the later
    one, because the bar's evening belongs to whatever is on stage when the drinks are being poured.
    """
    from catalog.models import Event

    # Matched on the CALENDAR DAY, not on a timestamp window. An event's date is stored early in its own day,
    # so a 6am-to-6am window over timestamps catches TOMORROW's show from this afternoon: it picked Friday's
    # Privilegio on a Thursday with nothing on. The service's date is the day it began, which after midnight is
    # still yesterday, so a tab that crosses midnight still belongs to the show it was poured at.
    return (Event.objects.filter(status=Event.ACTIVE, date__date=service_start(now).date())
            .order_by('-date').first())


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
        row = tab.setdefault(order.table_number, {'cents': 0, 'currency': order.currency, 'rounds': 0,
                                                  'paid_cents': 0})
        row['cents'] += order.total_cents
        row['rounds'] += 1
        if order.status == TableOrder.PAID:
            row['paid_cents'] += order.total_cents

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
            # Settled when every round on the table has been paid for. A table halfway through paying is not
            # settled, because the number the bar is owed is still not zero.
            'settled': bool(running and running['paid_cents'] == running['cents']),
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
    show = current_show()
    taken, owed, currency = 0, 0, 'mxn'
    rounds = 0
    for order in TableOrder.objects.filter(created_at__gte=service_start()).exclude(status=TableOrder.CANCELLED):
        currency = order.currency or currency
        rounds += 1
        if order.status == TableOrder.PAID:
            taken += order.total_cents
        else:
            owed += order.total_cents
    return render(request, 'embed/tables.html', {
        'lang': lang,
        'tables': board,
        'open_count': sum(1 for t in board if t['orders']),
        'max_table': MAX_TABLE,
        'show': show,
        'show_name': show.label(lang) if show else '',
        'show_time': show.show_time if show else '',
        'rounds': rounds,
        'taken': format_money(taken, currency) if taken else '',
        'owed': format_money(owed, currency) if owed else '',
    })


@staff_member_required
@require_POST
def settle_table(request, number):
    """They have paid. Everything on this table tonight is settled, and anything still open was clearly served.

    Reversible on purpose: this is a tap on a phone in a dark room, and marking a table paid that has not paid
    is money walking out of the door. `?undo=1` puts it back.
    """
    rounds = TableOrder.objects.filter(table_number=number, created_at__gte=service_start()).exclude(
        status=TableOrder.CANCELLED)
    if request.GET.get('undo') or request.POST.get('undo'):
        rounds.filter(status=TableOrder.PAID).update(status=TableOrder.DELIVERED, paid_at=None)
    else:
        now = timezone.now()
        rounds.filter(delivered_at__isnull=True).update(delivered_at=now)
        rounds.exclude(status=TableOrder.PAID).update(status=TableOrder.PAID, paid_at=now)
    return redirect('tables')


@staff_member_required
@require_POST
def close_table(request, number):
    """Everything open on this table has been delivered."""
    closed = (TableOrder.objects.filter(table_number=number, status=TableOrder.OPEN)
              .update(status=TableOrder.DELIVERED, delivered_at=timezone.now()))
    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({'closed': closed, 'table': number})
    return redirect('tables')
