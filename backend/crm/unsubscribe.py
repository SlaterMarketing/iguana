"""One-click unsubscribe: a signed link that needs no account and never expires.

Anything we send in bulk has to carry a way out, both because it is the law where our audience lives and because
Gmail and Yahoo require `List-Unsubscribe` from bulk senders: without it our mail lands in spam and the ticket
confirmations suffer with it. The token signs the email address, so a link cannot be edited to unsubscribe someone
else, and it stays valid forever because an old newsletter is exactly where people click it.
"""

from django.conf import settings
from django.core import signing
from django.utils import timezone

SALT = 'iguana.unsubscribe'


def token_for(email):
    return signing.dumps({'email': str(email).strip().lower()}, salt=SALT, compress=True)


def email_from_token(token):
    """The address the token was made for, or None when it was not signed by us."""
    try:
        return signing.loads(token, salt=SALT)['email']
    except (signing.BadSignature, KeyError, TypeError):
        return None


def unsubscribe_url(email):
    base = str(getattr(settings, 'BACKEND_URL', '')).rstrip('/')
    return f'{base}/unsubscribe/{token_for(email)}'


def stop_marketing(contact):
    """Off the marketing list, but still reachable about a ticket they already bought."""
    contact.subscribed = False
    contact.email_marketing_eligible = False
    contact.unsubscribed_at = timezone.now()
    contact.save(update_fields=['subscribed', 'email_marketing_eligible', 'unsubscribed_at'])


def resume_marketing(contact):
    contact.subscribed = True
    contact.email_marketing_eligible = True
    contact.subscribed_at = timezone.now()
    contact.unsubscribed_at = None
    contact.save(update_fields=['subscribed', 'email_marketing_eligible', 'subscribed_at', 'unsubscribed_at'])


def bulk_headers(email):
    """Headers every bulk send needs. The Post header is what makes Gmail's own one-click button work."""
    return {
        'List-Unsubscribe': f'<{unsubscribe_url(email)}>, <mailto:hello@iguanacomedy.com?subject=unsubscribe>',
        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    }
