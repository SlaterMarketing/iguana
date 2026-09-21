"""The only way to send marketing mail from here, so an unsubscribe link cannot be left off by accident.

Transactional mail (a ticket confirmation, a sign-in code) deliberately does not go through this: someone who
unsubscribes from the newsletter still needs the tickets they paid for, and putting an unsubscribe link on a
receipt teaches people to unsubscribe from receipts.
"""

import time

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone

from sales.i18n import normalize, tr

from .unsubscribe import bulk_headers, unsubscribe_url


def marketing_recipients(contacts):
    """Only people who are still opted in. Anyone unsubscribed is dropped here rather than at the send site."""
    return [c for c in contacts if c.subscribed and c.email_marketing_eligible and c.email]


def with_footer(body, email, lang):
    """Every marketing message ends the same way: why they got it, and how to stop it."""
    return '\n\n'.join([
        body.rstrip(),
        '-- ',
        tr(lang, 'You are receiving this because you signed up at iguanacomedy.com.'),
        tr(lang, 'Unsubscribe: {0}', unsubscribe_url(email)),
    ])


def _resolve(value, lang, contact):
    """A subject or body may be a plain string, or a function of the language, or of both.

    A fixed string goes through `tr()` so it is translated like everything else. Anything that has to be built
    per person, such as the weekly what-is-on mail whose links are marked with the reader, passes a callable
    instead, because there is no single string to translate.
    """
    if callable(value):
        try:
            return value(lang, contact)
        except TypeError:
            return value(lang)
    return tr(lang, value)


def send_marketing(subject, body, contacts, dry_run=False, campaign=None, rate=0.0):
    """Send one message to many contacts, each in their own language, one email per person.

    Returns (sent, skipped). A per-person send is slower than one big BCC, but it is what lets the footer and the
    List-Unsubscribe header name that person's own link, which is what Gmail's one-click button needs.

    `campaign` records who it actually went to, so a second run can tell. `rate` puts a pause between messages:
    this box delivers its own mail and a few hundred at once is a spike worth flattening.
    """
    from .models import CampaignRecipient

    recipients = marketing_recipients(contacts)
    skipped = len(contacts) - len(recipients)
    if dry_run:
        return 0, skipped

    sent = 0
    connection = get_connection()
    for index, contact in enumerate(recipients):
        lang = normalize(getattr(contact, 'locale', '') or 'en')
        message = EmailMessage(
            subject=_resolve(subject, lang, contact),
            body=with_footer(_resolve(body, lang, contact), contact.email, lang),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[contact.email],
            # A newsletter people cannot reply to is a newsletter that loses the reply. Receipts keep no-reply.
            reply_to=[settings.MARKETING_REPLY_TO] if getattr(settings, 'MARKETING_REPLY_TO', '') else None,
            headers=bulk_headers(contact.email),
            connection=connection,
        )
        delivered = message.send(fail_silently=True)
        sent += delivered
        if campaign is not None:
            CampaignRecipient.objects.create(
                campaign=campaign, contact=contact, email=contact.email,
                status='SENT' if delivered else 'FAILED',
                sent_at=timezone.now() if delivered else None, send_attempts=1,
            )
        if rate and index + 1 < len(recipients):
            time.sleep(rate)
    return sent, skipped
