"""The PIN is the whole door (owner, 2026-09-28: "they can just log in with their pin").

There used to be a second lock, the tablet signed in as a floor account first. It was dropped because staff
met a username/password screen before the PIN pad. What protects the pad now, since it is on the open internet:

  - five wrong PINs from one address in fifteen minutes locks that address out (`PinFailure`);
  - a PIN session is a person, not a Django user, so it can never reach /admin/ (that still needs a staff
    account, and nothing here makes one);
  - it lapses after IDLE_MINUTES without a tap, so a phone left on the bar does not stay somebody.
"""

import json
import time
from datetime import timedelta
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from crm.geo import client_ip

from .models import PinFailure, Staff

PERSON_KEY = 'pos_staff'
SEEN_KEY = 'pos_seen'
# Minutes without a tap before the PIN is asked for again.
IDLE_MINUTES = 30


def current_staff(request):
    sid = request.session.get(PERSON_KEY)
    seen = request.session.get(SEEN_KEY, 0)
    if not sid or time.time() - seen > IDLE_MINUTES * 60:
        return None
    staff = Staff.objects.filter(pk=sid, active=True).first()
    if staff:
        request.session[SEEN_KEY] = time.time()
    return staff


def sign_in_staff(request, staff):
    request.session[PERSON_KEY] = staff.pk
    request.session[SEEN_KEY] = time.time()


def sign_out_staff(request):
    request.session.pop(PERSON_KEY, None)


def pos_required(view=None, *, manager=False, cashier=False, api=False):
    """A person must have typed a PIN. `manager`/`cashier` narrow it to those roles."""

    def decorate(fn):
        @wraps(fn)
        def guard(request, *args, **kwargs):
            staff = current_staff(request)
            if staff is None:
                if api:
                    return JsonResponse({'error': 'Escribe tu PIN.', 'pin': True}, status=401)
                return redirect(f'/pos/entrar/?next={request.path}')
            if manager and not staff.is_manager:
                if api:
                    return JsonResponse({'error': 'Solo el gerente.'}, status=403)
                return redirect('/pos/?denied=1')
            if cashier and not staff.can_charge:
                if api:
                    return JsonResponse({'error': 'Solo caja o gerente.'}, status=403)
                return redirect('/pos/?denied=1')
            request.staff = staff
            return fn(request, *args, **kwargs)

        return guard

    return decorate(view) if view else decorate


def authorizer(request, body=None):
    """The manager approving this action: the person signed in if they are one, else whoever's PIN was typed."""
    staff = getattr(request, 'staff', None)
    if staff and staff.is_manager:
        return staff
    body = body if body is not None else _body(request)
    pin = body.get('managerPin') or body.get('manager_pin')
    if not pin:
        return None
    # The PIN box in a dialog is a second place to guess one, so it shares the pad's lockout.
    if locked_out(request):
        return None
    found = Staff.by_pin(pin)
    if not (found and found.is_manager):
        record_failure(request)
        return None
    return found


def _body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or b'{}')
        except ValueError:
            return {}
    return request.POST


MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)


def locked_out(request):
    """Minutes left on this address's lockout, or 0."""
    since = timezone.now() - WINDOW
    recent = list(PinFailure.objects.filter(ip=client_ip(request) or '?', created_at__gte=since)
                  .order_by('created_at').values_list('created_at', flat=True))
    if len(recent) < MAX_FAILURES:
        return 0
    return max(1, int((recent[-MAX_FAILURES] + WINDOW - timezone.now()).total_seconds() // 60) + 1)


def record_failure(request):
    PinFailure.objects.create(ip=client_ip(request) or '?')
    PinFailure.objects.filter(created_at__lt=timezone.now() - WINDOW * 4).delete()


def clear_failures(request):
    PinFailure.objects.filter(ip=client_ip(request) or '?').delete()
