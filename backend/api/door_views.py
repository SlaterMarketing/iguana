"""La puerta: escanear un boleto, decir si sirve, y marcarlo.

Spanish only, like the rest of `/mesas/`.

The QR on a ticket holds the full check-in URL, so a phone's own camera app already opens the check-in page and
always will: this page exists because at a door that is too slow. Opening the camera app, waiting for the
banner, tapping it, waiting for a page, going back, and doing it again for the next person is four actions per
guest. Here the camera stays open and the answer appears in place.

🚨 Nobody has ever been checked in here (0 of 24 on one night, 0 of 16 on another), so the guest list at
`/mesas/reservas/` is what the door actually uses. That is worth remembering before trusting `checked_in_at`
for anything: a ticket with no check-in means nothing at all about whether that person came.
"""

from datetime import timedelta

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from sales.models import Order, Ticket
from sales.services import format_money

from .floor import floor_required

# A second scan of the same code moments later is the scanner seeing one QR twice, or a nervous second tap, not
# somebody trying it on. Inside this window it reads as "just let in" rather than as a warning, because a red
# screen at a door makes staff stop and argue with a guest who has done nothing wrong.
JUST_NOW = timedelta(seconds=20)


def _verdict(ticket, now):
    """What the door should do, as one word plus the facts behind it."""
    order = ticket.order
    if order.status != Order.COMPLETED:
        return 'unpaid'
    if ticket.checked_in_at is None:
        return 'valid'
    return 'just_now' if now - ticket.checked_in_at <= JUST_NOW else 'used'


def _payload(ticket, state):
    order = ticket.order
    collect = ticket.door_price_cents
    return {
        'state': state,
        'name': (order.customer_name or '').strip() or (order.customer_email or ''),
        'event': order.event.label('es') if order.event else order.event_name,
        'type': ticket.ticket_type_name,
        'collect': format_money(collect, order.currency) if collect else '',
        'seen_at': timezone.localtime(ticket.checked_in_at).strftime('%H:%M') if ticket.checked_in_at else '',
        'order': order.id,
    }


@floor_required
def door(request):
    return render(request, 'floor/puerta.html', {})


@floor_required
@require_POST
def verify(request):
    """Check one code and, when it is good, mark it used in the same breath.

    Marking happens here rather than on a second tap on purpose: a door that asks for a confirmation gets one
    reflexively, so the tap adds delay and no safety. What it does need is to be atomic, because two people
    scanning the same queue at once is normal, and the second scanner must be told `used`, not `valid`.
    """
    raw = (request.POST.get('code') or '').strip()
    # The QR holds a URL, so take the last non-empty path segment; a hand-typed code arrives bare.
    token = [part for part in raw.split('?')[0].rstrip('/').split('/') if part][-1] if raw else ''
    if not token:
        return JsonResponse({'state': 'unknown', 'name': '', 'event': '', 'type': '', 'collect': '',
                             'seen_at': '', 'order': ''})

    now = timezone.now()
    with transaction.atomic():
        # 🚨 `of=('self',)` is load-bearing, and its absence passes every local test. `Order.event` is
        # nullable, so `select_related('order__event')` is a LEFT OUTER JOIN, and Postgres refuses
        # `FOR UPDATE cannot be applied to the nullable side of an outer join`. SQLite ignores
        # `select_for_update` altogether, so the suite is green on a query that 500s in production the first
        # time somebody scans a ticket. Locking the ticket row alone is also all this needs.
        ticket = (Ticket.objects.select_for_update(of=('self',))
                  .select_related('order', 'order__event')
                  .filter(checkin_token=token).first())
        if ticket is None:
            return JsonResponse({'state': 'unknown', 'name': '', 'event': '', 'type': '', 'collect': '',
                                 'seen_at': '', 'order': ''})
        state = _verdict(ticket, now)
        if state == 'valid':
            ticket.checked_in_at = now
            ticket.save(update_fields=['checked_in_at'])
        payload = _payload(ticket, state)
    return JsonResponse(payload)


@floor_required
@require_POST
def undo(request):
    """Let one back out, because a scanner that cannot be wrong is a scanner nobody trusts.

    Somebody scans the wrong ticket, or a phone reads the QR behind the one being held up. Without this the
    door's only option is to wave the real holder through and leave the record lying.
    """
    token = (request.POST.get('token') or '').strip()
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().filter(checkin_token=token).first()
        if ticket is not None and ticket.checked_in_at is not None:
            ticket.checked_in_at = None
            ticket.save(update_fields=['checked_in_at'])
    return JsonResponse({'ok': True})
