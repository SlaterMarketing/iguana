"""Entrar y salir de la consola de piso.

A login of its own, rather than the admin's. `/admin/login/` refuses a non-staff account with "please enter a
correct username and password", which for these two accounts is misleading: the password IS correct, that
door is simply not theirs. A waiter reading that at the start of service concludes the account is broken and
calls somebody.
"""

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .floor import is_floor

HOME = '/mesas/'


def _safe_next(raw):
    """Only ever our own floor paths, so a crafted `?next=` cannot bounce somebody off the site."""
    if raw and raw.startswith('/mesas'):
        return raw
    return HOME


@csrf_protect
def sign_in(request):
    destination = _safe_next(request.GET.get('next') or request.POST.get('next'))
    if is_floor(request.user):
        return redirect(destination)
    error = ''
    if request.method == 'POST':
        user = authenticate(request,
                            username=(request.POST.get('username') or '').strip(),
                            password=request.POST.get('password') or '')
        if user is None or not is_floor(user):
            # One message for both cases on purpose: naming which half was wrong tells somebody guessing
            # which usernames exist.
            error = 'Usuario o contraseña incorrectos.'
        else:
            login(request, user)
            return redirect(destination)
    return render(request, 'floor/entrar.html', {'error': error, 'next': destination})


@require_POST
def sign_out(request):
    """Still here, but deliberately NOT offered as a button anywhere on the console.

    These run on tablets that live in the building and are meant to stay signed in across shifts. A `Salir`
    sitting in the nav beside Mesas and Carta is a mis-tap away at all times, and the cost of that mis-tap is
    somebody hunting for a password behind a bar mid-service. Signing out is a deliberate act: POST to this
    path, or use the admin's own logout, which is where the owner signs out anyway.
    """
    logout(request)
    return redirect('/mesas/entrar/')
