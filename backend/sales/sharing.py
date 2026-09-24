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
from zoneinfo import ZoneInfo

from django.conf import settings

from sales.i18n import normalize, tr

# Mirrors src/i18n/routes.ts, the same table crm/whats_on.py keeps. api.tests.WeeklyEmailTests holds it honest.
OPEN_MIC_PATH = {'en': '/en/open-mic/', 'es': '/es/open-mic/'}
CANCUN = ZoneInfo('America/Cancun')
EVENT_PATH = {'en': '/en/events/{slug}/', 'es': '/es/eventos/{slug}/'}
EVENTS_PATH = {'en': '/en/events/', 'es': '/es/eventos/'}


def is_open_mic(event):
    return bool(event and 'open-mic' in (event.tags or []))


def base_url():
    return (settings.SITE_URLS[0] if settings.SITE_URLS else settings.BACKEND_URL).rstrip('/')


def is_past(event):
    """Past means the night is OVER, judged by the Cancun calendar day.

    Comparing the stored timestamp against now made every show past from midnight, so the share block vanished
    on the morning of the show: the one day people are actually telling their friends about it.
    """
    from django.utils import timezone

    if not event or not event.date:
        return False
    return event.date.astimezone(CANCUN).date() < timezone.now().astimezone(CANCUN).date()


def share_url(order):
    """The page a friend should land on: this night, already chosen, nothing else to decide.

    A paid show shares its own page rather than the open mic lander, because that is where the friend can buy
    the thing being recommended. Somebody who has just spent 600 pesos on two tickets is at least as willing to
    tell people as somebody who reserved a free seat, and until now we asked only the free one.
    """
    event = order.event
    if not event or is_past(event):
        return ''
    if not is_open_mic(event):
        return f'{base_url()}{EVENT_PATH[normalize(order.locale)].format(slug=event.slug)}?ref=share' if event.slug else ''
    base = base_url()
    lang = normalize(order.locale)
    # `night` is the show's own language, `date` the exact night; the path prefix follows the SHARER's language,
    # since they are the one writing the message around it.
    night = normalize(getattr(event, 'language', '') or lang)
    day = event.date.astimezone().date().isoformat() if event.date else ''
    query = f'night={night}&ref=share' + (f'&date={day}' if day else '')
    return f'{base}{OPEN_MIC_PATH[lang]}?{query}'


def share_is_free(order):
    """Whether what they are passing on is a free seat. The copy promises different things either way."""
    return is_open_mic(order.event)


def share_message(order, lang=None):
    """What they send. Written to be sent as-is, because a message somebody has to compose does not get sent."""
    lang = normalize(lang or order.locale)
    url = share_url(order)
    if not url:
        return ''
    if is_open_mic(order.event):
        return tr(lang, 'I am going to the open mic at Iguana Comedy. Entry is free, reserve a seat here: {0}', url)
    return tr(lang, 'I am going to see {0} at Iguana Comedy. Tickets here: {1}', order.event_name, url)


def whatsapp_url(order, lang=None):
    url = share_url(order)
    return f'https://wa.me/?text={quote(share_message(order, lang))}' if url else ''
