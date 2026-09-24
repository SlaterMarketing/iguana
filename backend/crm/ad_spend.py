"""What the ads cost, fetched on a schedule and written down.

Nothing in a request path talks to Meta. The ad account's rate limit clears only by waiting, so a dashboard
that asked Graph on every load would eventually wall itself, and a Graph outage would turn the page into a 500
at the moment somebody wanted to know whether to keep spending. A cron calls `fetch()` every quarter of an
hour and `/stats/` reads the rows, which also means the page renders honestly, with the time of the last
successful fetch on it, when Meta is unreachable.

Two things about Meta's own numbers are worth remembering when reading anything built on this:

`time_range` is inclusive at both ends, so "since today, until today" is one day and `since = today - 1` is
two. That is what makes `meta-ads.py campaigns --days 1` a two-day figure, which read as a fivefold overspend
for about a minute on 2026-09-24.

And `reported_purchases` is Meta's attribution, not our database. It has been both high and low against the
orders we actually hold, so it is stored for comparison and never used as the denominator: cost per booking
here is always spend over bookings we can see in our own tables.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

from .models import AdSpend

log = logging.getLogger(__name__)

GRAPH = 'https://graph.facebook.com/v21.0'
TIMEOUT = 30

# The campaigns that sell a free seat. `scripts/meta-openmic-campaigns.py` builds them with this exact prefix,
# and anything else on the account is selling a ticket. It is a naming rule rather than a lookup because the
# campaign is the only object Meta's insights give us here; `api.tests.AdSpendTests` pins it.
FREE_PREFIX = 'open mic'

# How often one person should see an ad in a week before it counts as repetition. The owner's number.
FREQUENCY_TARGET = 1.3


def classify(campaign_name):
    return AdSpend.FREE if (campaign_name or '').strip().lower().startswith(FREE_PREFIX) else AdSpend.PAID


def _get(path, **params):
    params['access_token'] = settings.META_ADS_TOKEN
    url = f'{GRAPH}/{path}?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        return json.load(response)


def _purchases(row):
    for action in row.get('actions') or []:
        if action.get('action_type') in ('purchase', 'offsite_conversion.fb_pixel_purchase'):
            return int(float(action.get('value', 0)))
    return 0


FIELDS = 'campaign_id,campaign_name,spend,impressions,clicks,reach,frequency,actions'


def _write(row, day, window, now):
    AdSpend.objects.update_or_create(
        day=day, window=window, campaign_id=row['campaign_id'],
        defaults={
            'campaign_name': row.get('campaign_name', ''),
            'kind': classify(row.get('campaign_name', '')),
            'spend_cents': round(float(row.get('spend', 0)) * 100),
            'impressions': int(row.get('impressions', 0) or 0),
            'clicks': int(row.get('clicks', 0) or 0),
            'reach': int(row.get('reach', 0) or 0),
            'frequency': float(row.get('frequency', 0) or 0),
            'reported_purchases': _purchases(row),
            'fetched_at': now,
        })


def fetch(days=2, today=None):
    """Pull per-campaign figures and write them down. Returns rows written.

    Two passes, and the second is not a convenience. Daily rows are what a dashboard restates. The seven-day
    row has to be asked for AS a seven-day window, because reach counts PEOPLE: summing seven daily reaches
    counts somebody who saw the ad on Monday and again on Thursday twice, so a frequency derived from that sum
    reads lower than the truth, which is exactly the direction that hides ad fatigue.
    """
    if not settings.META_ADS_TOKEN:
        log.warning('no META_ADS_TOKEN, so /stats/ has no spend to show')
        return 0
    until = today or timezone.localdate()
    since = until - timedelta(days=max(days - 1, 0))
    now = timezone.now()
    written = 0

    daily = _get(f'{settings.META_AD_ACCOUNT}/insights', level='campaign', time_increment=1, limit=500,
                 time_range=json.dumps({'since': since.isoformat(), 'until': until.isoformat()}),
                 fields=FIELDS)
    for row in daily.get('data', []):
        _write(row, date.fromisoformat(row['date_start']), AdSpend.DAY, now)
        written += 1

    week_since = until - timedelta(days=6)
    weekly = _get(f'{settings.META_AD_ACCOUNT}/insights', level='campaign', limit=500,
                  time_range=json.dumps({'since': week_since.isoformat(), 'until': until.isoformat()}),
                  fields=FIELDS)
    for row in weekly.get('data', []):
        _write(row, until, AdSpend.WEEK, now)
        written += 1
    return written


def campaign_rows(day=None, window=AdSpend.DAY):
    """Per campaign, worst value for money first. Frequency comes from Meta and is never recomputed here."""
    day = day or timezone.localdate()
    rows = []
    for row in AdSpend.objects.filter(day=day, window=window).order_by('-spend_cents'):
        rows.append({
            'name': row.campaign_name,
            'free': row.kind == AdSpend.FREE,
            'spend': row.spend_cents / 100,
            'reach': row.reach,
            'impressions': row.impressions,
            'frequency': row.frequency,
            'clicks': row.clicks,
            'ctr': (row.clicks / row.impressions * 100) if row.impressions else None,
            'cpc': (row.spend_cents / 100 / row.clicks) if row.clicks else None,
            # The owner's target, not an industry threshold: 1.3 impressions per person per week. Set
            # 2026-09-24 looking at 1.7 and 1.8 on the open mics. Over it, the budget is buying the same
            # faces again rather than new ones, and the fix is a bigger audience or a smaller budget.
            'saturated': window == AdSpend.WEEK and row.frequency > FREQUENCY_TARGET,
        })
    return rows


def spend_between(first_day, last_day):
    """{'FREE': cents, 'PAID': cents} over an inclusive range of days."""
    totals = {AdSpend.FREE: 0, AdSpend.PAID: 0}
    for row in AdSpend.objects.filter(day__gte=first_day, day__lte=last_day, window=AdSpend.DAY):
        totals[row.kind] = totals.get(row.kind, 0) + row.spend_cents
    return totals


def last_fetch():
    row = AdSpend.objects.order_by('-fetched_at').first()
    return row.fetched_at if row else None
