"""Everything that changes a check, a shift or the stock, in one place.

Views call these; nothing else writes to a Check. Every function that moves money or stock takes a row lock on
the check first (`select_for_update(of=('self',))`: the check's table and waiter are nullable FKs, and Postgres
refuses FOR UPDATE across a nullable outer join, which SQLite would silently accept).
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from catalog.models import InventoryChange, InventoryItem, MenuItem

from .models import (CashMove, Check, CheckLine, Comanda, ItemCost, Modifier, Payment, Printer, Purchase,
                     PurchaseLine, Shift, Staff, StockCount, StockCountLine, Table, Zone)

log = logging.getLogger(__name__)

MAX_QTY = 50


class PosError(Exception):
    """A refusal the floor should read, in Spanish."""


def money(cents):
    return f'${cents / 100:,.2f}'


def service_start(now=None):
    from api.tables_views import service_start as start

    return start(now)


def current_show(now=None):
    from api.tables_views import current_show as show

    return show(now)


def _locked(cuenta_id):
    return Check.objects.select_for_update(of=('self',)).get(pk=cuenta_id)


def next_folio():
    return (Check.objects.aggregate(n=Max('folio'))['n'] or 0) + 1


# ---------------------------------------------------------------- checks

def open_check(*, table=None, label='', waiter=None, guests=1):
    """The table's open check, or a new one. Two waiters tapping the same free table get the same check."""
    with transaction.atomic():
        if table is not None:
            Table.objects.select_for_update().filter(pk=table.pk).first()
            existing = Check.objects.filter(table=table, status=Check.OPEN).first()
            if existing:
                return existing
        return Check.objects.create(folio=next_folio(), table=table, label=label[:60], waiter=waiter,
                                    guests=max(1, int(guests or 1)), event=current_show())


def add_line(cuenta, menu_item, *, quantity=1, modifier_ids=(), note='', by=None, from_customer=False):
    quantity = int(quantity or 1)
    if not 1 <= quantity <= MAX_QTY:
        raise PosError('Cantidad no válida.')
    mods = []
    if modifier_ids:
        allowed = {m.id: m for m in Modifier.objects.filter(pk__in=modifier_ids, active=True,
                                                             group__items=menu_item)}
        mods = [{'name': allowed[i].name, 'priceCents': allowed[i].price_cents}
                for i in modifier_ids if i in allowed]
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        if cuenta.status != Check.OPEN:
            raise PosError('La cuenta ya está cerrada.')
        return CheckLine.objects.create(cuenta=cuenta, menu_item=menu_item, name=menu_item.label('es'),
                                        unit_price_cents=menu_item.price_cents, quantity=quantity,
                                        modifiers=mods, note=note[:200], created_by=by,
                                        from_customer=from_customer)


def change_quantity(line, quantity):
    """Only a line that has not gone to the bar. A sent line is changed by voiding it, which leaves a trace."""
    quantity = int(quantity)
    with transaction.atomic():
        line = CheckLine.objects.select_for_update(of=('self',)).get(pk=line.pk)
        if line.sent_at or line.voided_at:
            raise PosError('Ya se envió a barra: para quitarlo, cancélalo.')
        if quantity <= 0:
            line.delete()
            return None
        if quantity > MAX_QTY:
            raise PosError('Cantidad no válida.')
        line.quantity = quantity
        line.save(update_fields=['quantity'])
        return line


def set_line_note(line, note):
    CheckLine.objects.filter(pk=line.pk, sent_at__isnull=True).update(note=note[:200])


def _apply_line_stock(line, who):
    """Take a sent line's recipe out of the count sheet, once."""
    if line.stock_applied_at or not line.menu_item_id:
        return
    for ing in line.menu_item.ingredients.select_related('inventory_item'):
        _move_stock(ing.inventory_item_id, -(ing.quantity * line.quantity), 'venta', who)
    line.stock_applied_at = timezone.now()
    line.save(update_fields=['stock_applied_at'])


def _return_line_stock(line, who):
    if not line.stock_applied_at or line.stock_returned_at or not line.menu_item_id:
        return
    for ing in line.menu_item.ingredients.select_related('inventory_item'):
        _move_stock(ing.inventory_item_id, ing.quantity * line.quantity, 'devuelto (no se preparó)', who)
    line.stock_returned_at = timezone.now()
    line.save(update_fields=['stock_returned_at'])


def _move_stock(item_id, delta, note, who):
    item = InventoryItem.objects.select_for_update().get(pk=item_id)
    after = max(Decimal(item.quantity) + Decimal(delta), Decimal(0))
    real = after - Decimal(item.quantity)
    item.quantity = after
    item.save(update_fields=['quantity', 'updated_at'])
    InventoryChange.objects.create(item=item, delta=real, quantity_after=after, note=note[:200], who=who[:80])


def send(cuenta, by=None):
    """ENVIAR: the unsent lines become a comanda, leave the stock and print at the bar. Returns the comanda."""
    who = by.name if by else 'cliente'
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        lines = list(cuenta.lines.filter(sent_at__isnull=True, voided_at__isnull=True).select_related('menu_item'))
        if not lines:
            return None
        start = service_start()
        number = (Comanda.objects.filter(created_at__gte=start).aggregate(n=Max('number'))['n'] or 0) + 1
        comanda = Comanda.objects.create(cuenta=cuenta, number=number, created_by=by)
        now = timezone.now()
        for line in lines:
            line.sent_at = now
            line.comanda = comanda
            line.save(update_fields=['sent_at', 'comanda'])
            _apply_line_stock(line, who)
        from .printing import comanda_ticket, queue

        queue(Printer.COMANDA, f'Comanda {number}', comanda_ticket(cuenta, comanda, lines, by))
        return comanda


def void_line(line, *, reason, note='', by=None, manager=None):
    """Cancel a line. A sent one needs a manager, and says whether the drink was made."""
    if reason not in dict(CheckLine.VOID_REASONS):
        reason = CheckLine.WASTED
    with transaction.atomic():
        line = CheckLine.objects.select_for_update(of=('self',)).get(pk=line.pk)
        if line.voided_at:
            return line
        if not line.sent_at:
            line.delete()
            return None
        if manager is None or not manager.is_manager:
            raise PosError('Cancelar algo ya enviado requiere autorización del gerente.')
        line.voided_at = timezone.now()
        line.void_reason = reason
        line.void_note = note[:200]
        line.voided_by = manager
        line.save(update_fields=['voided_at', 'void_reason', 'void_note', 'voided_by'])
        # Made and binned stays out of stock; never made, or typed by mistake, goes back.
        if reason in (CheckLine.NOT_MADE, CheckLine.MISTAKE):
            _return_line_stock(line, manager.name)
        return line


def set_discount(cuenta, *, percent=None, cents=None, reason='', manager=None):
    if manager is None or not manager.is_manager:
        raise PosError('Un descuento requiere autorización del gerente.')
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        if cuenta.status != Check.OPEN:
            raise PosError('La cuenta ya está cerrada.')
        if percent is not None:
            percent = max(0, min(100, int(percent)))
            amount = round(cuenta.subtotal_cents * percent / 100)
            label = f'{percent}%'
        else:
            amount = max(0, min(int(cents or 0), cuenta.subtotal_cents))
            label = money(amount)
        cuenta.discount_cents = amount
        cuenta.discount_reason = (f'{label} {reason}'.strip())[:120] if amount else ''
        cuenta.discount_by = manager if amount else None
        cuenta.save(update_fields=['discount_cents', 'discount_reason', 'discount_by'])
        return cuenta


def print_bill(cuenta, by=None):
    from .printing import bill_ticket, queue

    cuenta = Check.objects.get(pk=cuenta.pk)
    Check.objects.filter(pk=cuenta.pk).update(bill_printed_at=timezone.now())
    return queue(Printer.TICKET, f'Cuenta {cuenta.folio}', bill_ticket(cuenta))


def move(cuenta, table, by=None):
    """CAMBIAR MESA. Onto a free table it moves; onto a table with an open check it joins that check."""
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        if cuenta.status != Check.OPEN:
            raise PosError('La cuenta ya está cerrada.')
        target = Check.objects.select_for_update(of=('self',)).filter(table=table, status=Check.OPEN).exclude(
            pk=cuenta.pk).first()
        if target is None:
            cuenta.table = table
            cuenta.label = ''
            cuenta.save(update_fields=['table', 'label'])
            return cuenta
        return _merge(cuenta, target)


def join(cuenta, other, by=None):
    """JUNTAR: bring another open check's lines and payments onto this one."""
    with transaction.atomic():
        target = _locked(cuenta.pk)
        source = _locked(other.pk)
        if target.status != Check.OPEN or source.status != Check.OPEN or target.pk == source.pk:
            raise PosError('Solo se juntan dos cuentas abiertas distintas.')
        return _merge(source, target)


def _merge(source, target):
    source.lines.update(cuenta=target)
    source.payments.update(cuenta=target)
    source.comandas.update(cuenta=target)
    target.guests += source.guests
    target.discount_cents += source.discount_cents
    target.save(update_fields=['guests', 'discount_cents'])
    source.status = Check.CANCELLED
    source.cancel_reason = f'Unida a la cuenta {target.folio}'
    source.closed_at = timezone.now()
    source.save(update_fields=['status', 'cancel_reason', 'closed_at'])
    return target


def split(cuenta, line_ids, by=None):
    """DIVIDIR: the chosen lines move to a new check on the same table (a separate bill for that person)."""
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        lines = list(cuenta.lines.filter(pk__in=line_ids, voided_at__isnull=True))
        if not lines or len(lines) == len(cuenta.live_lines()):
            raise PosError('Elige algunos productos, no todos.')
        new = Check.objects.create(folio=next_folio(), table=cuenta.table,
                                   label=(cuenta.label or cuenta.where)[:60] + ' (div.)', waiter=cuenta.waiter,
                                   guests=1, event=cuenta.event)
        CheckLine.objects.filter(pk__in=[l.pk for l in lines]).update(cuenta=new)
        return new


def cancel_check(cuenta, *, reason, manager=None):
    if manager is None or not manager.is_manager:
        raise PosError('Cancelar una cuenta requiere autorización del gerente.')
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        if cuenta.status != Check.OPEN:
            raise PosError('La cuenta ya está cerrada.')
        if cuenta.paid_cents:
            raise PosError('La cuenta ya tiene pagos: cóbrala o devuelve el pago primero.')
        now = timezone.now()
        for line in cuenta.lines.filter(voided_at__isnull=True):
            if line.sent_at:
                line.voided_at = now
                line.void_reason = CheckLine.NOT_MADE
                line.void_note = 'cuenta cancelada'
                line.voided_by = manager
                line.save(update_fields=['voided_at', 'void_reason', 'void_note', 'voided_by'])
                _return_line_stock(line, manager.name)
            else:
                line.delete()
        cuenta.status = Check.CANCELLED
        cuenta.cancel_reason = reason[:200]
        cuenta.cancelled_by = manager
        cuenta.closed_at = now
        cuenta.save(update_fields=['status', 'cancel_reason', 'cancelled_by', 'closed_at'])
        return cuenta


# ---------------------------------------------------------------- payments

def pay(cuenta, *, method, amount_cents, tip_cents=0, received_cents=0, reference='', by=None, manager=None,
        stripe_intent='', stripe_charge=''):
    """COBRAR, one payment. The check closes when nothing is left to pay."""
    if method not in dict(Payment.METHODS):
        raise PosError('Forma de pago no válida.')
    if method == Payment.COURTESY and (manager is None or not manager.is_manager):
        raise PosError('Una cortesía requiere autorización del gerente.')
    amount_cents, tip_cents = int(amount_cents or 0), int(tip_cents or 0)
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        if cuenta.status != Check.OPEN:
            raise PosError('La cuenta ya está cerrada.')
        # Anything still unsent goes to the bar before the money is taken, as Soft Restaurant does.
        if cuenta.unsent:
            send(cuenta, by)
            cuenta = _locked(cuenta.pk)
        due = cuenta.due_cents
        if amount_cents <= 0 or amount_cents > due:
            raise PosError(f'El monto debe estar entre $0.01 y {money(due)}.')
        shift = Shift.current()
        if shift is None and method != Payment.PHONE:
            raise PosError('No hay turno de caja abierto. Abre la caja antes de cobrar.')
        change = 0
        if method == Payment.CASH:
            received_cents = int(received_cents or 0) or amount_cents + tip_cents
            if received_cents < amount_cents + tip_cents:
                raise PosError('El efectivo recibido no alcanza.')
            change = received_cents - amount_cents - tip_cents
        payment = Payment.objects.create(
            cuenta=cuenta, method=method, amount_cents=amount_cents, tip_cents=max(tip_cents, 0),
            received_cents=received_cents if method == Payment.CASH else 0, change_cents=change,
            reference=reference[:80], shift=shift, created_by=manager if method == Payment.COURTESY else by,
            stripe_payment_intent_id=stripe_intent, stripe_charge_id=stripe_charge)
        cuenta = Check.objects.prefetch_related('lines', 'payments').get(pk=cuenta.pk)
        if cuenta.due_cents == 0:
            _close(cuenta, by)
        return payment


def _close(cuenta, by):
    Check.objects.filter(pk=cuenta.pk).update(status=Check.PAID, closed_at=timezone.now())
    from .printing import final_ticket, queue

    cuenta = Check.objects.get(pk=cuenta.pk)
    queue(Printer.TICKET, f'Ticket {cuenta.folio}', final_ticket(cuenta))


def reopen(cuenta, manager):
    if manager is None or not manager.is_manager:
        raise PosError('Reabrir una cuenta requiere autorización del gerente.')
    with transaction.atomic():
        cuenta = _locked(cuenta.pk)
        if cuenta.status != Check.PAID:
            raise PosError('Solo se reabre una cuenta pagada.')
        cuenta.payments.filter(status=Payment.PAID).update(status=Payment.REFUNDED)
        cuenta.status = Check.OPEN
        cuenta.closed_at = None
        cuenta.save(update_fields=['status', 'closed_at'])
        return cuenta


# ---------------------------------------------------------------- the customer's own QR order

def table_for_number(number):
    """The table a customer QR names. A number the map does not have yet is added to the first zone."""
    table = Table.objects.filter(number=number).first()
    if table:
        return table
    zone = Zone.objects.order_by('sort_order').first() or Zone.objects.create(name='Salón')
    return Table.objects.create(zone=zone, number=number, x=5 + (number % 6) * 15, y=70, w=11, h=11)


def customer_order(table_number, quantities, *, note='', name=''):
    """A round from the table's QR lands on that table's check, UNSENT, for the waiter to confirm and send."""
    items = {m.id: m for m in MenuItem.objects.filter(pk__in=list(quantities), available=True,
                                                          category__active=True)}
    if not items:
        raise PosError('Nothing to order.')
    table = table_for_number(int(table_number))
    cuenta = open_check(table=table, label=name[:60])
    made = []
    for item_id, qty in quantities.items():
        if item_id in items and int(qty) > 0:
            made.append(add_line(cuenta, items[item_id], quantity=min(int(qty), MAX_QTY),
                                 note=(f'{name}: ' if name else '') + note[:150], from_customer=True))
    return cuenta, made


# ---------------------------------------------------------------- shifts

def open_shift(by, opening_cents):
    with transaction.atomic():
        if Shift.objects.select_for_update().filter(status=Shift.OPEN).exists():
            raise PosError('Ya hay un turno abierto.')
        return Shift.objects.create(opened_by=by, opening_cash_cents=max(int(opening_cents or 0), 0))


def cash_move(shift, kind, amount_cents, reason, by):
    if shift is None or shift.status != Shift.OPEN:
        raise PosError('No hay turno abierto.')
    if int(amount_cents or 0) <= 0:
        raise PosError('Monto no válido.')
    return CashMove.objects.create(shift=shift, kind=kind, amount_cents=int(amount_cents), reason=reason[:200] or '-',
                                   by=by)


def shift_summary(shift):
    """The corte: what each method took, the tips, and what should be in the drawer."""
    payments = list(shift.payments.filter(status=Payment.PAID).select_related('cuenta'))
    by_method = {code: {'label': label, 'amount': 0, 'tips': 0, 'count': 0} for code, label in Payment.METHODS}
    for p in payments:
        row = by_method[p.method]
        row['amount'] += p.amount_cents
        row['tips'] += p.tip_cents
        row['count'] += 1
    ins = sum(m.amount_cents for m in shift.moves.all() if m.kind == CashMove.IN)
    outs = sum(m.amount_cents for m in shift.moves.all() if m.kind == CashMove.OUT)
    cash = by_method[Payment.CASH]
    expected_cash = shift.opening_cash_cents + cash['amount'] + cash['tips'] + ins - outs
    checks = {p.cuenta_id for p in payments}
    voids = CheckLine.objects.filter(voided_at__gte=shift.opened_at,
                                     voided_at__lte=shift.closed_at or timezone.now()).select_related('voided_by')
    discounts = Check.objects.filter(pk__in=checks, discount_cents__gt=0)
    sales = sum(r['amount'] for c, r in by_method.items() if c != Payment.COURTESY)
    return {
        'shift': shift, 'methods': [r | {'code': c} for c, r in by_method.items()],
        'sales': sales, 'tips': sum(r['tips'] for r in by_method.values()),
        'courtesy': by_method[Payment.COURTESY]['amount'], 'checks': len(checks),
        'ins': ins, 'outs': outs, 'moves': list(shift.moves.select_related('by')),
        'expected_cash': expected_cash,
        'counted_cash': shift.counted_cash_cents,
        'cash_difference': None if shift.counted_cash_cents is None else shift.counted_cash_cents - expected_cash,
        'expected_card': by_method[Payment.CARD]['amount'] + by_method[Payment.CARD]['tips'],
        'counted_card': shift.counted_card_cents,
        'voids': list(voids), 'void_cents': sum(v.each_cents * v.quantity for v in voids),
        'discounts': list(discounts), 'discount_cents': sum(c.discount_cents for c in discounts),
        'open_checks': Check.objects.filter(status=Check.OPEN).count(),
    }


def close_shift(shift, by, counted_cash_cents, counted_card_cents=None, note=''):
    with transaction.atomic():
        shift = Shift.objects.select_for_update().get(pk=shift.pk)
        if shift.status != Shift.OPEN:
            raise PosError('El turno ya está cerrado.')
        shift.status = Shift.CLOSED
        shift.closed_by = by
        shift.closed_at = timezone.now()
        shift.counted_cash_cents = max(int(counted_cash_cents or 0), 0)
        shift.counted_card_cents = None if counted_card_cents in (None, '') else max(int(counted_card_cents), 0)
        shift.note = note[:300]
        shift.save()
    from .printing import corte_ticket, queue

    queue(Printer.TICKET, 'Corte de caja', corte_ticket(shift_summary(shift)))
    return shift


# ---------------------------------------------------------------- inventory

def record_purchase(*, supplier, lines, reference='', note='', by=None):
    """`lines` is [(InventoryItem, quantity Decimal, cost_cents)]. Adds stock and records the unit cost."""
    lines = [(i, Decimal(q), int(c or 0)) for i, q, c in lines if Decimal(q) > 0]
    if not lines:
        raise PosError('Agrega al menos un producto con cantidad.')
    with transaction.atomic():
        purchase = Purchase.objects.create(supplier=supplier, reference=reference[:80], note=note[:200], by=by)
        for item, qty, cost in lines:
            PurchaseLine.objects.create(purchase=purchase, item=item, quantity=qty, cost_cents=cost)
            _move_stock(item.pk, qty, f'compra {supplier.name if supplier else ""} {reference}'.strip(),
                        by.name if by else '')
            if cost:
                ItemCost.objects.update_or_create(item=item, defaults={'unit_cost_cents': int(Decimal(cost) / qty)})
        return purchase


def record_waste(item, quantity, reason, by):
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise PosError('Cantidad no válida.')
    with transaction.atomic():
        _move_stock(item.pk, -quantity, f'merma: {reason}'[:200], by.name if by else '')


def start_count(by):
    with transaction.atomic():
        count = StockCount.objects.create(by=by)
        StockCountLine.objects.bulk_create([StockCountLine(count=count, item=i, expected=i.quantity)
                                            for i in InventoryItem.objects.filter(active=True)])
        return count


def apply_count(count, by):
    """Set every counted item to what was counted, each difference written to the history."""
    with transaction.atomic():
        count = StockCount.objects.select_for_update().get(pk=count.pk)
        if count.status != StockCount.OPEN:
            raise PosError('Este inventario ya se aplicó.')
        for line in count.lines.select_related('item').exclude(counted__isnull=True):
            item = InventoryItem.objects.select_for_update().get(pk=line.item_id)
            delta = line.counted - item.quantity
            if delta:
                item.quantity = line.counted
                item.save(update_fields=['quantity', 'updated_at'])
                InventoryChange.objects.create(item=item, delta=delta, quantity_after=line.counted,
                                               note='inventario físico', who=by.name if by else '')
        count.status = StockCount.APPLIED
        count.applied_at = timezone.now()
        count.save(update_fields=['status', 'applied_at'])
        return count
