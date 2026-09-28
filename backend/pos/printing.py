"""Tickets: what they say, and how a printer at the club gets them from a server that is not at the club.

Every ticket is a list of plain lines 42 characters wide (80mm paper, the printers' standard font). The same
lines become:

  - ePOS-Print XML for an Epson TM with **Server Direct Print** (TM-m30 and newer): the printer polls
    /pos/print/<token>/ every few seconds, we answer with any queued jobs, it posts back the result;
  - plain text for a Star with **CloudPRNT**: the printer polls, we say a job is ready, it GETs it, it DELETEs
    it when printed;
  - an 80mm HTML page for the browser fallback (`/pos/imprimir/<id>/`), so a tablet can print through its own
    print dialog before any printer is set up.

A job with no printer of its role is left for the browser: the screen that made it opens the print page.
"""

from xml.sax.saxutils import escape

from django.utils import timezone

from .models import Payment, Printer, PrintJob

WIDTH = 42
RULE = '-' * WIDTH


def queue(role, title, lines):
    printer = Printer.objects.filter(role=role, active=True).first()
    return PrintJob.objects.create(role=role, printer=printer, title=title[:80], lines=lines)


def _pair(left, right):
    left, right = str(left), str(right)
    room = WIDTH - len(right) - 1
    return f'{left[:room]:<{room}} {right}'


def _money(cents):
    return f'${cents / 100:,.2f}'


def _center(text):
    return str(text)[:WIDTH].center(WIDTH).rstrip()


def _header(cuenta, title):
    local = timezone.localtime()
    return [_center('IGUANA COMEDY'), _center(title), RULE,
            _pair(cuenta.where, f'Folio {cuenta.folio}'),
            _pair(f'Mesero: {cuenta.waiter.name if cuenta.waiter else "-"}', f'Pers: {cuenta.guests}'),
            _pair(f'{local:%d/%m/%Y}', f'{local:%H:%M}'), RULE]


def _item_lines(lines):
    out = []
    for line in lines:
        out.append(_pair(f'{line.quantity} {line.name}', _money(line.total_cents)))
        for mod in line.modifiers or []:
            out.append(f'   + {mod.get("name", "")}')
        if line.note:
            out.append(f'   * {line.note}'[:WIDTH])
    return out


def comanda_ticket(cuenta, comanda, lines, by):
    """What the bar makes. Big and plain: no prices, the table first."""
    out = [f'COMANDA {comanda.number}'.center(WIDTH).rstrip(), RULE,
           _pair(cuenta.where.upper(), f'Folio {cuenta.folio}'),
           _pair(f'{by.name if by else "Cliente (QR)"}', f'{timezone.localtime(comanda.created_at):%H:%M}'), RULE]
    for line in lines:
        out.append(f'{line.quantity:>2}  {line.name}'[:WIDTH])
        for mod in line.modifiers or []:
            out.append(f'     + {mod.get("name", "")}'[:WIDTH])
        if line.note:
            out.append(f'     * {line.note}'[:WIDTH])
    return out + [RULE]


def bill_ticket(cuenta, pay_url=''):
    out = _header(cuenta, 'CUENTA') + _item_lines(cuenta.live_lines()) + [RULE]
    out.append(_pair('Subtotal', _money(cuenta.subtotal_cents)))
    if cuenta.discount_cents:
        out.append(_pair(f'Descuento {cuenta.discount_reason}'[:30], '-' + _money(cuenta.discount_cents)))
    out.append(_pair('TOTAL', _money(cuenta.total_cents)))
    if cuenta.paid_cents:
        out.append(_pair('Pagado', _money(cuenta.paid_cents)))
        out.append(_pair('Por pagar', _money(cuenta.due_cents)))
    total = cuenta.total_cents
    out += [RULE, 'Propina sugerida:',
            _pair('  10%', _money(round(total * .10))), _pair('  15%', _money(round(total * .15))),
            _pair('  20%', _money(round(total * .20)))]
    from .views_pay import pay_link

    out += [RULE, _center('Paga con tu celular:'), pay_link(cuenta), RULE, _center('¡Gracias!')]
    return out


def final_ticket(cuenta):
    out = _header(cuenta, 'TICKET DE VENTA') + _item_lines(cuenta.live_lines()) + [RULE]
    if cuenta.discount_cents:
        out.append(_pair('Subtotal', _money(cuenta.subtotal_cents)))
        out.append(_pair('Descuento', '-' + _money(cuenta.discount_cents)))
    out.append(_pair('TOTAL', _money(cuenta.total_cents)))
    for p in cuenta.payments.filter(status=Payment.PAID):
        out.append(_pair(p.get_method_display(), _money(p.amount_cents)))
        if p.tip_cents:
            out.append(_pair('  Propina', _money(p.tip_cents)))
        if p.change_cents:
            out.append(_pair('  Cambio', _money(p.change_cents)))
    return out + [RULE, _center('¡Gracias por venir!'), _center('iguanacomedy.com')]


def corte_ticket(summary):
    shift = summary['shift']
    out = [_center('IGUANA COMEDY'), _center('CORTE DE CAJA'), RULE,
           _pair('Abrió', f'{shift.opened_by.name} {timezone.localtime(shift.opened_at):%d/%m %H:%M}')]
    if shift.closed_at:
        out.append(_pair('Cerró', f'{shift.closed_by.name} {timezone.localtime(shift.closed_at):%d/%m %H:%M}'))
    out += [RULE, _pair('Cuentas cobradas', summary['checks'])]
    for row in summary['methods']:
        if row['count']:
            out.append(_pair(f'{row["label"]} ({row["count"]})', _money(row['amount'])))
    out += [_pair('VENTA', _money(summary['sales'])), _pair('Propinas', _money(summary['tips'])),
            _pair('Descuentos', _money(summary['discount_cents'])),
            _pair('Cancelaciones', _money(summary['void_cents'])), RULE,
            _pair('Fondo inicial', _money(shift.opening_cash_cents)),
            _pair('Entradas', _money(summary['ins'])), _pair('Retiros', '-' + _money(summary['outs'])),
            _pair('EFECTIVO ESPERADO', _money(summary['expected_cash']))]
    if summary['counted_cash'] is not None:
        out.append(_pair('Efectivo contado', _money(summary['counted_cash'])))
        diff = summary['cash_difference']
        out.append(_pair('DIFERENCIA', ('+' if diff > 0 else '') + _money(diff) if diff else '$0.00'))
    return out + [RULE]


def epos_xml(jobs):
    """Server Direct Print's answer to a GetRequest: one ePOSPrint element per queued job."""
    parts = ['<?xml version="1.0" encoding="utf-8"?>', '<PrintRequestInfo Version="2.00">']
    for job in jobs:
        body = ''.join(f'<text>{escape(line)}&#10;</text>' for line in job.lines)
        parts.append(
            '<ePOSPrint><Parameter><devid>local_printer</devid><timeout>10000</timeout>'
            f'<printjobid>{job.id}</printjobid></Parameter><PrintData>'
            '<epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">'
            '<text lang="es" smooth="true"/>'
            f'{body}<feed line="3"/><cut type="feed"/></epos-print></PrintData></ePOSPrint>')
    parts.append('</PrintRequestInfo>')
    return ''.join(parts)


def plain_text(job):
    return '\n'.join(job.lines) + '\n\n\n\n'
