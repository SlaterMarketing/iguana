"""Create or repair the floor console's accounts: `/mesas/` and nothing else.

A command rather than a line of python inside the deploy playbook, because this decides who can log in and
that deserves to be readable and to have a test. The inline `manage.py shell -c` one-liners elsewhere in
`deploy.yml` predate this and are not a pattern worth extending.

🚨 It FORCES `is_staff = False` and `is_superuser = False` every run, and that is the point rather than
housekeeping. Django's admin refuses a non-staff account at the login form, before it consults a single
permission, so `/admin/` is closed by construction instead of by remembering to withhold every model
permission one at a time. Somebody ticking "staff status" in the admin to be helpful is the realistic way
that protection disappears, and the next deploy takes it straight back off.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from api.floor import FLOOR_GROUP, floor_group

# A waiter, the bar and the door. Named for the job rather than the person, because the phone is shared and
# the person on it changes; an account per human would mean a new account every few weeks and a password
# nobody knows.
USERNAMES = ('mesero', 'bar', 'door')


class Command(BaseCommand):
    help = 'Create or repair the mesero and bar accounts for /mesas/.'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True, help='Shared floor password.')
        parser.add_argument('--usernames', nargs='*', default=list(USERNAMES))

    def handle(self, *args, **opts):
        User = get_user_model()
        group = floor_group()
        for username in opts['usernames']:
            user, created = User.objects.get_or_create(username=username)
            demoted = user.is_staff or user.is_superuser
            user.is_staff = False
            user.is_superuser = False
            user.is_active = True
            user.set_password(opts['password'])
            user.save()
            user.groups.add(group)
            note = 'created' if created else ('demoted from staff' if demoted else 'already there')
            self.stdout.write(f'  {username}: {note}, group {FLOOR_GROUP}, admin closed')
        self.stdout.write(f'{len(opts["usernames"])} floor account(s) ready for /mesas/')
