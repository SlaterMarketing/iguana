"""Email a contact list, with the unsubscribe link attached automatically.

    manage.py send_newsletter --list Newsletter --subject "New shows on sale" --body-file note.txt --dry-run
    manage.py send_newsletter --list Newsletter --subject "New shows on sale" --body-file note.txt --send

Dry run by default: it prints who would receive it and stops. `--send` is the only way to actually deliver, so a
mistyped list name cannot email the wrong people. Anyone unsubscribed is skipped by `crm.mail`, not here.
"""

import pathlib

from django.core.management.base import BaseCommand, CommandError

from crm.mail import marketing_recipients, send_marketing
from crm.models import Contact, ContactList


class Command(BaseCommand):
    help = 'Send a newsletter to a contact list'

    def add_arguments(self, parser):
        parser.add_argument('--list', dest='list_name', required=True, help='Contact list name, e.g. Newsletter')
        parser.add_argument('--subject', required=True)
        parser.add_argument('--body-file', required=True, type=pathlib.Path)
        parser.add_argument('--send', action='store_true', help='Actually deliver (otherwise it is a dry run)')

    def handle(self, *args, **opts):
        contact_list = ContactList.objects.filter(name__iexact=opts['list_name']).first()
        if not contact_list:
            names = ', '.join(ContactList.objects.values_list('name', flat=True)[:20]) or 'none'
            raise CommandError(f'No contact list called {opts["list_name"]!r}. There is: {names}')
        body = opts['body_file'].read_text().strip()
        if not body:
            raise CommandError(f'{opts["body_file"]} is empty')

        contacts = list(Contact.objects.filter(lists=contact_list).distinct())
        eligible = marketing_recipients(contacts)
        self.stdout.write(f'{contact_list.name}: {len(contacts)} on the list, {len(eligible)} still subscribed')

        if not opts['send']:
            for contact in eligible[:10]:
                self.stdout.write(f'  would email {contact.email}')
            if len(eligible) > 10:
                self.stdout.write(f'  ... and {len(eligible) - 10} more')
            self.stdout.write(self.style.WARNING('Dry run. Pass --send to deliver.'))
            return

        sent, skipped = send_marketing(opts['subject'], body, contacts)
        self.stdout.write(self.style.SUCCESS(f'sent {sent}, skipped {skipped} unsubscribed'))
