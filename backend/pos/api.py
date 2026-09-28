"""The JSON the order screen talks to. Every call answers with the whole check, so the screen redraws from one
source of truth instead of patching itself and drifting from what the server holds."""

import json

from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import MenuItem

from . import services
from .auth import authorizer, pos_required
from .models import Check, CheckLine, Payment, Printer, PrintJob, Table
from .services import PosError


def _body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return {}


def cuenta_json(cuenta):
    cuenta = (Check.objects.select_related('table', 'waiter', 'discount_by')
              .prefetch_related('lines__created_by', 'lines__voided_by', 'payments').get(pk=cuenta.pk))
    return {
        'id': cuenta.id, 'folio': cuenta.folio, 'status': cuenta.status, 'where': cuenta.where,
        'tableId': cuenta.table_id, 'guests': cuenta.guests,
        'waiter': cuenta.waiter.name if cuenta.waiter else '',
        'openedAt': timezone.localtime(cuenta.opened_at).strftime('%H:%M'),
        'billPrinted': bool(cuenta.bill_printed_at),
        'lines': [{
            'id': l.id, 'name': l.name, 'qty': l.quantity, 'each': l.each_cents, 'total': l.total_cents,
            'mods': [m.get('name', '') for m in (l.modifiers or [])], 'note': l.note,
            'sent': bool(l.sent_at), 'voided': bool(l.voided_at),
            'voidReason': l.get_void_reason_display() if l.voided_at else '',
            'customer': l.from_customer, 'by': l.created_by.name if l.created_by else ('QR' if l.from_customer else ''),
        } for l in cuenta.lines.all()],
        'subtotal': cuenta.subtotal_cents, 'discount': cuenta.discount_cents, 'discountReason': cuenta.discount_reason,
        'total': cuenta.total_cents, 'paid': cuenta.paid_cents, 'tips': cuenta.tips_cents, 'due': cuenta.due_cents,
        'unsent': len(cuenta.unsent),
        'payments': [{'method': p.get_method_display(), 'amount': p.amount_cents, 'tip': p.tip_cents,
                      'change': p.change_cents, 'reference': p.reference}
                     for p in cuenta.payments.all() if p.status == Payment.PAID],
    }


def _answer(cuenta, jobs=(), **extra):
    data = {'cuenta': cuenta_json(cuenta), 'print': [{'id': j.id, 'browser': j.printer_id is None, 'title': j.title}
                                                    for j in jobs if j]}
    data.update(extra)
    return JsonResponse(data)


def _fail(exc, status=400):
    return JsonResponse({'error': str(exc)}, status=status)


def _jobs_since(mark):
    return list(PrintJob.objects.filter(created_at__gte=mark))


@pos_required(api=True)
def cuenta(request, cuenta_id):
    return _answer(get_object_or_404(Check, pk=cuenta_id))


def _action(fn):
    """POST, the check loaded, PosError shown to the floor, and any ticket this printed handed back."""

    @pos_required(api=True)
    @require_POST
    def view(request, cuenta_id):
        cuenta = get_object_or_404(Check, pk=cuenta_id)
        mark = timezone.now()
        body = _body(request)
        try:
            result = fn(request, cuenta, body)
        except PosError as exc:
            return _fail(exc)
        extra = {}
        if isinstance(result, tuple):
            result, extra = result
        target = result if isinstance(result, Check) else cuenta
        return _answer(target, _jobs_since(mark), switched=target.pk != cuenta.pk, **extra)

    view.__name__ = fn.__name__
    return view


@_action
def agregar(request, cuenta, body):
    item = MenuItem.objects.filter(pk=body.get('item'), available=True).first()
    if item is None:
        raise PosError('Ese producto no está disponible.')
    services.add_line(cuenta, item, quantity=body.get('qty') or 1, modifier_ids=body.get('mods') or [],
                      note=str(body.get('note') or ''), by=request.staff)


@_action
def enviar(request, cuenta, body):
    services.send(cuenta, request.staff)


@_action
def precuenta(request, cuenta, body):
    if cuenta.unsent:
        services.send(cuenta, request.staff)
    services.print_bill(cuenta, request.staff)


@_action
def descuento(request, cuenta, body):
    percent = body.get('percent')
    services.set_discount(cuenta, percent=int(percent) if percent not in (None, '') else None,
                          cents=_cents(body.get('amount')), reason=str(body.get('reason') or ''),
                          manager=authorizer(request, body))


@_action
def personas(request, cuenta, body):
    guests = int(body.get('guests') or 1)
    if not 1 <= guests <= 99:
        raise PosError('Número de personas no válido.')
    Check.objects.filter(pk=cuenta.pk).update(guests=guests)


@_action
def mover(request, cuenta, body):
    table = Table.objects.filter(pk=body.get('table'), active=True).first()
    if table is None:
        raise PosError('Elige una mesa.')
    return services.move(cuenta, table, request.staff)


@_action
def juntar(request, cuenta, body):
    other = Check.objects.filter(pk=body.get('other'), status=Check.OPEN).first()
    if other is None:
        raise PosError('Elige la cuenta a juntar.')
    return services.join(cuenta, other, request.staff)


@_action
def dividir(request, cuenta, body):
    new = services.split(cuenta, body.get('lines') or [], request.staff)
    return cuenta, {'message': f'Se separó en la cuenta {new.folio}.', 'newId': new.id}


@_action
def cancelar(request, cuenta, body):
    services.cancel_check(cuenta, reason=str(body.get('reason') or 'sin motivo'), manager=authorizer(request, body))


@_action
def pagar(request, cuenta, body):
    if not request.staff.can_charge and body.get('method') != Payment.PHONE:
        # A waiter can still take the money if a cashier or manager types their PIN.
        approver = authorizer(request, body)
        if approver is None:
            raise PosError('Cobrar requiere caja o gerente.')
    services.pay(cuenta, method=body.get('method'), amount_cents=_cents(body.get('amount')),
                 tip_cents=_cents(body.get('tip')), received_cents=_cents(body.get('received')),
                 reference=str(body.get('reference') or ''), by=request.staff, manager=authorizer(request, body))


@_action
def reabrir(request, cuenta, body):
    services.reopen(cuenta, authorizer(request, body))


def _cents(value):
    """'150', '150.50' or 150 pesos -> centavos."""
    if value in (None, ''):
        return 0
    try:
        return round(float(str(value).replace(',', '').replace('$', '')) * 100)
    except ValueError:
        raise PosError('Monto no válido.')


@pos_required(api=True)
@require_POST
def linea_cantidad(request, line_id):
    line = get_object_or_404(CheckLine, pk=line_id)
    try:
        services.change_quantity(line, int(_body(request).get('qty') or 0))
    except (PosError, ValueError) as exc:
        return _fail(exc)
    return _answer(line.cuenta)


@pos_required(api=True)
@require_POST
def linea_nota(request, line_id):
    line = get_object_or_404(CheckLine, pk=line_id)
    services.set_line_note(line, str(_body(request).get('note') or ''))
    return _answer(line.cuenta)


@pos_required(api=True)
@require_POST
def linea_cancelar(request, line_id):
    line = get_object_or_404(CheckLine, pk=line_id)
    body = _body(request)
    try:
        services.void_line(line, reason=body.get('reason'), note=str(body.get('note') or ''), by=request.staff,
                           manager=authorizer(request, body))
    except PosError as exc:
        return _fail(exc)
    return _answer(line.cuenta)


def table_states():
    """What the map colours each table by. Soft Restaurant's colours: libre, ocupada, cuenta impresa, and ours
    for a QR order nobody has sent yet (which is the one that needs a person to walk over)."""
    open_checks = (Check.objects.filter(status=Check.OPEN)
                   .select_related('table', 'waiter').prefetch_related('lines', 'payments'))
    by_table, loose = {}, []
    for c in open_checks:
        (by_table.setdefault(c.table_id, []) if c.table_id else loose).append(c)
    tables = []
    for t in Table.objects.filter(active=True).select_related('zone'):
        checks = by_table.get(t.id, [])
        state = 'free'
        if checks:
            state = 'busy'
            if any(l.from_customer and not l.sent_at and not l.voided_at for c in checks for l in c.lines.all()):
                state = 'order'
            elif all(c.bill_printed_at for c in checks):
                state = 'bill'
        tables.append({
            'id': t.id, 'number': t.number, 'label': t.label, 'zone': t.zone_id, 'shape': t.shape,
            'x': t.x, 'y': t.y, 'w': t.w, 'h': t.h, 'seats': t.seats, 'state': state,
            'checks': [{'id': c.id, 'folio': c.folio, 'total': c.total_cents, 'waiter': c.waiter.name if c.waiter else '',
                        'guests': c.guests, 'minutes': int((timezone.now() - c.opened_at).total_seconds() // 60)}
                       for c in checks],
        })
    return {
        'tables': tables,
        'loose': [{'id': c.id, 'folio': c.folio, 'where': c.where, 'total': c.total_cents,
                   'waiter': c.waiter.name if c.waiter else ''} for c in loose],
    }


@pos_required(api=True)
def mapa(request):
    return JsonResponse(table_states())
