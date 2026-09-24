"""Write down what the ads have cost, for /stats/ to read.

    manage.py snapshot_ad_spend            # today and yesterday
    manage.py snapshot_ad_spend --days 30  # backfill after an outage

Runs on a cron every quarter of an hour. It is the only thing here that talks to Meta: the page itself never
does, so a rate limit or a Graph outage costs a stale "last updated" line rather than a broken dashboard.
"""

from django.core.management.base import BaseCommand

from crm.ad_spend import fetch


class Command(BaseCommand):
    help = 'Snapshot Meta ad spend per campaign per day'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=2, help='How many days back, including today')

    def handle(self, *args, **opts):
        written = fetch(days=opts['days'])
        self.stdout.write(f'{written} campaign-day row(s) written')
