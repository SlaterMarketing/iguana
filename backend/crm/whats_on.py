"""The weekly "what is on" email: what it says, in both languages, built from what is actually on sale.

Written from the calendar rather than by hand every Monday, because a newsletter somebody has to write is a
newsletter that stops going out in week three. If there is nothing on, there is no email: a weekly send with
nothing in it trains people to ignore the ones that matter.

The recipients are mostly a Kintana-era ticket list and 92% of them have no language recorded, so the mail
carries BOTH languages every time, with the reader's own first when we know it. Guessing wrong and sending
somebody a mail they cannot read is worse than a mail that is twice as long.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings

from catalog.models import Event
from sales.i18n import normalize, tr

from .email_links import tag

CANCUN = ZoneInfo('America/Cancun')
OPEN_MIC_TAG = 'open-mic'

# Mirrors src/i18n/routes.ts. `api.tests.WeeklyEmailTests` reads that file and fails if these drift apart, because
# a dead link in a newsletter is only ever found by the person who clicked it.
PATHS = {
    'openMic': {'en': '/en/open-mic/', 'es': '/es/open-mic/'},
    'events': {'en': '/en/events/', 'es': '/es/eventos/'},
    'eventDetail': {'en': '/en/events/{slug}/', 'es': '/es/eventos/{slug}/'},
}

DATE_FORMATS = {'en': '%A %-d %B', 'es': '%A %-d de %B'}
WEEKDAYS_ES = {'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles', 'Thursday': 'jueves',
               'Friday': 'viernes', 'Saturday': 'sábado', 'Sunday': 'domingo'}
MONTHS_ES = {'January': 'enero', 'February': 'febrero', 'March': 'marzo', 'April': 'abril', 'May': 'mayo',
             'June': 'junio', 'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
             'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'}


def site_url(path, contact=None):
    """A link into the site, marked so a click tells us which language this person actually reads."""
    base = (settings.SITE_URLS[0] if settings.SITE_URLS else settings.BACKEND_URL).rstrip('/')
    return tag(f'{base}{path}', contact)


def format_day(when, lang):
    """"Tuesday 22 September" / "martes 22 de septiembre". Django's date filter needs an active locale and a
    request; this is a cron with neither, so the two month and weekday tables live here."""
    text = when.strftime(DATE_FORMATS[lang])
    if lang == 'es':
        for english, spanish in {**WEEKDAYS_ES, **MONTHS_ES}.items():
            text = text.replace(english, spanish)
        return text.lower()
    return text


def format_time(value, lang):
    """"20:00" -> "8:00 pm". The times are stored on a 24h clock and nobody in Playa reads them that way."""
    try:
        hour, minute = (int(part) for part in str(value).split(':')[:2])
    except (TypeError, ValueError):
        return ''
    suffix = 'am' if hour < 12 else 'pm'
    return f'{hour % 12 or 12}:{minute:02d} {suffix}'


def price_from(event):
    """The cheapest live ticket, as "50 MXN". None when the show has no priced ticket type."""
    prices = [t.price_cents for t in event.ticket_types.filter(active=True) if t.price_cents]
    if not prices:
        return None
    cents = min(prices)
    amount = f'{cents / 100:,.2f}'.rstrip('0').rstrip('.')
    return f'{amount} {event.currency.upper()}'


def week_events(start=None, days=7):
    """Everything on sale between today and `days` from now, in the Cancun calendar, soonest first."""
    today = start or dt.datetime.now(CANCUN).date()
    since = dt.datetime.combine(today, dt.time.min, tzinfo=CANCUN)
    until = dt.datetime.combine(today + dt.timedelta(days=days), dt.time.max, tzinfo=CANCUN)
    events = (Event.objects.filter(date__gte=since, date__lte=until, status=Event.ACTIVE)
              .prefetch_related('ticket_types').order_by('date'))
    return [e for e in events if e.is_public]


def _open_mic_block(event, lang, contact=None):
    when = event.date.astimezone(CANCUN)
    lines = [f'{format_day(when, lang)} · {event.label(lang)}']
    doors, show = format_time(event.doors_open, lang), format_time(event.show_time, lang)
    if doors and show:
        # The Spanish night calls it a sign-up list rather than doors, which is what its own flyer says.
        opens = tr(lang, 'Sign-up list {0}, show {1}. Free entry.', doors, show) if event.language == 'es' \
            else tr(lang, 'Doors {0}, show {1}. Free entry.', doors, show)
        lines.append(opens)
    price = price_from(event)
    if price:
        lines.append(tr(lang, 'Hold your seat for {0}, a free drink included: {1}',
                        price, site_url(PATHS['openMic'][lang], contact)))
    return '\n'.join(lines)


def _show_block(event, lang, contact=None):
    when = event.date.astimezone(CANCUN)
    lines = [f'{format_day(when, lang)} · {event.label(lang)}']
    show = format_time(event.show_time, lang)
    if show:
        lines.append(tr(lang, 'Show {0}.', show))
    link = site_url(PATHS['eventDetail'][lang].format(slug=event.slug), contact)
    price = price_from(event)
    lines.append(tr(lang, 'Tickets from {0}: {1}', price, link) if price else tr(lang, 'Details: {0}', link))
    return '\n'.join(lines)


def body_for(events, lang, lede='', contact=None):
    """The message in one language. `lede` is a line for the top, for a week that needs one."""
    lang = normalize(lang)
    blocks = [tr(lang, 'Hi there,')]
    if lede:
        blocks.append(lede)
    blocks.append(tr(lang, 'This week at Iguana Comedy, Playa del Carmen:'))
    for event in events:
        blocks.append(_open_mic_block(event, lang, contact) if OPEN_MIC_TAG in (event.tags or [])
                      else _show_block(event, lang, contact))
    blocks.append(tr(lang, 'Everything that is on: {0}', site_url(PATHS['events'][lang], contact)))
    blocks.append(tr(lang, 'See you at the club,'))
    blocks.append('Iguana Comedy')
    return '\n\n'.join(blocks)


def body(events, contact=None, lede_en='', lede_es=''):
    """Both languages in one message, the reader's own first when we know it.

    Separated by a rule rather than a heading, because a heading that says "English" is one more thing that has
    to be translated and one more thing to get wrong.

    Every link is marked with the contact, so whichever block they click from records the language they read and
    the blank locale on most of this list fills itself in over a few sends.
    """
    known = normalize(getattr(contact, 'locale', '')) if getattr(contact, 'locale', '') else 'en'
    second = 'es' if known == 'en' else 'en'
    ledes = {'en': lede_en, 'es': lede_es}
    return '\n\n- - -\n\n'.join(body_for(events, lang, ledes[lang], contact) for lang in (known, second))


def subject(events, lang):
    """Named after the biggest ticketed show of the week when there is one, since that is what sells."""
    lang = normalize(lang)
    ticketed = [e for e in events if OPEN_MIC_TAG not in (e.tags or [])]
    if ticketed:
        return tr(lang, 'This week at Iguana Comedy: {0}', ticketed[0].label(lang))
    return tr(lang, 'This week at Iguana Comedy: open mic Tuesday and Wednesday')
