"""Remind everybody booked for tonight, and give open mic guests a way to hand their seat back.

    manage.py send_show_reminders           # who would get one
    manage.py send_show_reminders --send    # send them

Runs daily at 15:00 UTC (10:00 in Playa) from deploy.yml. Every booking it sends to is stamped with
`Order.reminder_sent_at`, so a re-run or a double fire sends nothing twice. The copy and the rules are in
sales/reminders.py.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from sales.reminders import can_release, orders_for_today, send


class Command(BaseCommand):
    help = "Send the morning-of reminder for tonight's shows"

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true', help='Send (default: list who would get one)')

    def handle(self, *args, **opts):
        orders = list(orders_for_today())
        sent = 0
        for order in orders:
            kind = 'open mic, can give seat back' if can_release(order) else 'reminder only'
            self.stdout.write(f'  {"send" if opts["send"] else "would"}  {order.customer_email:38} '
                              f'{order.event_name[:30]:30} {kind}')
            if opts['send'] and send(order):
                order.reminder_sent_at = timezone.now()
                order.save(update_fields=['reminder_sent_at'])
                sent += 1
        self.stdout.write(f'{timezone.localdate()}: {len(orders)} booking(s), {sent} sent'
                          + ('' if opts['send'] else ' (dry run)'))
