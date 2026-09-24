"""Honour unsubscribe requests that arrive as EMAIL rather than as a click.

Two ways this happens and neither is exotic:

  A mail client picks the `mailto:` option out of `List-Unsubscribe` instead of the one-click URL. Apple Mail
  did exactly that on 2026-09-23: it sent "unsubscribe" to hello@, the mailbox nothing was reading, and the
  person stayed on the list. They had done everything right and would have received the next one.

  Somebody replies "unsubscribe" to any message we send. No header can catch that, and it is the commonest
  form of the request there is.

Ignoring either is a spam complaint waiting to happen, and a complaint costs the whole list's deliverability.

🚨 The body is read, but only after the quoted part is cut away. Every newsletter carries the word
"unsubscribe" in its own footer and a copy of each one lands in this very mailbox, so a naive body match would
unsubscribe whoever appears to have sent our own mail. Three things make it safe: our own addresses are refused
outright, everything from the first quote marker or "On ... wrote:" line down is discarded, and what is left
has to be SHORT and has to contain a phrase that is the request rather than a mention of it.

That matters because the commonest real request is not a bare "unsubscribe" subject. It is somebody replying
to their own ticket email, subject still "Re: Tus boletos", with "ya no quiero recibir correos" in the body.
Subject-only matching read that as a normal reply and left them on the list.
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

# In the body the bar is higher, because a reply can mention anything. These are sentences somebody writes
# when they mean it, in both languages, since two thirds of this audience books in Spanish.
BODY_ASKS = re.compile(
    r'(remove me from|take me off|stop (sending|emailing)|no longer wish to receive|unsubscribe me'
    r'|please unsubscribe|d(?:a|á)r?me de baja|darse de baja|desuscrib|qu(?:i|í)tame de la lista'
    r'|ya no (?:quiero|deseo) recibir|no me (?:manden|env(?:i|í)en) m(?:a|á)s (?:correos|emails)'
    r'|cancelar (?:la )?suscripci(?:o|ó)n)', re.I)

# The bare word on its own is a request; the same word inside a sentence is a mention. "The footer says I can
# unsubscribe here" is somebody describing the email, not asking to leave it, and acting on that would remove
# a happy customer from the list for being polite.
BARE_ASK = re.compile(r'^\W*(unsubscribe|baja|stop|remove)\W*$', re.I)

# Where a reply stops being theirs and starts being ours quoted back. Anything from here down is discarded.
QUOTE_LINE = re.compile(
    r'^\s*(>|on .*wrote:|el .*escribi(?:o|ó):|-{2,}\s*original message|_{5,}|de:\s|from:\s)', re.I)

# A request is a sentence, not an essay. Past this many characters it is a conversation that happens to
# contain the word, and those should be read by a person rather than acted on by a cron.
MAX_BODY = 600


def own_words(message):
    """The part of a reply the sender actually typed, with our own mail quoted underneath cut away."""
    if message.is_multipart():
        part = next((p for p in message.walk() if p.get_content_type() == 'text/plain'), None)
    else:
        part = message
    if part is None:
        return ''
    try:
        raw = part.get_payload(decode=True)
        text = raw.decode(part.get_content_charset() or 'utf-8', 'ignore') if raw else str(part.get_payload())
    except Exception:
        return ''
    lines = []
    for line in text.splitlines():
        if QUOTE_LINE.match(line):
            break
        lines.append(line)
    return '\n'.join(lines).strip()


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
            address = parseaddr(str(message.get('From', '')))[1].strip().lower()
            if not address or ours(address):
                continue
            if ASKS.match(str(message.get('Subject', ''))):
                asked.add(address)
                continue
            body = own_words(message)
            if body and len(body) <= MAX_BODY and (BODY_ASKS.search(body) or BARE_ASK.match(body)):
                asked.add(address)

        for address in sorted(asked):
            contact = Contact.objects.filter(email__iexact=address).first()
            if contact is None:
                # Remember it anyway. They are not on the list today, but this address has been imported from
                # a spreadsheet once already and asking twice is how a person becomes a spam complaint.
                unknown.append(address)
                if opts['apply']:
                    contact = Contact.objects.create(email=address)
                    stop_marketing(contact)
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
            self.stdout.write(f'  was not on the list, remembered anyway: {address}')
