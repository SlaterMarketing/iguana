"""The link somebody sends a friend after reserving, and the message that goes with it.

A person who has just booked is the cheapest audience there is: they have already decided, they are about to
tell somebody anyway, and the seat they are recommending is free. This is the one moment where asking costs
nothing and the ask is easy to say yes to.

The link goes to the open mic lander pinned to the night they just booked, not to a generic page, so a friend
lands on one show with one form. It carries `ref=share` so the difference between shared traffic and bought
traffic is measurable rather than assumed.

WhatsApp first, because this is Playa del Carmen and that is where a plan between friends actually happens.
"""

from urllib.parse import quote

from django.conf import settings

from sales.i18n import normalize, tr

# Mirrors src/i18n/routes.ts, the same table crm/whats_on.py keeps. api.tests.WeeklyEmailTests holds it honest.
OPEN_MIC_PATH = {'en': '/en/open-mic/', 'es': '/es/open-mic/'}


def is_open_mic(event):
    return bool(event and 'open-mic' in (event.tags or []))


def share_url(order):
    """The page a friend should land on: this night, already chosen, nothing else to decide."""
    event = order.event
    if not is_open_mic(event):
        return ''
    base = (settings.SITE_URLS[0] if settings.SITE_URLS else settings.BACKEND_URL).rstrip('/')
    lang = normalize(order.locale)
    # `night` is the show's own language, `date` the exact night; the path prefix follows the SHARER's language,
    # since they are the one writing the message around it.
    night = normalize(getattr(event, 'language', '') or lang)
    day = event.date.astimezone().date().isoformat() if event.date else ''
    query = f'night={night}&ref=share' + (f'&date={day}' if day else '')
    return f'{base}{OPEN_MIC_PATH[lang]}?{query}'


def share_message(order, lang=None):
    """What they send. Written to be sent as-is, because a message somebody has to compose does not get sent."""
    lang = normalize(lang or order.locale)
    return tr(lang, 'I am going to the open mic at Iguana Comedy. Entry is free, reserve a seat here: {0}',
              share_url(order))


def whatsapp_url(order, lang=None):
    url = share_url(order)
    return f'https://wa.me/?text={quote(share_message(order, lang))}' if url else ''
