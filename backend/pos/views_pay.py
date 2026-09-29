"""The customer's phone paying a check, and the printers fetching their tickets.

Paying: the precuenta carries a QR of /pos/pagar/<check pay_token>/. The page is the same one the table QR has
always used (templates/floor/pay.html), fed this check's lines. The amount is always recomputed here from the
check; the phone only chooses the tip. A PENDING Payment is made when the card form opens and becomes PAID
when Stripe says so, from the browser or from the webhook, whichever is first.
"""

import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from sales.i18n import lang_from_request, normalize, tr
from sales.links import public_base
from sales.services import format_money, stripe_client, stripe_enabled

from .models import Check, Payment, Printer, PrintJob, Shift
from .printing import epos_xml, plain_text

log = logging.getLogger(__name__)

TIP_CHOICES = (0, 10, 15, 20)
DEFAULT_TIP = 15


def pay_link(cuenta):
    return f'{public_base()}/pos/pagar/{cuenta.pay_token}/'


def _lang(request):
    asked = request.GET.get('lang') or ''
    return normalize(asked) if asked in ('en', 'es') else lang_from_request(request)


def _tip(cents, percent):
    return round(cents * percent / 100)


def pay_page(request, token):
    lang = _lang(request)
    cuenta = Check.objects.filter(pay_token=token).first()
    if cuenta is None or cuenta.status == Check.CANCELLED:
        return render(request, 'floor/pay.html', {'lang': lang, 'gone': True}, status=404)
    due = cuenta.due_cents if cuenta.status == Check.OPEN else 0
    options = [{'percent': p, 'money': format_money(_tip(due, p), 'mxn'),
                'total': format_money(due + _tip(due, p), 'mxn'), 'on': p == DEFAULT_TIP} for p in TIP_CHOICES]
    return render(request, 'floor/pay.html', {
        'lang': lang, 'token': token, 'pay_base': f'/pos/pagar/{token}/',
        'table': cuenta.folio, 'label': cuenta.where,
        'show': cuenta.event.label(lang) if cuenta.event else '',
        'lines': [{'quantity': l.quantity, 'name': l.name, 'money': format_money(l.total_cents, 'mxn')}
                  for l in cuenta.live_lines()],
        'bill': format_money(due, 'mxn'), 'bill_cents': due, 'currency': 'MXN', 'tips': options,
        'default_tip': DEFAULT_TIP, 'settled': due == 0,
        'stripe_key': settings.STRIPE_PUBLISHABLE_KEY if stripe_enabled() else '',
        'dev_payment': settings.DEBUG and not stripe_enabled(),
        'card_text': json.dumps(tr(lang, 'Continue to card')), 'pay_text': json.dumps(tr(lang, 'Pay now')),
        'working_text': json.dumps(tr(lang, 'One moment')),
        'failed_text': json.dumps(tr(lang, 'That did not go through. Please try again.')),
    })


@require_POST
def pay_intent(request, token):
    lang = _lang(request)
    cuenta = Check.objects.filter(pay_token=token, status=Check.OPEN).first()
    if cuenta is None:
        return JsonResponse({'error': tr(lang, 'This bill has closed.')}, status=404)
    due = cuenta.due_cents
    if due == 0:
        return JsonResponse({'error': tr(lang, 'There is nothing to pay on this table.')}, status=409)
    try:
        percent = int(request.POST.get('tip', DEFAULT_TIP))
    except ValueError:
        percent = DEFAULT_TIP
    percent = percent if percent in TIP_CHOICES else DEFAULT_TIP
    payment = Payment.objects.create(cuenta=cuenta, method=Payment.PHONE, status=Payment.PENDING,
                                     amount_cents=due, tip_cents=_tip(due, percent))
    if not stripe_enabled():
        if settings.DEBUG:
            return JsonResponse({'paymentId': payment.id, 'devPayment': True})
        return JsonResponse({'error': tr(lang, 'Card payment is not available right now.')}, status=503)
    intent = stripe_client().PaymentIntent.create(
        amount=payment.amount_cents + payment.tip_cents, currency='mxn',
        payment_method_types=['card'],  # no Stripe Link box, as on the ticket checkout
        metadata={'purpose': 'pos', 'payment_id': payment.id, 'folio': str(cuenta.folio)},
        description=f'Iguana Comedy cuenta {cuenta.folio}')
    Payment.objects.filter(pk=payment.pk).update(stripe_payment_intent_id=intent.id)
    return JsonResponse({'paymentId': payment.id, 'clientSecret': intent.client_secret})


def settle(payment, charge_id=''):
    """Turn a phone payment PAID, once, and close the check if that paid it. Called by the page and the webhook."""
    from . import services

    with transaction.atomic():
        fresh = Payment.objects.select_for_update(of=('self',)).get(pk=payment.pk)
        if fresh.status == Payment.PAID:
            return fresh
        cuenta = Check.objects.select_for_update(of=('self',)).get(pk=fresh.cuenta_id)
        if cuenta.unsent:
            services.send(cuenta, None)
        fresh.status = Payment.PAID
        fresh.stripe_charge_id = charge_id or ''
        fresh.shift = Shift.current()
        fresh.created_at = timezone.now()
        fresh.save(update_fields=['status', 'stripe_charge_id', 'shift', 'created_at'])
        cuenta = Check.objects.prefetch_related('lines', 'payments').get(pk=cuenta.pk)
        if cuenta.status == Check.OPEN and cuenta.due_cents == 0:
            services._close(cuenta, None)
    return fresh


@csrf_exempt
@require_POST
def pay_confirm(request, token):
    lang = _lang(request)
    payment = Payment.objects.filter(pk=request.POST.get('paymentId', ''), cuenta__pay_token=token).first()
    if payment is None:
        return JsonResponse({'error': tr(lang, 'This bill has closed.')}, status=404)
    if payment.status != Payment.PAID:
        if payment.stripe_payment_intent_id:
            intent = stripe_client().PaymentIntent.retrieve(payment.stripe_payment_intent_id)
            if intent.status != 'succeeded':
                return JsonResponse({'error': tr(lang, 'Payment has not completed yet.')}, status=409)
            settle(payment, intent.latest_charge or '')
        elif settings.DEBUG and not stripe_enabled():
            settle(payment)
        else:
            return JsonResponse({'error': tr(lang, 'Payment has not completed yet.')}, status=409)
    return JsonResponse({'ok': True, 'doneUrl': f'/pos/pagar/{token}/listo/'})


def pay_done(request, token):
    lang = _lang(request)
    cuenta = get_object_or_404(Check, pay_token=token)
    payment = cuenta.payments.filter(method=Payment.PHONE, status=Payment.PAID).order_by('-created_at').first()
    return render(request, 'floor/pay_done.html', {
        'lang': lang, 'table': cuenta.where, 'paid': payment is not None,
        'total': format_money(payment.amount_cents + payment.tip_cents, 'mxn') if payment else '',
        'tip': format_money(payment.tip_cents, 'mxn') if payment and payment.tip_cents else '',
        'when': timezone.localtime(payment.created_at) if payment else None,
    })


# ---------------------------------------------------------------- printers

@csrf_exempt
def printer_poll(request, token):
    """One URL per printer, speaking whichever protocol that printer was registered with."""
    printer = Printer.objects.filter(token=token, active=True).first()
    if printer is None:
        return HttpResponse(status=404)
    Printer.objects.filter(pk=printer.pk).update(last_seen_at=timezone.now())
    return (_epson if printer.protocol == Printer.EPSON else _star)(request, printer)


def _waiting(printer):
    return PrintJob.objects.filter(printer=printer, status__in=(PrintJob.QUEUED, PrintJob.SENT)).order_by('created_at')


def _epson(request, printer):
    """Server Direct Print: ConnectionType=GetRequest asks for work, SetResponse reports what printed."""
    kind = request.POST.get('ConnectionType', '')
    if kind == 'SetResponse':
        text = request.POST.get('ResponseFile', '')
        for job in _waiting(printer).filter(status=PrintJob.SENT):
            if job.id in text:
                ok = f'<printjobid>{job.id}</printjobid>' in text and 'success="false"' not in text.split(job.id)[1][:300]
                job.status = PrintJob.DONE if ok else PrintJob.QUEUED
                job.done_at = timezone.now() if ok else None
                job.save(update_fields=['status', 'done_at'])
        return HttpResponse('', content_type='text/plain')
    jobs = list(_waiting(printer)[:5])
    if not jobs:
        return HttpResponse('', content_type='text/xml; charset=utf-8')
    PrintJob.objects.filter(pk__in=[j.pk for j in jobs]).update(status=PrintJob.SENT, sent_at=timezone.now())
    return HttpResponse(epos_xml(jobs), content_type='text/xml; charset=utf-8')


def _star(request, printer):
    """CloudPRNT: POST polls, GET fetches the job, DELETE confirms it printed."""
    job = _waiting(printer).first()
    if request.method == 'POST':
        body = {'jobReady': job is not None}
        if job:
            body.update({'mediaTypes': ['text/plain'], 'jobToken': job.id})
        return JsonResponse(body)
    if request.method == 'GET':
        wanted = PrintJob.objects.filter(pk=request.GET.get('token') or (job.id if job else ''), printer=printer).first()
        if wanted is None:
            return HttpResponse(status=404)
        PrintJob.objects.filter(pk=wanted.pk).update(status=PrintJob.SENT, sent_at=timezone.now())
        return HttpResponse(plain_text(wanted), content_type='text/plain; charset=utf-8')
    if request.method == 'DELETE':
        wanted = PrintJob.objects.filter(pk=request.GET.get('token', ''), printer=printer).first()
        if wanted:
            code = request.GET.get('code', '200OK')
            ok = code.startswith('2')
            wanted.status = PrintJob.DONE if ok else PrintJob.QUEUED
            wanted.done_at = timezone.now() if ok else None
            wanted.save(update_fields=['status', 'done_at'])
        return HttpResponse(status=200)
    return HttpResponse(status=405)
