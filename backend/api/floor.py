"""Who may use the floor console, and why it is not the admin.

The people who need `/mesas/` are a waiter and whoever is on the bar. They need one board and a count sheet;
they do not need the Django admin, and on a shared phone behind a bar the admin is a liability rather than a
feature: it can edit events, refund orders, read every customer's address and delete rows that nothing else
can put back.

🚨 The gate is `is_staff = False`, not a permission list. Django's admin refuses a non-staff account at the
login form itself, before any permission is consulted, so `/admin/` is closed by construction rather than by
remembering to withhold every model permission one at a time. Adding a model permission to a floor account
later cannot accidentally open the admin, because the admin never gets as far as looking.

That is also why this module exists instead of `staff_member_required`: floor accounts have to be turned away
from the admin AND let into `/mesas/`, which is exactly the combination that decorator cannot express.
"""

from functools import wraps

from django.contrib.auth.models import Group
from django.shortcuts import redirect

FLOOR_GROUP = 'Floor'
LOGIN_URL = '/mesas/entrar/'


def floor_group():
    group, _ = Group.objects.get_or_create(name=FLOOR_GROUP)
    return group


def is_floor(user):
    """Floor staff, or anybody with admin rights (the owner still has to be able to look at the board)."""
    if not (user and user.is_authenticated and user.is_active):
        return False
    return user.is_staff or user.groups.filter(name=FLOOR_GROUP).exists()


def floor_required(view):
    """Let floor staff and admins through, and send everybody else to the floor login, never the admin one.

    A floor account that lands on `/admin/login/` is told its credentials are wrong, which is true only in the
    sense that matters least: they are correct, that door is simply not theirs. Sending them somewhere that
    works is the difference between a login and a support call in the middle of service.
    """

    @wraps(view)
    def guard(request, *args, **kwargs):
        if is_floor(request.user):
            return view(request, *args, **kwargs)
        return redirect(f'{LOGIN_URL}?next={request.path}')

    return guard
