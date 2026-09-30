"""The screens. Spanish only, like the rest of the floor console: one audience, and it is the staff.

Layout follows Soft Restaurant so somebody who has worked a Mexican bar lands on something they already know:
PIN keypad -> table map with zone tabs and a function bar -> order screen with the check on the left, category
and product buttons on the right and the function keys along the bottom.
"""

import json
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import InventoryChange, InventoryItem, MenuCategory, MenuItem, MenuItemIngredient

from . import services
from .api import cuenta_json, table_states
from .auth import clear_failures, current_staff, locked_out, pos_required, record_failure, sign_in_staff, sign_out_staff
from .models import (CashMove, Check, CheckLine, Comanda, ItemCost, Modifier, ModifierGroup, Payment, Printer,
                     PrintJob, Purchase, Shift, Staff, StockCount, StockCountLine, Supplier, Table, Zone)
from .services import PosError
from .views_pay import pay_link


def _cents(value):
    try:
        return round(Decimal(str(value or '0').replace(',', '').replace('$', '').strip() or '0') * 100)
    except InvalidOperation:
        raise PosError('Monto no válido.')


def _dec(value):
    try:
        return Decimal(str(value or '0').replace(',', '.').strip() or '0')
    except InvalidOperation:
        raise PosError('Cantidad no válida.')


def _ctx(request, **kw):
    kw.setdefault('staff', getattr(request, 'staff', None))
    kw.setdefault('shift', Shift.current())
    return kw


# ---------------------------------------------------------------- sign in

def entrar(request):
    """The PIN keypad, and the only way in."""
    error = ''
    nxt = request.GET.get('next') or request.POST.get('next') or '/pos/'
    if not nxt.startswith(('/pos', '/mesas', '/checkin', '/scan')):
        nxt = '/pos/'
    if request.method == 'POST':
        wait = locked_out(request)
        if wait:
            error = f'Demasiados intentos. Espera {wait} min.'
        else:
            staff = Staff.by_pin(request.POST.get('pin'))
            if staff:
                clear_failures(request)
                sign_in_staff(request, staff)
                return redirect(nxt)
            record_failure(request)
            error = 'PIN incorrecto.'
    return render(request, 'pos/entrar.html', {'error': error, 'next': nxt,
                                               'first_run': not Staff.objects.exists()})


def salir(request):
    sign_out_staff(request)
    return redirect('/pos/entrar/')


# ---------------------------------------------------------------- map

@pos_required
def mapa(request):
    zones = list(Zone.objects.all())
    return render(request, 'pos/mapa.html', _ctx(
        request, zones=zones, state=table_states(request.staff), denied=request.GET.get('denied'),
        show=services.current_show()))


@pos_required
def mesa(request, table_id):
    """Tapping a table: its open check, a choice if it has been divided, or a new one."""
    table = get_object_or_404(Table, pk=table_id, active=True)
    checks = [c for c in Check.objects.filter(table=table, status=Check.OPEN).select_related('waiter').order_by('folio')
              if request.staff.may_open(table, c)]
    if not checks and not request.staff.may_open(table):
        return redirect('/pos/?denied=mesa')
    if not checks and Check.objects.filter(table=table, status=Check.OPEN).exists():
        return redirect('/pos/?denied=mesa')
    if request.method == 'POST' and request.POST.get('new'):
        cuenta = Check.objects.create(folio=services.next_folio(), table=table, waiter=request.staff,
                                      guests=int(request.POST.get('guests') or 1), event=services.current_show())
        return redirect(f'/pos/cuenta/{cuenta.id}/')
    if not checks:
        cuenta = services.open_check(table=table, waiter=request.staff, guests=request.GET.get('guests') or 1)
        return redirect(f'/pos/cuenta/{cuenta.id}/')
    if len(checks) == 1:
        return redirect(f'/pos/cuenta/{checks[0].id}/')
    return render(request, 'pos/elegir.html', _ctx(request, table=table, checks=checks))


@pos_required
@require_POST
def mesa_nueva(request):
    """Anyone on the floor can put a table on the map (2026-09-28): the bar carries one in mid-service."""
    zone = Zone.objects.filter(pk=request.POST.get('zone')).first() or Zone.objects.order_by('sort_order').first() \
        or Zone.objects.create(name='Salón')
    try:
        number = int(request.POST.get('number') or 0)
    except ValueError:
        number = 0
    number = number or (Table.objects.order_by('-number').values_list('number', flat=True).first() or 0) + 1
    if not 1 <= number <= 999 or Table.objects.filter(number=number, active=True).exists():
        return redirect('/pos/?denied=numero')
    table = Table.objects.filter(number=number).first()
    taken = [(t.x, t.y) for t in Table.objects.filter(zone=zone, active=True)]
    spot = next(((x, y) for y in range(6, 90, 20) for x in range(4, 90, 16)
                 if all(abs(x - tx) > 10 or abs(y - ty) > 14 for tx, ty in taken)), (80, 80))
    if table:  # an archived number comes back
        table.zone, table.active, table.x, table.y = zone, True, spot[0], spot[1]
        table.name = request.POST.get('name', '')[:40]
        table.save()
    else:
        table = Table.objects.create(zone=zone, number=number, name=request.POST.get('name', '')[:40],
                                     x=spot[0], y=spot[1], w=12, h=15)
    if request.staff.role == Staff.MESERO and request.staff.tables.exists():
        request.staff.tables.add(table)
    return redirect(f'/pos/mesa/{table.pk}/')


@pos_required
@require_POST
def rapida(request):
    """A check with no table: the bar, somebody standing, a takeaway."""
    label = (request.POST.get('label') or 'Barra').strip()[:60]
    cuenta = Check.objects.create(folio=services.next_folio(), label=label, waiter=request.staff,
                                  event=services.current_show())
    return redirect(f'/pos/cuenta/{cuenta.id}/')


# ---------------------------------------------------------------- the order screen

def menu_payload():
    groups = {}
    for g in ModifierGroup.objects.prefetch_related('options', 'items'):
        for item in g.items.all():
            groups.setdefault(item.id, []).append({
                'id': g.id, 'name': g.name, 'min': g.min_select, 'max': g.max_select,
                'options': [{'id': o.id, 'name': o.name, 'price': o.price_cents} for o in g.options.all() if o.active]})
    cats = []
    for c in MenuCategory.objects.filter(active=True).prefetch_related('items'):
        items = [{'id': i.id, 'name': i.label('es'), 'price': i.price_cents, 'groups': groups.get(i.id, [])}
                 for i in c.items.all() if i.available]
        if items:
            cats.append({'id': c.id, 'name': c.label('es'), 'items': items})
    return cats


@pos_required
def cuenta(request, cuenta_id):
    cuenta = get_object_or_404(Check, pk=cuenta_id)
    from .api import claim

    if claim(request.staff, cuenta):
        return redirect('/pos/?denied=mesa')
    cuenta.refresh_from_db()
    tables = [{'id': t.id, 'label': t.label, 'zone': t.zone.name} for t in Table.objects.filter(active=True).select_related('zone')]
    others = [{'id': c.id, 'label': f'{c.folio} · {c.where}'} for c in
              Check.objects.filter(status=Check.OPEN).exclude(pk=cuenta.pk).select_related('table', 'waiter')
              if request.staff.may_open(c.table, c)]
    from api.tables_views import qr_svg

    return render(request, 'pos/cuenta.html', _ctx(
        request, cuenta=cuenta, pay_qr=qr_svg(pay_link(cuenta)),
        boot={'cuentaId': cuenta.id, 'cuenta': cuenta_json(cuenta), 'menu': menu_payload(), 'tables': tables, 'others': others,
              'staff': {'name': request.staff.name, 'manager': request.staff.is_manager,
                        'cashier': True},
              'shiftOpen': Shift.current() is not None,
              'payUrl': pay_link(cuenta)}))


# ---------------------------------------------------------------- printing (browser fallback)

@pos_required
def imprimir(request, job_id):
    job = get_object_or_404(PrintJob, pk=job_id)
    if request.method == 'POST' or request.GET.get('done'):
        PrintJob.objects.filter(pk=job.pk).update(status=PrintJob.DONE, done_at=timezone.now())
    return render(request, 'pos/imprimir.html', {'job': job, 'auto': request.GET.get('auto')})


@pos_required
def pendientes(request):
    """Tickets waiting for a browser print because no printer of their kind is set up."""
    jobs = PrintJob.objects.filter(printer__isnull=True, status=PrintJob.QUEUED,
                                   created_at__gte=timezone.now() - timedelta(hours=12)).order_by('-created_at')
    return render(request, 'pos/pendientes.html', _ctx(request, jobs=jobs[:60]))


# ---------------------------------------------------------------- bar screen

@pos_required
def barra(request):
    """What the bar has to make, oldest first. A tablet at the bar can live on this page instead of a printer."""
    if request.method == 'POST':
        Comanda.objects.filter(pk=request.POST.get('comanda')).update(
            done_at=None if request.POST.get('undo') else timezone.now())
        return redirect('/pos/barra/')
    since = services.service_start()
    pending = (Comanda.objects.filter(created_at__gte=since, done_at__isnull=True)
               .select_related('cuenta__table', 'created_by').prefetch_related('lines').order_by('created_at'))
    done = (Comanda.objects.filter(created_at__gte=since, done_at__isnull=False)
            .select_related('cuenta__table').order_by('-done_at')[:8])
    now = timezone.now()
    rows = [{'c': c, 'minutes': int((now - c.created_at).total_seconds() // 60),
             'lines': [l for l in c.lines.all() if not l.voided_at]} for c in pending]
    return render(request, 'pos/barra.html', _ctx(request, rows=rows, done=done))


# ---------------------------------------------------------------- cash

@pos_required(cashier=True)
def caja(request):
    shift = Shift.current()
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'open':
                services.open_shift(request.staff, _cents(request.POST.get('opening')))
            elif action in ('in', 'out'):
                services.cash_move(shift, CashMove.IN if action == 'in' else CashMove.OUT,
                                   _cents(request.POST.get('amount')), request.POST.get('reason', ''), request.staff)
            elif action == 'close':
                if Check.objects.filter(status=Check.OPEN, payments__status=Payment.PAID).exists() and \
                        not request.POST.get('force'):
                    raise PosError('Hay cuentas abiertas con pagos parciales. Ciérralas o confirma el corte.')
                closed = services.close_shift(shift, request.staff, _cents(request.POST.get('counted_cash')),
                                              _cents(request.POST.get('counted_card')) if request.POST.get('counted_card') else None,
                                              request.POST.get('note', ''))
                return redirect(f'/pos/caja/{closed.id}/?print=1')
            return redirect('/pos/caja/')
        except PosError as exc:
            error = str(exc)
    history = Shift.objects.filter(status=Shift.CLOSED).select_related('opened_by', 'closed_by')[:15]
    return render(request, 'pos/caja.html', _ctx(
        request, summary=services.shift_summary(shift) if shift else None, history=history, error=error,
        open_checks=Check.objects.filter(status=Check.OPEN).select_related('table').prefetch_related('lines', 'payments')))


@pos_required(cashier=True)
def corte(request, shift_id):
    shift = get_object_or_404(Shift, pk=shift_id)
    summary = services.shift_summary(shift)
    job = PrintJob.objects.filter(title='Corte de caja', created_at__gte=shift.closed_at or shift.opened_at).first() \
        if request.GET.get('print') else None
    return render(request, 'pos/corte.html', _ctx(request, s=summary, job=job))


# ---------------------------------------------------------------- inventory

@pos_required
def inventario(request):
    error = ''
    if request.method == 'POST':
        try:
            item = get_object_or_404(InventoryItem, pk=request.POST.get('item'))
            action = request.POST.get('action')
            with transaction.atomic():
                if action == 'set':
                    target = _dec(request.POST.get('quantity'))
                    if target < 0 or target > 100000:
                        raise PosError('Cantidad no válida.')
                    services._move_stock(item.pk, target - item.quantity, 'ajuste', request.staff.name)
                elif action in ('plus', 'minus'):
                    services._move_stock(item.pk, Decimal(1 if action == 'plus' else -1), 'ajuste', request.staff.name)
                elif action == 'waste':
                    services.record_waste(item, _dec(request.POST.get('quantity')), request.POST.get('reason') or 'merma',
                                          request.staff)
            return redirect(f'/pos/inventario/?area={request.POST.get("area", "")}#i{item.pk}')
        except PosError as exc:
            error = str(exc)
    area = request.GET.get('area') or ''
    items = InventoryItem.objects.filter(active=True)
    if area:
        items = items.filter(area=area)
    costs = {c.item_id: c.unit_cost_cents for c in ItemCost.objects.all()}
    rows = sorted([{'i': i, 'cost': costs.get(i.pk, 0),
                    'value': int(costs.get(i.pk, 0) * i.quantity)} for i in items],
                  key=lambda r: (not r['i'].low, r['i'].area, r['i'].name))
    return render(request, 'pos/inventario.html', _ctx(
        request, rows=rows, area=area, areas=InventoryItem.AREAS, error=error,
        total_value=sum(r['value'] for r in rows),
        history=InventoryChange.objects.select_related('item')[:40]))


@pos_required(manager=True)
def insumo(request, item_id=None):
    """Create or edit a count-sheet item."""
    item = get_object_or_404(InventoryItem, pk=item_id) if item_id else InventoryItem()
    if request.method == 'POST':
        item.name = (request.POST.get('name') or '').strip()[:120] or item.name
        item.unit = request.POST.get('unit', '')[:30]
        item.area = request.POST.get('area') or InventoryItem.BAR
        item.par = _dec(request.POST.get('par'))
        item.active = request.POST.get('active', 'on') == 'on'
        if not item.pk:
            item.quantity = _dec(request.POST.get('quantity'))
        if item.name:
            item.save()
        return redirect('/pos/inventario/')
    return render(request, 'pos/insumo.html', _ctx(request, item=item, areas=InventoryItem.AREAS))


@pos_required
def compras(request):
    error = ''
    if request.method == 'POST':
        try:
            supplier = None
            if request.POST.get('supplier_new'):
                supplier = Supplier.objects.create(name=request.POST['supplier_new'].strip()[:120])
            elif request.POST.get('supplier'):
                supplier = Supplier.objects.filter(pk=request.POST['supplier']).first()
            lines = []
            for key in request.POST:
                if key.startswith('q_') and request.POST[key].strip():
                    item = InventoryItem.objects.filter(pk=key[2:]).first()
                    if item:
                        lines.append((item, _dec(request.POST[key]), _cents(request.POST.get('c_' + key[2:]))))
            services.record_purchase(supplier=supplier, lines=lines, reference=request.POST.get('reference', ''),
                                     note=request.POST.get('note', ''), by=request.staff)
            return redirect('/pos/inventario/compras/?ok=1')
        except PosError as exc:
            error = str(exc)
    return render(request, 'pos/compras.html', _ctx(
        request, error=error, ok=request.GET.get('ok'), suppliers=Supplier.objects.filter(active=True),
        items=InventoryItem.objects.filter(active=True),
        purchases=Purchase.objects.select_related('supplier', 'by').prefetch_related('lines__item')[:20]))


@pos_required
def conteo(request, count_id=None):
    """Inventario físico: a sheet of everything, typed as counted, applied in one go."""
    if count_id is None:
        if request.method == 'POST':
            count = services.start_count(request.staff)
            return redirect(f'/pos/inventario/conteo/{count.id}/')
        return render(request, 'pos/conteos.html', _ctx(request, counts=StockCount.objects.select_related('by')[:20]))
    count = get_object_or_404(StockCount, pk=count_id)
    error = ''
    if request.method == 'POST' and count.status == StockCount.OPEN:
        try:
            for line in count.lines.all():
                raw = request.POST.get(f'n_{line.pk}', '').strip()
                line.counted = _dec(raw) if raw else None
                line.save(update_fields=['counted'])
            if request.POST.get('apply'):
                services.apply_count(count, request.staff)
            return redirect(f'/pos/inventario/conteo/{count.id}/')
        except PosError as exc:
            error = str(exc)
    lines = count.lines.select_related('item').order_by('item__area', 'item__name')
    return render(request, 'pos/conteo.html', _ctx(request, count=count, lines=lines, error=error))


# ---------------------------------------------------------------- catalog

@pos_required(manager=True)
def productos(request):
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'category':
                name = request.POST.get('name', '').strip()
                if name:
                    MenuCategory.objects.create(name=name[:80], name_es=name[:80],
                                                sort_order=MenuCategory.objects.count())
            elif action == 'toggle':
                item = get_object_or_404(MenuItem, pk=request.POST.get('item'))
                item.available = not item.available
                item.save(update_fields=['available'])
            elif action == 'cat_toggle':
                cat = get_object_or_404(MenuCategory, pk=request.POST.get('category'))
                cat.active = not cat.active
                cat.save(update_fields=['active'])
            return redirect('/pos/productos/')
        except PosError as exc:
            error = str(exc)
    cats = MenuCategory.objects.prefetch_related('items__ingredients__inventory_item', 'items__modifier_groups')
    return render(request, 'pos/productos.html', _ctx(request, cats=cats, error=error,
                                                     groups=ModifierGroup.objects.prefetch_related('options', 'items')))


@pos_required(manager=True)
def producto(request, item_id=None):
    item = get_object_or_404(MenuItem, pk=item_id) if item_id else MenuItem(
        category_id=request.GET.get('category') or (MenuCategory.objects.first().pk if MenuCategory.objects.exists() else None))
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        try:
            if action == 'save':
                name = request.POST.get('name', '').strip()
                if not name:
                    raise PosError('Ponle nombre.')
                # A second product with the same name in the same category shows up twice on the menu and splits
                # its sales between two rows (it happened with Michelob Ultra, 2026-09-29), so point at the one
                # that exists instead.
                twin = MenuItem.objects.filter(category_id=request.POST.get('category'),
                                               name__iexact=name[:120]).exclude(pk=item.pk).first()
                if twin:
                    raise PosError(f'Ya existe «{twin.name}» en esa categoría. Ábrelo desde Productos y edítalo.')
                item.name = name[:120]
                # The console is Spanish, so the Spanish name moves with it; the customer menu reads name_es.
                item.name_es = name[:120]
                item.description = item.description_es = request.POST.get('description', '')[:300]
                item.price_cents = _cents(request.POST.get('price'))
                item.category = get_object_or_404(MenuCategory, pk=request.POST.get('category'))
                item.available = request.POST.get('available') == 'on'
                item.save()
                item.modifier_groups.set(ModifierGroup.objects.filter(pk__in=request.POST.getlist('groups')))
                return redirect(f'/pos/productos/{item.pk}/?ok=1')
            if action == 'ingredient' and item.pk:
                inv = get_object_or_404(InventoryItem, pk=request.POST.get('inventory'))
                qty = _dec(request.POST.get('quantity'))
                if qty <= 0:
                    raise PosError('Cantidad no válida.')
                MenuItemIngredient.objects.update_or_create(menu_item=item, inventory_item=inv, defaults={'quantity': qty})
            if action == 'unlink' and item.pk:
                MenuItemIngredient.objects.filter(pk=request.POST.get('ingredient'), menu_item=item).delete()
            return redirect(f'/pos/productos/{item.pk}/')
        except PosError as exc:
            error = str(exc)
    costs = {c.item_id: c.unit_cost_cents for c in ItemCost.objects.all()}
    ingredients = list(item.ingredients.select_related('inventory_item')) if item.pk else []
    cost = sum(int(costs.get(i.inventory_item_id, 0) * i.quantity) for i in ingredients)
    return render(request, 'pos/producto.html', _ctx(
        request, item=item, error=error, ok=request.GET.get('ok'), categories=MenuCategory.objects.all(),
        groups=ModifierGroup.objects.all(), chosen={g.pk for g in item.modifier_groups.all()} if item.pk else set(),
        ingredients=ingredients, inventory=InventoryItem.objects.filter(active=True), cost=cost,
        margin=(item.price_cents - cost) if item.pk and cost else None))


@pos_required(manager=True)
def modificadores(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'group':
            name = request.POST.get('name', '').strip()
            if name:
                ModifierGroup.objects.create(name=name[:60], min_select=int(request.POST.get('min') or 0),
                                             max_select=max(1, int(request.POST.get('max') or 1)))
        elif action == 'option':
            group = get_object_or_404(ModifierGroup, pk=request.POST.get('group'))
            name = request.POST.get('name', '').strip()
            if name:
                Modifier.objects.create(group=group, name=name[:60], price_cents=_cents(request.POST.get('price')))
        elif action == 'delete_option':
            Modifier.objects.filter(pk=request.POST.get('option')).update(active=False)
        elif action == 'delete_group':
            ModifierGroup.objects.filter(pk=request.POST.get('group')).delete()
        return redirect('/pos/productos/modificadores/')
    return render(request, 'pos/modificadores.html', _ctx(request, groups=ModifierGroup.objects.prefetch_related('options', 'items')))


# ---------------------------------------------------------------- reports

def _range(request):
    today = timezone.localdate()
    try:
        start = datetime.strptime(request.GET.get('desde', ''), '%Y-%m-%d').date()
    except ValueError:
        start = today
    try:
        end = datetime.strptime(request.GET.get('hasta', ''), '%Y-%m-%d').date()
    except ValueError:
        end = start
    # Service days run 6am to 6am, so a show that ends at 1am belongs to the day it started.
    tz = timezone.get_current_timezone()
    return start, end, (timezone.make_aware(datetime.combine(start, time(6)), tz),
                        timezone.make_aware(datetime.combine(end + timedelta(days=1), time(6)), tz))


@pos_required(manager=True)
def reportes(request):
    start, end, (since, until) = _range(request)
    payments = Payment.objects.filter(status=Payment.PAID, created_at__gte=since, created_at__lt=until)
    checks = Check.objects.filter(status=Check.PAID, closed_at__gte=since, closed_at__lt=until)
    lines = CheckLine.objects.filter(cuenta__in=checks, voided_at__isnull=True)
    by_product = {}
    for l in lines.select_related('menu_item__category'):
        key = l.name
        row = by_product.setdefault(key, {'name': l.name, 'qty': 0, 'cents': 0,
                                          'category': l.menu_item.category.label('es') if l.menu_item else '-'})
        row['qty'] += l.quantity
        row['cents'] += l.total_cents
    by_category = {}
    for row in by_product.values():
        c = by_category.setdefault(row['category'], {'name': row['category'], 'qty': 0, 'cents': 0})
        c['qty'] += row['qty']
        c['cents'] += row['cents']
    by_method = {code: {'label': label, 'amount': 0, 'tips': 0, 'count': 0} for code, label in Payment.METHODS}
    for p in payments:
        by_method[p.method]['amount'] += p.amount_cents
        by_method[p.method]['tips'] += p.tip_cents
        by_method[p.method]['count'] += 1
    by_waiter = {}
    for c in checks.select_related('waiter').prefetch_related('lines', 'payments'):
        name = c.waiter.name if c.waiter else 'QR / sin mesero'
        w = by_waiter.setdefault(name, {'name': name, 'checks': 0, 'cents': 0, 'tips': 0, 'guests': 0})
        w['checks'] += 1
        w['cents'] += c.total_cents
        w['tips'] += c.tips_cents
        w['guests'] += c.guests
    voids = CheckLine.objects.filter(voided_at__gte=since, voided_at__lt=until).select_related('cuenta', 'voided_by')
    discounts = checks.filter(discount_cents__gt=0).select_related('discount_by')
    by_show = {}
    for c in checks.select_related('event').prefetch_related('lines'):
        name = c.event.label('es') if c.event else 'Sin show'
        s = by_show.setdefault(name, {'name': name, 'checks': 0, 'cents': 0})
        s['checks'] += 1
        s['cents'] += c.total_cents
    sales = sum(r['amount'] for k, r in by_method.items() if k != Payment.COURTESY)
    # Theoretical cost of what was sold, from recipes and last purchase costs.
    costs = {c.item_id: c.unit_cost_cents for c in ItemCost.objects.all()}
    cogs = 0
    for l in lines.select_related('menu_item').prefetch_related('menu_item__ingredients'):
        if l.menu_item:
            cogs += sum(int(costs.get(i.inventory_item_id, 0) * i.quantity) for i in l.menu_item.ingredients.all()) * l.quantity
    return render(request, 'pos/reportes.html', _ctx(
        request, start=start, end=end, sales=sales, checks=checks.count(),
        guests=sum(c.guests for c in checks), tips=sum(r['tips'] for r in by_method.values()),
        methods=[r for r in by_method.values() if r['count']],
        products=sorted(by_product.values(), key=lambda r: -r['cents']),
        categories=sorted(by_category.values(), key=lambda r: -r['cents']),
        waiters=sorted(by_waiter.values(), key=lambda r: -r['cents']),
        shows=sorted(by_show.values(), key=lambda r: -r['cents']),
        voids=voids, void_cents=sum(v.each_cents * v.quantity for v in voids),
        discounts=discounts, discount_cents=sum(c.discount_cents for c in discounts),
        cogs=cogs, average=(sales // checks.count()) if checks.count() else 0))


# ---------------------------------------------------------------- setup (manager)

@pos_required(manager=True)
def personal(request):
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        pin = (request.POST.get('pin') or '').strip()
        try:
            if action in ('add', 'pin') and not (pin.isdigit() and 4 <= len(pin) <= 6):
                raise PosError('El PIN debe ser de 4 a 6 números.')
            if action in ('add', 'pin') and Staff.by_pin(pin):
                raise PosError('Ese PIN ya lo usa otra persona. Elige otro.')
            if action == 'add':
                name = request.POST.get('name', '').strip()
                if not name:
                    raise PosError('Escribe el nombre.')
                s = Staff(name=name[:80], role=request.POST.get('role') or Staff.MESERO)
                s.set_pin(pin)
                s.save()
            elif action == 'pin':
                s = get_object_or_404(Staff, pk=request.POST.get('staff'))
                s.set_pin(pin)
                s.save(update_fields=['pin_hash'])
            elif action == 'role':
                s = get_object_or_404(Staff, pk=request.POST.get('staff'))
                if s.pk == request.staff.pk and request.POST.get('role') != Staff.GERENTE:
                    raise PosError('No te puedes quitar el rol de gerente a ti mismo.')
                s.role = request.POST.get('role') or s.role
                s.save(update_fields=['role'])
            elif action == 'section':
                s = get_object_or_404(Staff, pk=request.POST.get('staff'))
                s.tables.set(Table.objects.filter(number__in=_numbers(request.POST.get('section', ''))))
            elif action == 'toggle':
                s = get_object_or_404(Staff, pk=request.POST.get('staff'))
                if s.pk == request.staff.pk:
                    raise PosError('No te puedes dar de baja a ti mismo.')
                s.active = not s.active
                s.save(update_fields=['active'])
            return redirect('/pos/personal/')
        except PosError as exc:
            error = str(exc)
    people = [{'s': s, 'section': _ranges(sorted(s.tables.values_list('number', flat=True)))}
              for s in Staff.objects.prefetch_related('tables')]
    return render(request, 'pos/personal.html', _ctx(request, people=people, roles=Staff.ROLES, error=error))


def _numbers(text):
    """'1-6, 9' -> {1,2,3,4,5,6,9}."""
    out = set()
    for part in str(text).replace(' ', '').split(','):
        if '-' in part:
            a, _, b = part.partition('-')
            if a.isdigit() and b.isdigit() and int(b) - int(a) < 300:
                out.update(range(int(a), int(b) + 1))
        elif part.isdigit():
            out.add(int(part))
    return out


def _ranges(numbers):
    """[1,2,3,6] -> '1-3, 6'."""
    out, start, prev = [], None, None
    for n in numbers + [None]:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f'{start}-{prev}' if prev != start else str(start))
            start = prev = n
    return ', '.join(out)


@pos_required(manager=True)
def configurar_mesas(request):
    if request.method == 'POST':
        if request.content_type == 'application/json':
            for row in json.loads(request.body or b'[]'):
                Table.objects.filter(pk=row.get('id')).update(
                    x=max(0, min(95, float(row['x']))), y=max(0, min(95, float(row['y']))),
                    w=max(4, min(40, float(row['w']))), h=max(4, min(40, float(row['h']))))
            return JsonResponse({'ok': True})
        action = request.POST.get('action')
        if action == 'zone':
            name = request.POST.get('name', '').strip()
            if name:
                Zone.objects.create(name=name[:60], sort_order=Zone.objects.count())
        elif action == 'table':
            zone = get_object_or_404(Zone, pk=request.POST.get('zone'))
            number = int(request.POST.get('number') or 0) or ((Table.objects.order_by('-number').values_list('number', flat=True).first() or 0) + 1)
            if Table.objects.filter(number=number).exists():
                messages.error(request, f'Ya existe la mesa {number}.')
            else:
                Table.objects.create(zone=zone, number=number, name=request.POST.get('name', '')[:40],
                                     shape=request.POST.get('shape') or Table.SQUARE,
                                     seats=int(request.POST.get('seats') or 4))
        elif action == 'edit':
            t = get_object_or_404(Table, pk=request.POST.get('table'))
            t.name = request.POST.get('name', '')[:40]
            t.shape = request.POST.get('shape') or t.shape
            t.seats = int(request.POST.get('seats') or t.seats)
            t.zone = get_object_or_404(Zone, pk=request.POST.get('zone') or t.zone_id)
            t.active = request.POST.get('active') == 'on'
            t.save()
        return redirect('/pos/mesas/')
    return render(request, 'pos/mesas.html', _ctx(
        request, zones=Zone.objects.prefetch_related('tables'),
        tables=Table.objects.select_related('zone'), shapes=Table.SHAPES,
        tables_json=[{'id': t.pk, 'n': str(t.number), 'z': t.zone_id, 'x': t.x, 'y': t.y, 'w': t.w, 'h': t.h,
                      's': t.shape} for t in Table.objects.filter(active=True)]))


@pos_required(manager=True)
def impresoras(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            Printer.objects.create(name=request.POST.get('name', 'Impresora')[:60],
                                   role=request.POST.get('role') or Printer.COMANDA,
                                   protocol=request.POST.get('protocol') or Printer.EPSON)
        elif action == 'toggle':
            p = get_object_or_404(Printer, pk=request.POST.get('printer'))
            p.active = not p.active
            p.save(update_fields=['active'])
        elif action == 'test':
            p = get_object_or_404(Printer, pk=request.POST.get('printer'))
            PrintJob.objects.create(role=p.role, printer=p, title='Prueba',
                                    lines=['IGUANA COMEDY', 'Prueba de impresión', timezone.localtime().strftime('%d/%m/%Y %H:%M'), '-' * 42])
        return redirect('/pos/impresoras/')
    base = request.build_absolute_uri('/').rstrip('/')
    return render(request, 'pos/impresoras.html', _ctx(
        request, printers=[{'p': p, 'url': f'{base}/pos/print/{p.token}/'} for p in Printer.objects.all()]))
