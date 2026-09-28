"""Two locks, as in Soft Restaurant: the DEVICE, and the PERSON.

The tablet is signed in as a floor account (api/floor.py), which is what keeps /admin/ shut on a phone behind a
bar. On top of that, whoever is using it types their PIN: that is who every check, void and payment is recorded
against. The PIN session is short on purpose (a waiter walks away and the next person must not be them), while
the device session stays signed in for a year.
"""

import json
import time
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect

from api.floor import is_floor

from .models import Staff

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
    """The device must be a floor login and a person must have typed a PIN. `manager`/`cashier` narrow it."""

    def decorate(fn):
        @wraps(fn)
        def guard(request, *args, **kwargs):
            if not is_floor(request.user):
                if api:
                    return JsonResponse({'error': 'Esta tableta no ha iniciado sesión.'}, status=401)
                return redirect(f'/mesas/entrar/?next={request.path}')
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
    found = Staff.by_pin(body.get('managerPin') or body.get('manager_pin'))
    return found if found and found.is_manager else None


def _body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or b'{}')
        except ValueError:
            return {}
    return request.POST
