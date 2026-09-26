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

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from sales.i18n import lang_from_request
from sales.models import TableOrder
from sales.stock import apply_stock, deliver, void_line
from sales.services import format_money

from .floor import floor_required
from .menu_views import MAX_TABLE

# What the board lays out when the room is quiet. The club has fewer tables than the 100 a QR can name, and a
# board of a hundred empty squares is unreadable; the rest appear the moment somebody orders from one.
def table_labels():
    """What each spot is called. Missing means the plain "Mesa N" the template falls back to."""
    from catalog.models import FloorSettings

    raw = FloorSettings.load().labels or {}
    return {str(k): str(v).strip()[:40] for k, v in raw.items() if str(v).strip()}


def tables_on_show():
    """How many table cards to draw, from the floor settings the bar edits at `/mesas/`.

    Read per request rather than cached: it changes when somebody carries another table in, and a board that
    needed a restart to notice would be the reason nobody bothered to update it.
    """
    from catalog.models import FloorSettings

    return FloorSettings.load().tables
CANCUN = ZoneInfo('America/Cancun')


def _who(request):
    return (request.user.get_full_name() or request.user.get_username())[:80] if request.user.is_authenticated else ''


def _back(request):
    """Back to whichever board they pressed the button on: `/mesas/` for the floor, `/tables/` from the admin."""
    referer = request.META.get('HTTP_REFERER') or ''
    return '/mesas/' if '/mesas' in referer else 'tables'


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
    # 🚨 SOLD_OUT is still a show, and this is where forgetting that costs money. Marking Privilegio sold out
    # on the afternoon of 2026-09-25 made this return None for its own night: the bar board would have shown
    # no show, and every round poured would have been stamped `event=None`, so "what did the bar take on the
    # Privilegio night" would have had no answer for the busiest night of the week. Only DRAFT and CANCELLED
    # are not a show.
    return (Event.objects.filter(status__in=(Event.ACTIVE, Event.SOLD_OUT),
                                 date__date=service_start(now).date())
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
    for order in (TableOrder.objects.filter(created_at__gte=service_start(), closed_at__isnull=True)
                  .exclude(status=TableOrder.CANCELLED)):
        row = tab.setdefault(order.table_number, {'cents': 0, 'currency': order.currency, 'rounds': 0,
                                                  'paid_cents': 0})
        row['cents'] += order.total_cents
        row['rounds'] += 1
        if order.status == TableOrder.PAID:
            row['paid_cents'] += order.total_cents

    numbers = sorted(set(by_table) | set(tab) | set(range(1, tables_on_show() + 1)))
    labels = table_labels()
    tables = []
    for number in numbers:
        row = by_table.get(number)
        waited = None
        if row:
            waited = int((timezone.now() - row['orders'][0].created_at).total_seconds() // 60)
        running = tab.get(number)
        tables.append({
            'number': number,
            # Blank unless somebody named it; the template prints "Mesa N" when it is.
            'label': labels.get(str(number), ''),
            'orders': row['orders'] if row else [],
            'items': ', '.join(o.summary for o in row['orders']) if row else '',
            # Whoever put their name on a round that is still waiting. A tray arriving with a name on it beats
            # one held over a table asking who had the margarita.
            'who': ', '.join(sorted({o.guest_name for o in row['orders'] if o.guest_name})) if row else '',
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


def board_version():
    """A short fingerprint of everything the board draws, cheap enough to ask for every few seconds.

    🚨 Deliberately NOT a push. Gunicorn runs three SYNC workers, so an SSE or long-poll connection pins one
    worker for as long as a tablet has the page open: three tablets would consume every worker and the whole
    site, checkout included, would stop answering. A poll that asks "has anything changed" and almost always
    hears no costs one short query and holds nothing.

    It hashes what is VISIBLE rather than a timestamp column, so it catches the cases a `max(created_at)` would
    miss: a round marked delivered, a table settled, a line voided (which moves `total_cents`), and somebody
    changing how many tables there are.
    """
    import hashlib

    from catalog.models import FloorSettings

    rows = (TableOrder.objects.filter(created_at__gte=service_start())
            .order_by('pk').values_list('pk', 'status', 'total_cents', 'delivered_at', 'paid_at'))
    digest = hashlib.blake2s(repr(list(rows)).encode(), digest_size=8)
    digest.update(str(FloorSettings.load().tables).encode())
    return digest.hexdigest()


@floor_required
def board_state(request):
    """What the board polls. One number, so the answer is the same size whether anything happened or not."""
    return JsonResponse({'v': board_version()})


@floor_required
def tables(request):
    """The board as the admin has always served it: bilingual, following the staff phone's language."""
    return _render_board(request, lang_from_request(request), floor=False)


@floor_required
def mesas(request):
    """The same board at `/mesas/`, in Spanish, with the floor console's own navigation.

    Spanish is not negotiated here, unlike `/tables/`, which reads `Accept-Language`. The floor console has one
    audience and it works in Spanish; a board that changed language because somebody picked up the wrong phone
    is a worse board. The nav strip is the only other difference, because a floor account has nowhere else to
    go: no admin, so the links out have to be on the page.
    """
    return _render_board(request, 'es', floor=True)


def _render_board(request, lang, floor):
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
    # The queue, in TABLE ORDER, so somebody holding a tray walks the room in one direction instead of
    # zig-zagging across it. It used to be longest-waiting first, which sounds fairer and makes the carrier
    # cross the room between drinks (owner, 2026-09-25). Nothing is lost by the change: a round that has been
    # sitting turns amber past ten minutes and says how long, so the one that needs hurrying still stands out
    # wherever it is in the list. Grouped by table because that is what Delivered closes.
    waiting = sorted((t for t in board if t['orders']), key=lambda t: t['number'])

    # Which table is showing its breakdown. It lives in the URL rather than in a <details> element because this
    # page reloads itself every twenty seconds, and a panel that snaps shut mid-read is worse than no panel.
    try:
        opened = int(request.GET.get('open', ''))
    except ValueError:
        opened = 0
    if opened:
        # Its own name, never `rounds`: that one is the night's COUNT for the header, and shadowing it printed
        # a raw `<QuerySet [<TableOrder: ...>]>` across the top of the live board the moment anybody opened a
        # breakdown (2026-09-25). Django templates have no `int` to fall back on, so the repr just renders.
        detail_rounds = (TableOrder.objects.filter(table_number=opened, created_at__gte=service_start())
                         .exclude(status=TableOrder.CANCELLED).prefetch_related('items').order_by('created_at'))
        detail = [{
            'at': order.created_at.astimezone(CANCUN),
            'status': order.status,
            'waiting': order.status == TableOrder.OPEN,
            'paid': order.status == TableOrder.PAID,
            'total': format_money(order.total_cents, order.currency),
            'items': [{'id': i.id, 'quantity': i.quantity, 'name': i.name,
                       'line': format_money(i.unit_price_cents * i.quantity, order.currency),
                       'voided': i.voided, 'void_reason': i.get_void_reason_display() if i.voided else '',
                       'void_note': i.void_note, 'voided_by': i.voided_by}
                      for i in order.items.all()],
            'note': order.note,
            'who': order.guest_name,
        } for order in detail_rounds]
        for row in board:
            if row['number'] == opened:
                row['breakdown'] = detail
                row['is_open'] = True
    return render(request, 'embed/tables.html', {
        'lang': lang,
        'floor': floor,
        'tables': board,
        'waiting': waiting,
        'open_count': sum(1 for t in board if t['orders']),
        'max_table': MAX_TABLE,
        'tables_count': tables_on_show(),
        'board_version': board_version(),
        'show': show,
        'show_name': show.label(lang) if show else '',
        'show_time': show.show_time if show else '',
        'rounds': rounds,
        'taken': format_money(taken, currency) if taken else '',
        'owed': format_money(owed, currency) if owed else '',
    })


@floor_required
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
        # Anything still open when the table pays was clearly carried over, so it leaves the store room here
        # too. `apply_stock` is what makes that safe to say twice: a round Delivered already accounted for is
        # skipped rather than counted again. Done BEFORE the bulk update, because a queryset `.update()` never
        # loads a row and so can never decrement anything.
        for order in rounds.exclude(status=TableOrder.PAID):
            apply_stock(order, who=_who(request))
        rounds.filter(delivered_at__isnull=True).update(delivered_at=now)
        rounds.exclude(status=TableOrder.PAID).update(status=TableOrder.PAID, paid_at=now)
    return redirect(_back(request))


@floor_required
def add_round(request, number):
    """Put a round on a table's bill from the floor, for an order taken verbally.

    Not everybody scans the QR on the table, and a waiter who takes an order at the table had no way to get it
    onto the bill: the board could take a line OFF and never put one on, so anything ordered out loud was
    either lost or written on paper and added up by hand at the end of the night.

    It creates the same row the customer's own order creates, through `menu_views.create_round`.

    🚨 It lands DELIVERED, not waiting (dueño, 2026-09-25: "entregado no aplica porque nadie está ordenando
    por el sitio web ahorita, son los meseros poniendo órdenes"). Waiting-then-Delivered is a QUEUE, and a
    queue only means something when the order arrives from somewhere other than the person who will carry it.
    While the waiters are the ones typing, every round would be entered and then immediately confirmed by the
    same pair of hands, which is one pointless tap per round during service and a button that says nothing
    when it is pressed.
    The stock still moves exactly once, through `deliver` rather than a status write, so the count sheet
    behaves the same as it always did.
    ⚠ The CUSTOMER's own QR order still lands WAITING, because there the bar genuinely has not made it yet.
    That is what Delivered is for, and it comes back on its own the day anybody scans a table QR.
    """
    from catalog.models import MenuCategory, MenuItem
    from .menu_views import MAX_PER_ITEM, create_round, valid_table

    if not valid_table(number):
        return redirect('/mesas/')

    if request.method == 'POST':
        quantities = {}
        for key, value in request.POST.items():
            if not key.startswith('q:'):
                continue
            try:
                qty = int(value)
            except (TypeError, ValueError):
                continue
            if qty > 0:
                quantities[key[2:]] = min(qty, MAX_PER_ITEM)
        items = {i.id: i for i in MenuItem.objects.filter(id__in=quantities, available=True)}
        if quantities and items:
            # No email to the bar: the person entering this IS the bar, and a notification about your own
            # keystrokes is noise that teaches people to ignore the channel.
            order = create_round(number, quantities, items, lang='es', note=request.POST.get('note', ''),
                                 guest_name=request.POST.get('nombre', ''), notify=False)
            # Through `deliver`, never a status write: it is what moves the stock, and it is guarded so a
            # double post cannot take the ingredients out twice.
            deliver(order, who=_who(request))
            return redirect(f'/mesas/?open={number}#t{number}')
        return redirect(f'/mesas/mesa/{number}/agregar/?vacio=1')

    categories = [
        {'name': c.name_es or c.name,
         'items': [i for i in c.items.all() if i.available]}
        for c in MenuCategory.objects.filter(active=True).prefetch_related('items')
    ]
    # What this table already has, because "add more" without seeing the current bill is how a round gets
    # ordered twice. Same service window and the same exclusions as the board, so the two agree.
    running = (TableOrder.objects.filter(table_number=number, created_at__gte=service_start(),
                                         closed_at__isnull=True)
               .exclude(status=TableOrder.CANCELLED).prefetch_related('items').order_by('created_at'))
    rounds = list(running)
    so_far = sum(o.total_cents for o in rounds)
    return render(request, 'floor/agregar.html', {
        'number': number,
        'label': table_labels().get(str(number), ''),
        'grupos': [c for c in categories if c['items']],
        'vacio': request.GET.get('vacio'),
        'rounds': rounds,
        'so_far': format_money(so_far, rounds[0].currency if rounds else 'mxn') if so_far else '',
        'already': ', '.join(o.summary for o in rounds if o.summary),
    })


@floor_required
@require_POST
def set_tables(request):
    """Change how many tables the room has, from the board.

    Lowering it is safe by construction rather than by a guard: the board unions in every table that has a
    round tonight, so a table with an open tab keeps its card even if the count drops below its number. Money
    on a table can never be hidden by this, which is why it does not need a confirmation.
    """
    from catalog.models import FloorSettings

    settings_row = FloorSettings.load()
    raw = request.POST.get('tables', '')
    if request.POST.get('more'):
        wanted = settings_row.tables + 1
    elif request.POST.get('fewer'):
        wanted = settings_row.tables - 1
    else:
        try:
            wanted = int(str(raw).strip())
        except (TypeError, ValueError):
            wanted = settings_row.tables
    settings_row.tables = max(1, min(MAX_TABLE, wanted))
    settings_row.updated_by = _who(request)
    settings_row.save(update_fields=['tables', 'updated_at', 'updated_by'])
    return redirect(_back(request))


@floor_required
@require_POST
def name_table(request, number):
    """Call a spot what the staff call it: Box 1, Barra, Terraza.

    The NUMBER still routes everything, so a renamed spot keeps working for the QR on it and for a customer
    typing a number into the menu. This is only what the board and the bill say.
    """
    from catalog.models import FloorSettings

    row = FloorSettings.load()
    labels = dict(row.labels or {})
    name = (request.POST.get('label') or '').strip()[:40]
    if name:
        labels[str(number)] = name
    else:
        labels.pop(str(number), None)   # cleared: back to "Mesa N"
    row.labels = labels
    row.updated_by = _who(request)
    row.save(update_fields=['labels', 'updated_at', 'updated_by'])
    destination = _back(request)
    if destination == '/mesas/':
        return redirect(f'/mesas/?open={number}#t{number}')
    return redirect(destination)


@floor_required
@require_POST
def close_out(request, number):
    """The party paid and left: clear the table for the next one.

    🚨 Only once everything on it is paid. Clearing a table that still owes money would take the one number
    the bar is owed off the only screen anybody looks at, which is the same mistake pressing Delivered used to
    make. Unpaid rounds are settled first, or taken off the bill one line at a time.

    The rounds are not deleted and the money stays in the night: `/stats/` and the takings count every
    non-cancelled round whether or not it was closed. All this does is stop it being this table's running tab,
    so the next people do not sit down in front of somebody else's bill.
    """
    rounds = TableOrder.objects.filter(table_number=number, created_at__gte=service_start(),
                                       closed_at__isnull=True).exclude(status=TableOrder.CANCELLED)
    if request.GET.get('undo') or request.POST.get('undo'):
        TableOrder.objects.filter(table_number=number, created_at__gte=service_start()).update(closed_at=None)
    elif rounds.exists() and not rounds.exclude(status=TableOrder.PAID).exists():
        rounds.update(closed_at=timezone.now())
    return redirect(_back(request))


@floor_required
@require_POST
def void_item(request, number, item_id):
    """Take a line off a table's bill, because it was not ordered or was not any good.

    🚨 The reason is not paperwork, it decides the arithmetic. "No se preparó" puts the ingredients back on the
    shelf; "Se preparó y se tiró" leaves the count alone because the drink is in a bin, and a sheet that
    claimed it was on the shelf would send somebody looking for it. `sales/stock.py::void_line` holds both.

    Not a delete. The line stays on the round, struck through, with who took it off: the bar wants it gone from
    the bill, which it is, but "remove a drink from the bill" is also how money leaves a till, so it has to
    leave a trace. A deleted row would change the night's takings and leave nothing behind.
    """
    from sales.models import TableOrderItem

    item = (TableOrderItem.objects
            .filter(id=item_id, order__table_number=number, order__created_at__gte=service_start())
            .exclude(order__status=TableOrder.CANCELLED)
            .select_related('order', 'menu_item').first())
    if item is not None:
        void_line(item, request.POST.get('reason', ''), note=request.POST.get('note', ''), who=_who(request))
    destination = _back(request)
    if destination == '/mesas/':
        return redirect(f'/mesas/?open={number}#t{number}')
    return redirect(f'/tables/?open={number}#t{number}')


@floor_required
@require_POST
def close_table(request, number):
    """Everything open on this table has been delivered, and comes out of the store room as it goes."""
    rounds = list(TableOrder.objects.filter(table_number=number, status=TableOrder.OPEN))
    for order in rounds:
        # One at a time and through `deliver`, not a bulk `.update()`: a queryset update never loads a row, so
        # it can mark ten rounds delivered without touching a single ingredient. That is exactly the silent
        # drift this is here to avoid.
        deliver(order, who=_who(request))
    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({'closed': len(rounds), 'table': number})
    return redirect(_back(request))
