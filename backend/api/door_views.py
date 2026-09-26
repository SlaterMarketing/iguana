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

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
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

log = logging.getLogger(__name__)


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
            # 🚨 Log what was actually scanned. A refusal at the door is the one place where "it says the
            # ticket does not work" has to be answerable in seconds, and the commonest cause is not a bug: it
            # is a QR from the guest promoter's platform, which our scanner can never read. Without this the
            # only evidence is a 200 in the access log with no body.
            log.warning('door: no ticket for scanned code %r (len %d)', raw[:80], len(raw))
            return JsonResponse({'state': 'unknown', 'name': '', 'event': '', 'type': '', 'collect': '',
                                 'seen_at': '', 'order': ''})
        state = _verdict(ticket, now)
        if state == 'valid':
            ticket.checked_in_at = now
            ticket.save(update_fields=['checked_in_at'])
        payload = _payload(ticket, state)
    return JsonResponse(payload)


@floor_required
def lookup(request):
    """Find a guest by typing a few letters of their name.

    🚨 This is the path that actually works on the iPhones at the door. iOS Safari has no `BarcodeDetector`,
    so the in-page scanner cannot run there at all, and a guest whose ticket was sold by a promoter carries
    THEIR QR, which our scanner could never read even on Android. Both of those people are admitted the same
    way: the door types three letters of the name and taps the right row.

    Matches on name or email, because somebody who booked under a partner's name is found by the address on
    the phone they are holding out.
    """
    term = (request.GET.get('q') or '').strip()
    if len(term) < 2:
        return JsonResponse({'guests': []})

    now = timezone.now()
    tickets = (Ticket.objects
               .filter(order__status=Order.COMPLETED)
               .filter(Q(order__customer_name__icontains=term) | Q(order__customer_email__icontains=term))
               .select_related('order', 'order__event')
               .order_by('order__customer_name', 'pk')[:40])

    guests = []
    for ticket in tickets:
        payload = _payload(ticket, _verdict(ticket, now))
        payload['token'] = ticket.checkin_token
        payload['promoter'] = ticket.order.source or ''
        guests.append(payload)
    return JsonResponse({'guests': guests})


@floor_required
@require_POST
def admit(request):
    """Let one in by hand, from the lookup. Same rules and the same marking as a scan.

    Deliberately the SAME code path as the scanner: a hand-admitted guest has to be marked, counted and
    refused-when-already-used exactly like a scanned one, or the two halves of the door disagree about who is
    inside.
    """
    return verify(request)


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
