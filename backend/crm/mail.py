"""The only way to send marketing mail from here, so an unsubscribe link cannot be left off by accident.

Transactional mail (a ticket confirmation, a sign-in code) deliberately does not go through this: someone who
unsubscribes from the newsletter still needs the tickets they paid for, and putting an unsubscribe link on a
receipt teaches people to unsubscribe from receipts.
"""

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

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


def send_marketing(subject, body, contacts, dry_run=False):
    """Send one message to many contacts, each in their own language, one email per person.

    Returns (sent, skipped). A per-person send is slower than one big BCC, but it is what lets the footer and the
    List-Unsubscribe header name that person's own link, which is what Gmail's one-click button needs.
    """
    recipients = marketing_recipients(contacts)
    skipped = len(contacts) - len(recipients)
    if dry_run:
        return 0, skipped

    sent = 0
    connection = get_connection()
    for contact in recipients:
        lang = normalize(getattr(contact, 'locale', '') or 'en')
        message = EmailMessage(
            subject=tr(lang, subject),
            body=with_footer(body, contact.email, lang),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[contact.email],
            headers=bulk_headers(contact.email),
            connection=connection,
        )
        sent += message.send(fail_silently=True)
    return sent, skipped
