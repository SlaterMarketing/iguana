"""Send purchases and checkouts to Meta server-side, through the Conversions API.

The site has no browser purchase pixel and cannot have a useful one: checkout runs in an iframe served from
api.iguanacomedy.com, so a pixel on the marketing pages never sees the sale. Meta therefore learns what an ad is
worth only if the backend tells it. This module is that telling.

Server-side is also the only version that survives an ad blocker, which is most of the audience on a phone, so
Purchase and InitiateCheckout are sent from here and ONLY from here. The browser pixel on the Astro site sends
PageView and ViewContent and nothing else, which means there is no event to deduplicate and no dedup to get wrong.

Nothing here may break a booking. Every send happens on a background thread after the transaction commits, every
failure is logged and swallowed, and with no pixel or token configured the whole module is a no-op that says so
once. A customer must never fail to buy a seat because Meta was slow.
"""

import hashlib
import json
import logging
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

API_VERSION = 'v21.0'
TIMEOUT = 10

_warned = {'off': False}


def configured():
    return bool(getattr(settings, 'META_PIXEL_ID', '') and getattr(settings, 'META_CAPI_TOKEN', ''))


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _plain(value):
    """Lowercase, strip accents and punctuation: Meta hashes 'Playa del Carmen' as 'playadelcarmen'."""
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text.lower())


def hash_email(value):
    value = str(value or '').strip().lower()
    return _sha(value) if '@' in value else ''


def hash_phone(value):
    """Meta wants digits only, including the country code. A number with no country code cannot be matched, and
    guessing one is worse than sending nothing: a 10-digit Mexican and US number look identical."""
    raw = str(value or '').strip()
    digits = re.sub(r'\D', '', raw)
    if not raw.startswith('+') or len(digits) < 8:
        return ''
    return _sha(digits)


def hash_name(value):
    plain = _plain(value)
    return _sha(plain) if plain else ''


def hash_place(value):
    plain = _plain(value)
    return _sha(plain) if plain else ''


def hash_country(value):
    code = _plain(value)[:2]
    return _sha(code) if len(code) == 2 else ''


def user_data(*, email='', phone='', first_name='', last_name='', city='', region='', country='',
              ip='', user_agent='', fbp='', fbc=''):
    """The identity block. Hashed fields go in as one-element lists, plain ones (fbp, fbc, ip, ua) as strings.

    More matched fields means a higher event match quality, which is what decides whether Meta can attribute the
    sale to the ad at all. Empty fields are dropped rather than sent blank, which Meta scores against you.
    """
    hashed = {
        'em': hash_email(email),
        'ph': hash_phone(phone),
        'fn': hash_name(first_name),
        'ln': hash_name(last_name),
        'ct': hash_place(city),
        'st': hash_place(region),
        'country': hash_country(country),
    }
    data = {key: [value] for key, value in hashed.items() if value}
    for key, value in (('client_ip_address', ip), ('client_user_agent', user_agent), ('fbp', fbp), ('fbc', fbc)):
        if value:
            data[key] = str(value)
    return data


def _post(payload):
    pixel = getattr(settings, 'META_PIXEL_ID', '')
    body = {'data': json.dumps(payload), 'access_token': getattr(settings, 'META_CAPI_TOKEN', '')}
    test_code = getattr(settings, 'META_TEST_EVENT_CODE', '')
    if test_code:
        body['test_event_code'] = test_code
    url = f'https://graph.facebook.com/{API_VERSION}/{pixel}/events'
    request = urllib.request.Request(url, data=urllib.parse.urlencode(body).encode())
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            result = json.load(response)
        received = result.get('events_received')
        if received:
            log.info('Meta CAPI accepted %s event(s): %s', received, [e['event_name'] for e in payload])
        else:
            log.warning('Meta CAPI accepted nothing: %s', result)
    except urllib.error.HTTPError as exc:
        log.warning('Meta CAPI %s for %s: %s', exc.code, [e['event_name'] for e in payload],
                    exc.read().decode(errors='replace')[:300])
    except Exception as exc:  # noqa: BLE001 - a booking must never fail because Meta did
        log.warning('Meta CAPI send failed for %s: %s', [e['event_name'] for e in payload], exc)


def send(event_name, *, event_id, user, custom=None, source_url='', event_time=None, action_source='website'):
    """Queue one event. Returns immediately; the HTTP call runs on a daemon thread."""
    if not configured():
        if not _warned['off']:
            log.info('Meta CAPI is off: set META_PIXEL_ID and META_CAPI_TOKEN in config.py to report conversions')
            _warned['off'] = True
        return
    event = {
        'event_name': event_name,
        'event_time': int(event_time or time.time()),
        'event_id': str(event_id),
        'action_source': action_source,
        'user_data': user,
    }
    if source_url:
        event['event_source_url'] = source_url
    if custom:
        event['custom_data'] = custom
    threading.Thread(target=_post, args=([event],), daemon=True).start()
