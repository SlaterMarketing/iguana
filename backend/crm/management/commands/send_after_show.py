"""The morning-after note to everyone who booked last night's show.

    manage.py send_after_show                      # dry run: prints who would get it
    manage.py send_after_show --send               # actually delivers
    manage.py send_after_show --date 2026-09-23 --send

Dry run by default, like `send_newsletter`, so a wrong `--date` cannot mail the wrong night. Unsubscribed
people are dropped by `crm.mail`, not here, and every booking the run considers is stamped whether it was
mailed or skipped: a follow-up that arrives three days late is not a follow-up.
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from crm.after_show import body_for, plan, subject_for
from crm.mail import marketing_recipients, send_marketing
from sales.models import Order


class Command(BaseCommand):
    help = "Ask last night's audience how it was, and to tell somebody"

    def add_arguments(self, parser):
        parser.add_argument('--days-ago', type=int, default=1, help='How far back the show was (default 1)')
        parser.add_argument('--date', help='Follow up on this exact show day instead, YYYY-MM-DD')
        parser.add_argument('--send', action='store_true', help='Actually deliver (otherwise it is a dry run)')
        parser.add_argument('--rate', type=float, default=0.2, help='Seconds between messages')

    def handle(self, *args, **opts):
        days_ago = opts['days_ago']
        if opts['date']:
            try:
                wanted = datetime.strptime(opts['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f'--date wants YYYY-MM-DD, got {opts["date"]!r}')
            days_ago = (timezone.localdate() - wanted).days
            if days_ago < 0:
                raise CommandError(f'{wanted} has not happened yet')

        day, to_send, also_stamp = plan(days_ago)
        if not to_send and not also_stamp:
            self.stdout.write(f'{day}: nothing booked, nothing to follow up')
            return

        contacts = [contact for _, contact in to_send]
        eligible = {c.email.lower() for c in marketing_recipients(contacts)}
        self.stdout.write(f'{day}: {len(to_send)} booking(s) to follow up, {len(eligible)} still subscribed, '
                          f'{len(also_stamp)} stamped without mail')
        for order, contact in to_send:
            mark = 'send ' if contact.email.lower() in eligible else 'skip '
            self.stdout.write(f'  {mark} {order.customer_email:38s} {order.event_name}')

        if not opts['send']:
            self.stdout.write(self.style.WARNING('Dry run. Pass --send to deliver.'))
            self.stdout.write('')
            sample = to_send[0][0]
            self.stdout.write(f'Subject: {subject_for(sample.locale)}')
            self.stdout.write(body_for(sample))
            return

        # The body is per BOOKING (the show's name is in it), so the callable looks the order up by the
        # address `crm.mail` is writing to rather than trying to carry one body for everybody.
        by_email = {order.customer_email.lower(): order for order, _ in to_send}
        sent, skipped = send_marketing(
            lambda lang, contact=None: subject_for(lang),
            lambda lang, contact: body_for(by_email[contact.email.lower()], lang),
            contacts, rate=opts['rate'])

        stamped = timezone.now()
        ids = [order.id for order, _ in to_send] + [order.id for order in also_stamp]
        Order.objects.filter(id__in=ids).update(follow_up_sent_at=stamped)
        self.stdout.write(self.style.SUCCESS(f'{day}: {sent} sent, {skipped} skipped, {len(ids)} stamped'))
