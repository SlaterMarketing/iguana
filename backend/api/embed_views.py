from datetime import UTC, datetime, timedelta

import stripe
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import Event
from crm.geo import remember_on_contact, visitor_profile
from crm.models import Contact, TrackedEvent
from crm.unsubscribe import email_from_token, resume_marketing, stop_marketing
from sales.ad_reporting import report_checkout_started
from sales.i18n import lang_from_request, normalize, tr
from sales.models import Membership, MembershipPlan, Order, Ticket
from sales.services import (DATE_FORMATS, CheckoutError, complete_order, create_order, current_membership, price_cart,
                            reserve_at_door, stripe_client, stripe_enabled)

from .auth import contact_from_fan_token, error, json_body
from .fan_views import fan_event_json
from .public_views import _by_id_or_slug, public_events


def tracker_js(request):
    response = render(request, 'embed/k.js', {'backend_url': settings.BACKEND_URL}, content_type='application/javascript')
    response['Cache-Control'] = 'public, max-age=300'
    return response


# Strings the checkout script builds in the browser. The page gets them already translated.
CHECKOUT_JS_STRINGS = ('Sold out', 'pay at the door', 'members only', '{0} left', 'Add one {0}', 'Remove one {0}',
                       'Up to {0} per order', 'Member benefit ({0} free)', 'Member discount',
                       'Reserve 1 seat', 'Reserve {0} seats', 'Pay {0} at the door', 'Free', 'Get 1 ticket',
                       'Get {0} tickets', 'Pay {0}', '1 ticket', '{0} tickets', 'Reserving...', 'Processing...',
                       'Enter your name and email.', 'The total is now {0}. Press the button again to pay it.',
                       'Something went wrong.')


@xframe_options_exempt
def event_checkout(request, key):
    event = _by_id_or_slug(public_events(), key)
    lang = normalize(request.GET.get('lang'))
    return render(request, 'embed/checkout.html', {
        'event': event,
        'event_name': event.label(lang),
        'lang': lang,
        'embedded': request.GET.get('embedded') == '1',
        'bootstrap': {
            'lang': lang,
            'strings': {text: tr(lang, text) for text in CHECKOUT_JS_STRINGS},
            'event': fan_event_json(event, None, lang),
            'apiBase': settings.BACKEND_URL,
            'stripeKey': settings.STRIPE_PUBLISHABLE_KEY if stripe_enabled() else '',
            'devPayments': settings.DEBUG and not stripe_enabled(),
            'siteOrigins': settings.SITE_URLS,
        },
    })


def _body_lang(request):
    body = json_body(request)
    return normalize(body.get('lang')) if isinstance(body, dict) else 'en'


def _cart_payload(request):
    body = json_body(request)
    if body is None:
        raise CheckoutError('Invalid request')
    items = body.get('items') or {}
    if not isinstance(items, dict):
        raise CheckoutError('Invalid ticket selection')
    return body, {str(k): v for k, v in items.items()}, contact_from_fan_token(str(body.get('fanToken') or ''))


@csrf_exempt
def unsubscribe(request, token):
    """The link at the foot of every bulk email. GET shows where the address stands, POST changes it.

    Gmail's one-click button POSTs here without a CSRF token and without a session, so the view is exempt: the
    signed token in the URL is the only thing that proves who is asking, and it only ever names one address.
    """
    email = email_from_token(token)
    lang = lang_from_request(request)
    contact = Contact.objects.filter(email=email).first() if email else None

    if request.method == 'POST' and contact:
        if request.POST.get('action') == 'resubscribe':
            resume_marketing(contact)
        else:
            stop_marketing(contact)

    return render(request, 'embed/unsubscribe.html', {
        'lang': lang,
        'email': email,
        # An address we have never seen counts as unsubscribed: there is nothing to send it either way.
        'subscribed': bool(contact and contact.subscribed),
        'site_url': settings.SITE_URLS[0] if settings.SITE_URLS else settings.BACKEND_URL,
    })


@csrf_exempt
@require_POST
def checkout_quote(request, event_id):
    event = get_object_or_404(public_events(), pk=event_id)
    lang = _body_lang(request)
    try:
        _, items, contact = _cart_payload(request)
        cart = price_cart(event, items, contact, lang)
    except CheckoutError as exc:
        return error(exc.translated(lang))
    return JsonResponse({'subtotalCents': cart.subtotal_cents, 'discountCents': cart.discount_cents,
                         'freeTickets': cart.free_tickets, 'totalCents': cart.total_cents, 'currency': event.currency,
                         'isMember': current_membership(contact) is not None,
                         'payAtDoor': any(ticket_type.pay_at_door for ticket_type, _, _ in cart.lines)})


@csrf_exempt
@require_POST
def checkout_start(request, event_id):
    event = get_object_or_404(public_events(), pk=event_id)
    lang = _body_lang(request)
    if event.ticketing_type != 'INTERNAL' or event.status in (Event.CANCELLED, Event.POSTPONED, Event.SOLD_OUT):
        return error(tr(lang, 'Tickets are not on sale for this show.'))
    try:
        body, items, contact = _cart_payload(request)
        name, email, phone = (str(body.get(k) or '').strip() for k in ('name', 'email', 'phone'))
        if not name or '@' not in email:
            raise CheckoutError('Enter your name and email.')
        if contact and contact.email != email.lower():
            contact = None  # member pricing only applies to the signed-in member's own email
        cart = price_cart(event, items, contact, lang)
    except CheckoutError as exc:
        return error(exc.translated(lang))

    attribution = body.get('attribution') if isinstance(body.get('attribution'), dict) else {}
    attribution = {k: str(v)[:200] for k, v in attribution.items() if k != 'visitor'}
    client = body.get('client') if isinstance(body.get('client'), dict) else {}
    attribution['visitor'] = visitor_profile(request, locale=lang, browser_language=client.get('browserLanguage', ''),
                                             time_zone=client.get('timeZone', ''))
    # Meta matches a server-side conversion on the browser that made it. The fan is in this iframe, so the header
    # is theirs; `_fbp` and `_fbc` belong to the site origin and arrive in attribution from k.js.
    attribution['userAgent'] = request.headers.get('User-Agent', '')[:500]

    if any(ticket_type.pay_at_door for ticket_type, _, _ in cart.lines):
        try:
            order = reserve_at_door(event, cart, name=name, email=email, phone=phone, contact=contact,
                                    attribution=attribution, locale=lang)
        except CheckoutError as exc:
            return error(exc.translated(lang))
        remember_on_contact(order.contact, attribution['visitor'])
        return JsonResponse({'orderId': order.id, 'complete': True,
                             'successUrl': f'{settings.BACKEND_URL}/orders/{order.public_view_token}/'})

    order = create_order(event, cart, name=name, email=email, phone=phone, contact=contact, attribution=attribution,
                         locale=lang)
    remember_on_contact(order.contact, attribution['visitor'])
    report_checkout_started(order)
    success_url = f'{settings.BACKEND_URL}/orders/{order.public_view_token}/'

    if cart.total_cents == 0:
        complete_order(order)
        return JsonResponse({'orderId': order.id, 'complete': True, 'successUrl': success_url})
    if not stripe_enabled():
        if settings.DEBUG:
            return JsonResponse({'orderId': order.id, 'complete': False, 'devPayment': True, 'successUrl': success_url,
                                 'totalCents': cart.total_cents})
        return error(tr(lang, 'Online payment is not available yet. Please contact us to book.'))

    intent = stripe_client().PaymentIntent.create(
        amount=cart.total_cents, currency=event.currency, receipt_email=order.customer_email,
        automatic_payment_methods={'enabled': True},
        metadata={'purpose': 'tickets', 'order_id': order.id, 'event_id': event.id},
        description=f'{event.name} tickets',
    )
    order.stripe_payment_intent_id = intent.id
    order.save(update_fields=['stripe_payment_intent_id'])
    return JsonResponse({'orderId': order.id, 'complete': False, 'clientSecret': intent.client_secret,
                         'successUrl': success_url, 'totalCents': cart.total_cents})


@csrf_exempt
@require_POST
def checkout_confirm(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    lang = _body_lang(request)
    if order.status != Order.COMPLETED:
        if order.stripe_payment_intent_id:
            intent = stripe_client().PaymentIntent.retrieve(order.stripe_payment_intent_id)
            if intent.status != 'succeeded':
                return error(tr(lang, 'Payment has not completed yet.'), 409)
            complete_order(order, intent.latest_charge or '')
        elif settings.DEBUG and not stripe_enabled():
            complete_order(order)  # local development: no Stripe keys, simulate a successful payment
        else:
            return error(tr(lang, 'Payment has not completed yet.'), 409)
    return JsonResponse({'ok': True, 'successUrl': f'{settings.BACKEND_URL}/orders/{order.public_view_token}/'})


def order_page(request, token):
    order = get_object_or_404(Order.objects.select_related('event__venue').prefetch_related('items', 'tickets'),
                              public_view_token=token)
    lang = normalize(order.locale)
    return render(request, 'embed/order.html', {
        'order': order, 'lang': lang, 'date_format': DATE_FORMATS[lang],
        'status_label': tr(lang, order.get_status_display().lower()),
        'site_url': settings.SITE_URLS[0] if settings.SITE_URLS else '',
    })


@staff_member_required
def checkin(request, token):
    ticket = get_object_or_404(Ticket.objects.select_related('order__event'), checkin_token=token)
    just_checked_in = False
    if request.method == 'POST' and ticket.checked_in_at is None and ticket.order.status == Order.COMPLETED:
        ticket.checked_in_at = timezone.now()
        ticket.save(update_fields=['checked_in_at'])
        just_checked_in = True
    lang = lang_from_request(request)
    return render(request, 'embed/checkin.html', {
        'ticket': ticket, 'just_checked_in': just_checked_in, 'lang': lang,
        'status_label': tr(lang, ticket.order.get_status_display().lower()),
    })


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get('Stripe-Signature', ''),
                                               settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)
    obj = event['data']['object']
    kind = event['type']

    if kind == 'payment_intent.succeeded':
        meta = obj.get('metadata') or {}
        if meta.get('purpose') == 'tickets':
            order = Order.objects.filter(pk=meta.get('order_id')).first()
            if order:
                complete_order(order, obj.get('latest_charge') or '')
        elif meta.get('purpose') == 'membership_oneoff':
            plan = MembershipPlan.objects.filter(pk=meta.get('plan_id')).first()
            contact_id = meta.get('contact_id')
            if plan and contact_id and not Membership.objects.filter(notes=f'pi:{obj["id"]}').exists():
                now = timezone.now()
                ends = None if meta.get('kind') == 'lifetime' else now + timedelta(days=plan.pass_days or 1)
                Membership.objects.create(contact_id=contact_id, plan=plan, status=Membership.ACTIVE,
                                          source=meta.get('kind', '').upper(), starts_at=now, ends_at=ends,
                                          notes=f'pi:{obj["id"]}')

    elif kind in ('customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'):
        membership = Membership.objects.filter(stripe_subscription_id=obj['id']).first()
        if membership:
            status = obj.get('status')
            membership.status = {
                'active': Membership.ACTIVE, 'trialing': Membership.ACTIVE, 'past_due': Membership.PAST_DUE,
                'canceled': Membership.CANCELED, 'unpaid': Membership.PAST_DUE,
                'incomplete': Membership.PENDING, 'incomplete_expired': Membership.EXPIRED,
            }.get(status, membership.status)
            items = (obj.get('items') or {}).get('data') or []
            period_end = obj.get('current_period_end') or (items[0].get('current_period_end') if items else None)
            if period_end:
                membership.ends_at = datetime.fromtimestamp(period_end, tz=UTC)
            membership.auto_renew = not obj.get('cancel_at_period_end') and status != 'canceled'
            membership.save()

    return HttpResponse(status=200)


@csrf_exempt
def ingest(request, kind):
    if request.method != 'POST':
        return HttpResponse(status=405)
    body = json_body(request) or {}
    if str(body.get('token', '')) not in settings.PUBLIC_API_KEYS:
        return HttpResponse(status=204)
    TrackedEvent.objects.create(
        kind=kind[:40],
        name=str(body.get('name', ''))[:80],
        visitor_key=str(body.get('visitorKey', ''))[:100],
        url=str(body.get('url', ''))[:1000],
        referrer=str(body.get('referrer', ''))[:1000],
        properties={k: body[k] for k in ('utm', 'props', 'email', 'traits') if body.get(k)},
    )
    return HttpResponse(status=204)
