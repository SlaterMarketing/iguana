"""Confirmed opt-in: an address joins the mailing list only after somebody proves they can read it.

Written the night a bot was caught filling the newsletter form. All 59 sign-ups on the site came from one
machine: `timeZone: Europe/Moscow` on every one, `page: /en/`, `en-US`, arriving through Tor exits in Germany,
Sweden, the US and the Netherlands, paced at a median of 63 minutes so the rate never looked like a burst. The
addresses were scraped from elsewhere and belonged to real strangers at universities and companies.

Nothing about the payload could have caught that. The bot sends exactly what the real form sends, so any
server-side check on the shape of the request is a check it can satisfy. What it cannot do is read the mail.
The weekly newsletter was hours from being the first bulk send off a brand-new domain, straight to 59 people
who never asked for it, which is how a sending reputation is destroyed before it is built.

So the gate is the one gate a bot cannot pass: we send one email and wait. An unconfirmed address stays off
the list, gets no weekly mail and quietly expires. The token is the same signed-address machinery as the
unsubscribe link, with its own salt so neither link can be used as the other.
"""

from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage
from django.utils import timezone

from sales.i18n import normalize, tr

SALT = 'iguana.optin'
# Long enough that somebody who opens their mail at the weekend is still fine, short enough that a stale link
# from a year-old scrape cannot quietly add an address later.
MAX_AGE = timedelta(days=30)


def token_for(email):
    return signing.dumps({'email': str(email).strip().lower()}, salt=SALT, compress=True)


def email_from_token(token):
    """The address this token was made for, or None when it was not signed by us or has expired."""
    try:
        return signing.loads(token, salt=SALT, max_age=MAX_AGE.total_seconds())['email']
    except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError):
        return None


def confirm_url(email):
    base = str(getattr(settings, 'BACKEND_URL', '')).rstrip('/')
    return f'{base}/newsletter/confirm/{token_for(email)}'


def send_confirmation(email, lang='en'):
    """One email, asking them to confirm. Never goes through `crm.mail.send_marketing`: this is not marketing,
    it is the question of whether marketing is wanted, and it must not carry an unsubscribe footer for a list
    the person is not on yet."""
    lang = normalize(lang)
    body = '\n\n'.join([
        tr(lang, 'Hi there,'),
        tr(lang, 'Confirm you want our weekly email about what is on at Iguana Comedy:'),
        confirm_url(email),
        tr(lang, 'If you did not ask for this, ignore this email and nothing else will be sent.'),
        'Iguana Comedy\niguanacomedy.com',
    ])
    message = EmailMessage(
        subject=tr(lang, 'Confirm your email'),
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    return message.send(fail_silently=True)


def confirm(contact):
    """Called when the link is clicked. Only here does an address become mailable."""
    contact.subscribed = True
    contact.email_marketing_eligible = True
    contact.subscribed_at = contact.subscribed_at or timezone.now()
    contact.unsubscribed_at = None
    contact.save(update_fields=['subscribed', 'email_marketing_eligible', 'subscribed_at', 'unsubscribed_at'])
    return contact
