"""Which host a URL we generate should carry.

Two hosts serve this application and they are not interchangeable:

  `iguanacomedy.com` is where a PERSON is sent. A ticket link in a confirmation email, the QR a door scans, an
  unsubscribe link, the staff boards. `api.iguanacomedy.com` in an inbox reads as somebody else's domain, and
  it is the first thing a phishing filter looks at.

  `api.iguanacomedy.com` is where a BROWSER talks to us: the checkout iframe, k.js, /api/. The iframe is a
  separate origin on purpose, so that stays.

nginx serves the human paths on both hosts, so every QR already printed and every link already emailed keeps
working. Only what we generate from here on uses the short one.

Read at call time rather than frozen into a setting at import: `SITE_URLS` is the live value, and a setting
computed once cannot be overridden in a test, which is exactly how the first version of this went out wrong.
"""

from django.conf import settings


def public_base():
    """The host to put in front of anything a person will see or click."""
    urls = getattr(settings, 'SITE_URLS', None)
    return (urls[0] if urls else settings.BACKEND_URL).rstrip('/')


def order_url(order):
    return f'{public_base()}/orders/{order.public_view_token}/'


def checkin_url(ticket):
    return f'{public_base()}/checkin/{ticket.checkin_token}/'
