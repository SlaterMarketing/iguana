"""Send a test email through the configured backend as DEFAULT_FROM_EMAIL (the identity real mail uses)."""
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('recipients', nargs='+')
        parser.add_argument('--subject', default='Iguana Comedy mail test')

    def handle(self, recipients, subject, **options):
        token = get_random_string(12)
        body = (
            'This is a delivery test from the Iguana Comedy site.\n\n'
            f'Sent {timezone.now().isoformat(timespec="seconds")} from {settings.BACKEND_URL}.\n'
            f'Test token: {token}\n\nIguana Comedy\niguanacomedy.mx\n'
        )
        connection = get_connection()
        sent = 0
        for to in recipients:
            domain = settings.DEFAULT_FROM_EMAIL.rsplit('@', 1)[-1].strip('> ')
            message_id = f'<mailtest-{token}-{sent}@{domain}>'
            message = EmailMessage(f'{subject} [{token}]', body, settings.DEFAULT_FROM_EMAIL, [to], connection=connection,
                                   headers={'Message-ID': message_id})
            sent += message.send()
            self.stdout.write(f'queued to={to} from={settings.DEFAULT_FROM_EMAIL} message_id={message_id} token={token}')
        if sent != len(recipients):
            raise SystemExit(f'only {sent} of {len(recipients)} messages were accepted by the backend')
        self.stdout.write(self.style.SUCCESS(f'sent={sent} token={token}'))
