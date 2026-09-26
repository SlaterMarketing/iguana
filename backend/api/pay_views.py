"""Paying the table's bill from the customer's own phone.

The waiter holds up a QR, the table scans it, and the bill opens on their phone with a card form. Nothing
about the table changes until Stripe says the money moved.

🚨 **The amount is never posted.** The page sends which TIP was chosen; the bill is summed from the rounds
server-side on every request. A hidden total is a field somebody can edit, and a bar bill is exactly the thing
worth editing.

🚨 **Settling is idempotent and it locks.** The browser confirms, the Stripe webhook confirms, and a customer
who taps twice on a bad connection confirms again: the same payment must not be able to settle a table twice,
nor settle rounds somebody has since added. `settle()` takes the rows `FOR UPDATE` and does nothing at all
when the payment is already PAID.
⚠ `select_for_update(of=('self',))` because `TableOrder.event` is nullable, and Postgres refuses `FOR UPDATE`
on the nullable side of an outer join. SQLite ignores locking entirely, so this is a bug that passes every
local test and 500s the first time a real phone uses it.
"""

import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from sales.i18n import lang_from_request, normalize, tr
from sales.models import TableOrder, TablePayment
from sales.services import format_money, stripe_client, stripe_enabled
from sales.table_billing import (DEFAULT_TIP, TIP_CHOICES, bill_for, table_from_token, tip_cents,
                                 unpaid_rounds)

from .tables_views import CANCUN

log = logging.getLogger(__name__)


def _lang(request):
    """The phone's own language. `?lang=` wins, because the waiter may know better than the handset."""
    asked = request.GET.get('lang') or ''
    return normalize(asked) if asked in ('en', 'es') else lang_from_request(request)


def _money(cents, currency):
    return format_money(cents, currency)


def pay_page(request, token):
    """The bill, the tip toggle and the card form. Bilingual: a customer reads this one."""
    lang = _lang(request)
    number = table_from_token(token)
    if number is None:
        return render(request, 'floor/pay.html', {'lang': lang, 'gone': True}, status=404)

    bill = bill_for(number)
    options = [{'percent': p,
                'cents': tip_cents(bill['cents'], p),
                'money': _money(tip_cents(bill['cents'], p), bill['currency']),
                'total': _money(bill['cents'] + tip_cents(bill['cents'], p), bill['currency']),
                'on': p == DEFAULT_TIP} for p in TIP_CHOICES]
    return render(request, 'floor/pay.html', {
        'lang': lang,
        'token': token,
        'table': number,
        'label': bill['label'],
        'show': bill['show'].label(lang) if bill['show'] else '',
        'lines': [{'quantity': l['quantity'], 'name': l['name'], 'money': _money(l['cents'], bill['currency'])}
                  for l in bill['lines']],
        'bill': _money(bill['cents'], bill['currency']),
        'bill_cents': bill['cents'],
        'currency': bill['currency'].upper(),
        'tips': options,
        'default_tip': DEFAULT_TIP,
        'settled': bill['cents'] == 0,
        'stripe_key': settings.STRIPE_PUBLISHABLE_KEY if stripe_enabled() else '',
        'dev_payment': settings.DEBUG and not stripe_enabled(),
        # The button's own words, JSON-encoded here rather than interpolated inside the script. An apostrophe
        # in a translation would otherwise break the whole script and leave the page with no way to pay and
        # nothing on screen saying why.
        'card_text': json.dumps(tr(lang, 'Continue to card')),
        'pay_text': json.dumps(tr(lang, 'Pay now')),
        'working_text': json.dumps(tr(lang, 'One moment')),
        'failed_text': json.dumps(tr(lang, 'That did not go through. Please try again.')),
    })


def _chosen_tip(request):
    try:
        percent = int(request.POST.get('tip', DEFAULT_TIP))
    except (TypeError, ValueError):
        percent = DEFAULT_TIP
    return percent if percent in TIP_CHOICES else DEFAULT_TIP


@require_POST
def pay_intent(request, token):
    """Price the bill again, then ask Stripe for an intent. Never trusts a number from the page."""
    lang = _lang(request)
    number = table_from_token(token)
    if number is None:
        return JsonResponse({'error': tr(lang, 'This bill has closed.')}, status=404)

    bill = bill_for(number)
    if bill['cents'] == 0:
        return JsonResponse({'error': tr(lang, 'There is nothing to pay on this table.')}, status=409)

    percent = _chosen_tip(request)
    tip = tip_cents(bill['cents'], percent)
    payment = TablePayment.objects.create(
        table_number=number, event=bill['show'], bill_cents=bill['cents'], tip_cents=tip,
        tip_percent=percent, total_cents=bill['cents'] + tip, currency=bill['currency'], locale=lang)

    if not stripe_enabled():
        # Local development only. In production this refuses rather than pretending, because a bill that says
        # paid and took no money is worse than one that cannot be paid at all.
        if settings.DEBUG:
            return JsonResponse({'paymentId': payment.id, 'devPayment': True,
                                 'totalCents': payment.total_cents})
        return JsonResponse({'error': tr(lang, 'Card payment is not available right now.')}, status=503)

    intent = stripe_client().PaymentIntent.create(
        amount=payment.total_cents, currency=payment.currency,
        automatic_payment_methods={'enabled': True},
        metadata={'purpose': 'table', 'payment_id': payment.id, 'table': str(number)},
        description=f'Iguana Comedy table {number}',
    )
    payment.stripe_payment_intent_id = intent.id
    payment.save(update_fields=['stripe_payment_intent_id'])
    return JsonResponse({'paymentId': payment.id, 'clientSecret': intent.client_secret,
                         'totalCents': payment.total_cents})


def settle(payment, charge_id=''):
    """Mark the table paid, once, whoever asks.

    The browser asks, the webhook asks, and a customer on a bad connection asks twice. Only the first one may
    move anything, which is why the guard is the payment's own status inside the lock rather than a check the
    caller is trusted to have made.

    ⚠ Rounds are marked one at a time and `payment` is stamped on each, so "which drinks did this card pay
    for" is answerable later. A queryset `.update()` would be faster and would lose that.
    """
    with transaction.atomic():
        fresh = TablePayment.objects.select_for_update().get(pk=payment.pk)
        if fresh.status == TablePayment.PAID:
            return fresh
        now = timezone.now()
        rounds = list(unpaid_rounds(fresh.table_number).select_for_update(of=('self',)))
        for order in rounds:
            order.status = TableOrder.PAID
            order.paid_at = now
            order.payment = fresh
            if order.delivered_at is None:
                order.delivered_at = now  # they are paying for it, so it reached the table
            order.save(update_fields=['status', 'paid_at', 'payment', 'delivered_at'])
        fresh.status = TablePayment.PAID
        fresh.paid_at = now
        fresh.stripe_charge_id = charge_id or ''
        fresh.save(update_fields=['status', 'paid_at', 'stripe_charge_id'])
    return fresh


@csrf_exempt
@require_POST
def pay_confirm(request, token):
    """The browser reporting a successful card. Verified against Stripe, never believed on its own."""
    lang = _lang(request)
    payment = TablePayment.objects.filter(pk=request.POST.get('paymentId', '')).first()
    if payment is None or table_from_token(token) != payment.table_number:
        return JsonResponse({'error': tr(lang, 'This bill has closed.')}, status=404)

    if payment.status != TablePayment.PAID:
        if payment.stripe_payment_intent_id:
            intent = stripe_client().PaymentIntent.retrieve(payment.stripe_payment_intent_id)
            if intent.status != 'succeeded':
                return JsonResponse({'error': tr(lang, 'Payment has not completed yet.')}, status=409)
            settle(payment, intent.latest_charge or '')
        elif settings.DEBUG and not stripe_enabled():
            settle(payment)
        else:
            return JsonResponse({'error': tr(lang, 'Payment has not completed yet.')}, status=409)
    return JsonResponse({'ok': True, 'doneUrl': f'/mesa/pagar/{token}/listo/'})


def pay_done(request, token):
    """What the table sees when the card has gone through: the one screen they show the waiter on the way out."""
    lang = _lang(request)
    number = table_from_token(token)
    payment = (TablePayment.objects.filter(table_number=number, status=TablePayment.PAID)
               .order_by('-paid_at').first() if number is not None else None)
    return render(request, 'floor/pay_done.html', {
        'lang': lang,
        'table': number,
        'paid': payment is not None,
        'total': _money(payment.total_cents, payment.currency) if payment else '',
        'tip': _money(payment.tip_cents, payment.currency) if payment and payment.tip_cents else '',
        'when': payment.paid_at.astimezone(CANCUN) if payment and payment.paid_at else None,
    })
