"""Honour unsubscribe requests that arrive as EMAIL rather than as a click.

Two ways this happens and neither is exotic:

  A mail client picks the `mailto:` option out of `List-Unsubscribe` instead of the one-click URL. Apple Mail
  did exactly that on 2026-09-23: it sent "unsubscribe" to hello@, the mailbox nothing was reading, and the
  person stayed on the list. They had done everything right and would have received the next one.

  Somebody replies "unsubscribe" to any message we send. No header can catch that, and it is the commonest
  form of the request there is.

Ignoring either is a spam complaint waiting to happen, and a complaint costs the whole list's deliverability.

🚨 Matched on the SUBJECT only, never the body. Every newsletter carries the word "unsubscribe" in its own
footer, and a copy of each one is delivered to this very mailbox, so a body match would unsubscribe whoever
appears to have sent our own mail. Our own addresses are refused outright for the same reason.
"""

import mailbox
import re
from email.utils import parseaddr

from django.conf import settings
from django.core.management.base import BaseCommand

from crm.models import Contact
from crm.unsubscribe import stop_marketing

DEFAULT_MAILBOX = '/var/mail/inbox'

# The subject has to BE the request, not merely mention it.
ASKS = re.compile(r'^\s*(re:\s*)?(unsubscribe|desuscribir(me)?|darme de baja|baja|remove me|stop)\b', re.I)


def ours(address):
    """Never act on a message that looks like it came from us: our own newsletter is in this mailbox."""
    domain = address.rsplit('@', 1)[-1].lower()
    mine = {u.split('//')[-1].split('/')[0].lower() for u in getattr(settings, 'SITE_URLS', [])}
    mine |= {d.lstrip('www.') for d in mine}
    return any(domain == d or domain.endswith('.' + d) for d in mine if d)


class Command(BaseCommand):
    help = 'Unsubscribe anyone who emailed asking to be unsubscribed.'

    def add_arguments(self, parser):
        parser.add_argument('--mailbox', default=DEFAULT_MAILBOX)
        parser.add_argument('--apply', action='store_true', help='Actually unsubscribe (otherwise a dry run)')

    def handle(self, *args, **opts):
        try:
            box = mailbox.mbox(opts['mailbox'])
        except OSError as exc:
            self.stderr.write(f'cannot read {opts["mailbox"]}: {exc}')
            return

        asked, changed, unknown = set(), 0, []
        for message in box:
            subject = str(message.get('Subject', ''))
            if not ASKS.match(subject):
                continue
            address = parseaddr(str(message.get('From', '')))[1].strip().lower()
            if not address or ours(address):
                continue
            asked.add(address)

        for address in sorted(asked):
            contact = Contact.objects.filter(email__iexact=address).first()
            if contact is None:
                unknown.append(address)
                continue
            if not contact.subscribed:
                continue
            self.stdout.write(f'  unsubscribing {address}')
            if opts['apply']:
                stop_marketing(contact)
            changed += 1

        self.stdout.write(f'{len(asked)} asked by email, {changed} still needed it'
                          + ('' if opts['apply'] else ' (dry run, pass --apply)'))
        for address in unknown:
            # Worth seeing: somebody asking to leave a list they are not on usually means a forwarded copy.
            self.stdout.write(f'  not on the list: {address}')
