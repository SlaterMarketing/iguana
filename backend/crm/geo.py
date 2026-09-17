"""Who is signing up or booking, and from where: language, browser time zone and IP location.

IP location uses the DB-IP "IP to City Lite" database (CC BY 4.0, https://db-ip.com), downloaded to settings.GEOIP_DB
and refreshed monthly by ansible (`iguana-geoip-refresh`). If the file is missing, lookups return nothing and log one
warning: a sign-up or a checkout must never fail because a location could not be looked up.
"""

import ipaddress
import logging
import os
import threading

from django.conf import settings

log = logging.getLogger(__name__)

LOOPBACK = ('127.0.0.1', '::1')


def client_ip(request):
    # nginx proxies every request and sets X-Real-IP to the connecting address (files/iguana_proxy_params). Trust it
    # only when the request really came through that local proxy, or anyone could claim any address.
    remote = request.META.get('REMOTE_ADDR', '')
    if remote in LOOPBACK:
        real = request.headers.get('X-Real-IP', '').strip()
        if real:
            return real
    return remote


_state = {'mtime': None, 'reader': None, 'warned': False}
_lock = threading.Lock()


def _reader():
    """The open database, reopened when the monthly refresh replaces the file, so no app restart is needed."""
    path = getattr(settings, 'GEOIP_DB', '')
    try:
        mtime = os.stat(path).st_mtime
        with _lock:
            if mtime != _state['mtime']:
                import maxminddb

                _state['reader'], _state['mtime'] = maxminddb.open_database(path), mtime
            return _state['reader']
    except (ImportError, OSError, ValueError) as exc:
        if not _state['warned']:
            log.warning('IP location lookups are off: cannot open GEOIP_DB %r (%s)', path, exc)
            _state['warned'] = True
        return None


def locate(ip):
    """{'country': 'MX', 'region': 'Quintana Roo', 'city': 'Playa del Carmen'}, or {} when unknown."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return {}
    if not address.is_global:
        return {}
    reader = _reader()
    if reader is None:
        return {}
    record = reader.get(ip) or {}
    english = lambda node: ((node or {}).get('names') or {}).get('en', '')
    found = {
        'country': (record.get('country') or {}).get('iso_code', ''),
        'region': english((record.get('subdivisions') or [{}])[0]),
        'city': english(record.get('city')),
    }
    return {key: value for key, value in found.items() if value}


def visitor_profile(request, *, locale='', browser_language='', time_zone=''):
    ip = client_ip(request)
    profile = {'ip': ip, 'locale': str(locale or '')[:5], 'browserLanguage': str(browser_language or '')[:35],
               'timeZone': str(time_zone or '')[:60], **locate(ip)}
    return {key: value for key, value in profile.items() if value}


CONTACT_FIELDS = (('locale', 'locale'), ('browser_language', 'browserLanguage'), ('time_zone', 'timeZone'),
                  ('geo_country', 'country'), ('geo_region', 'region'), ('geo_city', 'city'), ('last_ip', 'ip'))


def remember_on_contact(contact, profile):
    """Keep the latest language and location on the contact, so campaigns can target by language and area."""
    changed = False
    for attr, key in CONTACT_FIELDS:
        value = profile.get(key)
        if value and getattr(contact, attr) != value:
            setattr(contact, attr, value)
            changed = True
    if changed:
        contact.save()
