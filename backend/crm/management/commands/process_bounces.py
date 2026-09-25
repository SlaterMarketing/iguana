"""Stop mailing addresses that have permanently failed, and only those.

Every Monday the newsletter goes to everyone on the list, and some of that list is four years of spreadsheet
imports. Addresses in it have been closed, mistyped or abandoned. Nothing was reading the bounces, so those
dead addresses were mailed again every week, and one of them had already bounced twice by the time this was
written. (Deliberately not named: this repository is public and the address belongs to a real person.)
Gmail and Yahoo both weigh hard-bounce RATE when deciding whether a sender reaches the inbox, so a handful of
dead rows quietly taxes delivery to the 600 people who are real.

🚨 A permanent failure is not automatically the recipient's fault, and acting on the 5 is how you unsubscribe
people who did nothing wrong. Measured on this box the day this was written: of 24 bounces, ten were `5.1.1`
(the address does not exist) and ten were `5.7.1`, which is Gmail refusing OUR IPv4 because 38.86.78.0/24 is
on the Spamhaus PBL. Both are `5.x.x` and both arrive in the same envelope. Treating them alike would have
removed ten live subscribers for the sin of being mailed from a listed IP, and the list would have shrunk
every time our own reputation slipped, which is exactly backwards.

So only the codes that mean "no such mailbox" act. Everything else permanent is printed and left alone,
because it is either about us (policy, reputation, rate limits) or about a condition that ends (a full
mailbox). A wrong unsubscribe is invisible and unrecoverable: nobody reports the newsletter they stopped
getting.
"""

import mailbox
import re
from email.utils import parseaddr

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import CampaignRecipient, Contact
from crm.unsubscribe import stop_marketing

from .process_unsubscribe_mail import DEFAULT_MAILBOX, ours

# The mailbox does not exist and never will: the only family where the address itself is the problem.
# 5.1.1 unknown user, 5.1.0 bad address, 5.1.3 bad syntax, 5.1.6 mailbox moved with no forwarding.
DEAD = ('5.1.1', '5.1.0', '5.1.3', '5.1.6')

ADDRESS = re.compile(r'(?:rfc822|utf-8);\s*(.+)', re.I)


def _recipients(message):
    """Every (address, status, action) the delivery-status part of a DSN reports.

    Postfix writes a structured `message/delivery-status` part on every bounce it generates, so the codes are
    read from there rather than scraped out of the human-readable paragraph above it. That paragraph quotes
    the remote server verbatim, and a remote server is free to word it however it likes.
    """
    found = []
    for part in message.walk():
        if part.get_content_type() != 'message/delivery-status':
            continue
        # The part holds one header block per recipient, after a per-message block.
        for block in part.get_payload():
            address = block.get('Final-Recipient') or block.get('Original-Recipient') or ''
            match = ADDRESS.search(str(address))
            if not match:
                continue
            status = str(block.get('Status', '')).strip()
            action = str(block.get('Action', '')).strip().lower()
            found.append((parseaddr(match.group(1).strip())[1].lower(), status, action))
    return found


class Command(BaseCommand):
    help = 'Unsubscribe addresses that permanently do not exist, from the bounces in the local mailbox.'

    def add_arguments(self, parser):
        parser.add_argument('--mailbox', default=DEFAULT_MAILBOX)
        parser.add_argument('--apply', action='store_true', help='Actually unsubscribe (otherwise a dry run)')

    def handle(self, *args, **opts):
        try:
            box = mailbox.mbox(opts['mailbox'])
        except OSError as exc:
            self.stderr.write(f'cannot read {opts["mailbox"]}: {exc}')
            return

        dead, other = {}, {}
        for message in box:
            for address, status, action in _recipients(message):
                if not address or ours(address) or action != 'failed':
                    continue
                if status.startswith(DEAD):
                    dead[address] = status
                elif status.startswith('5.'):
                    other.setdefault(address, status)

        changed = 0
        for address, status in sorted(dead.items()):
            contact = Contact.objects.filter(email__iexact=address).first()
            if contact is None or not contact.subscribed:
                continue
            self.stdout.write(f'  {status}  no such mailbox, unsubscribing {address}')
            if opts['apply']:
                stop_marketing(contact)
                if 'hard-bounce' not in (contact.tags or []):
                    contact.tags = (contact.tags or []) + ['hard-bounce']
                    contact.save(update_fields=['tags'])
                (CampaignRecipient.objects.filter(email__iexact=address, bounced_at__isnull=True)
                 .update(bounced_at=timezone.now()))
            changed += 1

        self.stdout.write(f'{len(dead)} addresses do not exist, {changed} were still being mailed'
                          + ('' if opts['apply'] else ' (dry run, pass --apply)'))
        for address, status in sorted(other.items()):
            # Permanent, but about us or about a condition that passes. Printed so somebody can see a pattern
            # forming: a run of 5.7.x is our own reputation, not their mailboxes.
            self.stdout.write(f'  {status}  left alone (not the address): {address}')
