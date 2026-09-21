#!/usr/bin/env python3
"""Put the customer list into Meta as a Custom Audience, and build a lookalike from it.

This is the only thing that can actually be "imported" into a new pixel. A pixel's event history cannot be
moved or copied: the Conversions API refuses any event older than seven days, so there is nothing to backfill,
and the old "Ticket Tracking" pixel last fired in May, which is outside every window Meta optimises on anyway.
A customer list is different. It is ours, it does not expire, and it gives a cold pixel a warm start.

Addresses and phone numbers are hashed ON THE SERVER and only hashes ever leave it, so no customer PII lands on
the dev box or in this repo. Meta is sent sha256 of the normalised value, which is exactly what it hashes its own
users with; it cannot reverse them, and neither can we.

    scripts/meta-audiences.py build            create or refresh the customer audience
    scripts/meta-audiences.py build --lookalike  also build a 1% Mexico lookalike from it
    scripts/meta-audiences.py status           audience sizes and when they last filled

The lookalike is deliberately not wired into any ad set yet. At 100 MXN a day an ad set needs the widest
audience it can get to deliver at all, and splitting that budget across another audience would starve both.
It is here so it is ready and already learning when the budget grows.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = 'https://graph.facebook.com/v21.0'
AD_ACCOUNT = 'act_178760798664478'
TOKEN_FILE = os.environ.get('META_TOKEN_FILE', '~/.credentials/meta/iguanacomedy/token')
CREDS = pathlib.Path('~/.credentials/vpsorg/iguanacomedy').expanduser()

AUDIENCE_NAME = 'Iguana customers and subscribers'
LOOKALIKE_NAME = 'Iguana lookalike 1% Mexico'
# Meta matches on any of these; more columns means a higher match rate, and the match rate is the whole point.
SCHEMA = ['EMAIL', 'PHONE', 'FN', 'LN', 'COUNTRY']
BATCH = 500


def token() -> str:
    path = pathlib.Path(TOKEN_FILE).expanduser()
    value = path.read_text().strip() if path.exists() else ''
    if not value:
        sys.exit(f'{path} is missing or empty; put the system-user token there (chmod 600)')
    return value


def _fail(path, exc):
    body = exc.read().decode(errors='replace')
    try:
        error = json.loads(body)['error']
        message = error.get('error_user_msg') or error.get('message', '')
    except Exception:
        message = body[:400]
    sys.exit(f'Graph API {exc.code} on {path}: {message}')


def get(path, **params):
    params['access_token'] = token()
    try:
        with urllib.request.urlopen(f'{API}/{path}?' + urllib.parse.urlencode(params), timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        _fail(path, exc)


def post(path, **params):
    params['access_token'] = token()
    data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                                   for k, v in params.items()}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f'{API}/{path}', data=data), timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        _fail(path, exc)


# The hashing runs on the production box, against the live CRM, and prints only hashes.
REMOTE = r'''
import hashlib, json, re, unicodedata, django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iguana.settings')
django.setup()
from crm.models import Contact

def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest() if value else ''

def plain(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text.lower())

rows = []
for c in Contact.objects.filter(unsubscribed_at__isnull=True):
    email = (c.email or '').strip().lower()
    if '@' not in email:
        continue
    raw = (c.phone_e164 or c.phone or '').strip()
    digits = re.sub(r'\D', '', raw)
    # A number with no country code cannot be matched and guessing one would be worse than leaving it out.
    phone = sha(digits) if raw.startswith('+') and len(digits) >= 8 else ''
    rows.append([sha(email), phone, sha(plain(c.first_name)), sha(plain(c.last_name)),
                 sha(plain(c.geo_country)[:2]) if len(plain(c.geo_country)) == 2 else ''])
print(json.dumps(rows))
'''


def load_hashed_rows():
    password = (CREDS / 'password').read_text().strip()
    user = (CREDS / 'user').read_text().strip()
    host = (CREDS / 'host').read_text().strip()
    # Base64 so the program survives the trip through ssh's shell intact; quoting it would turn every newline
    # in the source into a literal backslash-n and the remote python would refuse to parse it.
    encoded = base64.b64encode(REMOTE.encode()).decode()
    remote = ('cd /home/www/iguana/backend && sudo -n -u iguana DJANGO_SETTINGS_MODULE=iguana.settings '
              f"venv/bin/python -c \"import base64;exec(base64.b64decode('{encoded}'))\"")
    result = subprocess.run(['sshpass', '-p', password, 'ssh', '-o', 'StrictHostKeyChecking=no',
                             f'{user}@{host}', remote], capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        sys.exit(f'could not read the contact list from production: {result.stderr.strip()[:400]}')
    return json.loads(result.stdout.strip().splitlines()[-1])


def find_audience(name):
    payload = get(f'{AD_ACCOUNT}/customaudiences',
                  fields='id,name,subtype,approximate_count_lower_bound,operation_status', limit=200)
    return next((a for a in payload.get('data', []) if a['name'] == name), None)


def cmd_build(args):
    rows = load_hashed_rows()
    print(f'{len(rows)} subscribed contacts, hashed on the server')
    with_phone = sum(1 for r in rows if r[1])
    print(f'  {with_phone} carry a phone number with a country code as well as an email')

    audience = find_audience(AUDIENCE_NAME)
    if audience:
        print(f'  reusing audience {audience["id"]}')
    else:
        audience = post(f'{AD_ACCOUNT}/customaudiences', name=AUDIENCE_NAME,
                        description='Everyone who bought a ticket or signed up, from the Iguana CRM. '
                                    'Refreshed by scripts/meta-audiences.py.',
                        subtype='CUSTOM', customer_file_source='USER_PROVIDED_ONLY')
        print(f'  created audience {audience["id"]}')

    session_id = int(__import__('time').time())
    total = (len(rows) + BATCH - 1) // BATCH
    for index in range(0, len(rows), BATCH):
        chunk = rows[index:index + BATCH]
        number = index // BATCH + 1
        post(f'{audience["id"]}/users',
             payload={'schema': SCHEMA, 'data': chunk},
             session={'session_id': session_id, 'batch_seq': number,
                      'last_batch_flag': number == total, 'estimated_num_total': len(rows)})
        print(f'  sent batch {number} of {total} ({len(chunk)} rows)')

    if args.lookalike:
        existing = find_audience(LOOKALIKE_NAME)
        if existing:
            print(f'  lookalike already exists: {existing["id"]}')
        else:
            made = post(f'{AD_ACCOUNT}/customaudiences', name=LOOKALIKE_NAME,
                        subtype='LOOKALIKE', origin_audience_id=audience['id'],
                        lookalike_spec={'type': 'similarity', 'country': 'MX', 'ratio': 0.01})
            print(f'  created lookalike {made["id"]} (1% of Mexico, from the customer list)')
    print('\nMeta takes a few hours to match a list. Check back with: scripts/meta-audiences.py status')


def cmd_status(args):
    payload = get(f'{AD_ACCOUNT}/customaudiences',
                  fields='id,name,subtype,approximate_count_lower_bound,approximate_count_upper_bound,'
                         'operation_status,time_content_updated', limit=200)
    for audience in payload.get('data', []):
        low = audience.get('approximate_count_lower_bound')
        high = audience.get('approximate_count_upper_bound')
        size = f'{low:,} to {high:,}' if low and low > 0 else 'not sized yet'
        state = (audience.get('operation_status') or {}).get('description', '')
        print(f'  {audience["id"]}  {audience["name"][:38]:38} {audience.get("subtype", ""):10} {size:22} {state}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build', help='create or refresh the customer audience')
    build.add_argument('--lookalike', action='store_true', help='also build a 1%% Mexico lookalike')
    build.set_defaults(func=cmd_build)
    sub.add_parser('status', help='audience sizes').set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
