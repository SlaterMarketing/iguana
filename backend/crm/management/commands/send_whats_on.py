"""The weekly what-is-on email, built from the calendar rather than written by hand.

    manage.py send_whats_on                              dry run: prints the mail and who would get it
    manage.py send_whats_on --send                       deliver it
    manage.py send_whats_on --lede-en "We are open!" --lede-es "¡Ya abrimos!" --send
    manage.py send_whats_on --list Newsletter --send     only that list, instead of everyone subscribed

Dry run by default, like `send_newsletter`: `--send` is the only thing that delivers, so a cron that fires twice
or a hand-run rehearsal cannot mail the club's whole list by accident.

Two refusals worth knowing about. It will not send a week with nothing on it, because an empty newsletter is how
people learn to ignore the ones that matter. And it will not send the same week twice: each run is recorded as a
Campaign named for its Monday, and a second run of the same week needs `--again` said out loud.
"""

import datetime as dt

from django.core.management.base import BaseCommand, CommandError

from crm.mail import marketing_recipients, send_marketing
from crm.models import Campaign, Contact, ContactList
from crm.whats_on import CANCUN, body, subject, week_events


class Command(BaseCommand):
    help = 'Email the week\'s shows to the mailing list, in both languages'

    def add_arguments(self, parser):
        parser.add_argument('--list', dest='list_name', default='',
                            help='Contact list name; the default is everyone still subscribed')
        parser.add_argument('--days', type=int, default=7, help='How far ahead to include (default 7)')
        parser.add_argument('--lede-en', default='', help='An extra line at the top, English')
        parser.add_argument('--lede-es', default='', help='An extra line at the top, Spanish')
        parser.add_argument('--send', action='store_true', help='Actually deliver (otherwise it is a dry run)')
        parser.add_argument('--again', action='store_true', help='Send even though this week already went out')
        parser.add_argument('--rate', type=float, default=0.2,
                            help='Seconds between messages (default 0.2), so a send does not spike the queue')

    def handle(self, *args, **opts):
        events = week_events(days=opts['days'])
        if not events:
            self.stdout.write(self.style.WARNING(
                f'Nothing on in the next {opts["days"]} days, so there is no email to send.'))
            return

        monday = dt.datetime.now(CANCUN).date()
        monday -= dt.timedelta(days=monday.weekday())
        campaign_name = f'Weekly what is on {monday}'
        already = Campaign.objects.filter(name=campaign_name).first()
        if already and already.recipients.exists() and not opts['again']:
            raise CommandError(f'{campaign_name} already went to {already.recipients.count()} people. '
                               'Pass --again if you really mean to send it twice.')

        if opts['list_name']:
            contact_list = ContactList.objects.filter(name__iexact=opts['list_name']).first()
            if not contact_list:
                names = ', '.join(ContactList.objects.values_list('name', flat=True)[:20]) or 'none'
                raise CommandError(f'No contact list called {opts["list_name"]!r}. There is: {names}')
            contacts = list(Contact.objects.filter(lists=contact_list).distinct())
            audience = contact_list.name
        else:
            contacts = list(Contact.objects.filter(subscribed=True, email_marketing_eligible=True))
            audience = 'everyone subscribed'

        eligible = marketing_recipients(contacts)
        self.stdout.write(f'{len(events)} show(s) in the next {opts["days"]} days')
        for event in events:
            self.stdout.write(f'  {event.date.astimezone(CANCUN):%a %Y-%m-%d}  {event.label("en")}')
        known = sum(1 for c in eligible if c.locale)
        self.stdout.write(f'{audience}: {len(contacts)} contacts, {len(eligible)} still subscribed, '
                          f'{known} with a language recorded')

        lede = {'lede_en': opts['lede_en'], 'lede_es': opts['lede_es']}
        if not opts['send']:
            sample = eligible[0] if eligible else None
            self.stdout.write('\n' + '=' * 78)
            self.stdout.write(subject(events, getattr(sample, 'locale', '') or 'en'))
            self.stdout.write('-' * 78)
            self.stdout.write(body(events, sample, **lede))
            self.stdout.write('=' * 78)
            self.stdout.write(self.style.WARNING('\nDry run. Pass --send to deliver.'))
            return

        campaign = already or Campaign.objects.create(name=campaign_name, status='SENDING')
        sent, skipped = send_marketing(
            lambda lang: subject(events, lang),
            lambda lang, contact: body(events, contact, **lede),
            contacts,
            campaign=campaign,
            rate=opts['rate'],
        )
        campaign.status = 'SENT'
        campaign.save(update_fields=['status'])
        self.stdout.write(self.style.SUCCESS(f'sent {sent}, skipped {skipped} unsubscribed, recorded as '
                                             f'{campaign_name}'))
        if sent:
            self.stdout.write('Language is recorded when somebody clicks: every link is marked with the contact, '
                              'and which of the two blocks they clicked from says which language they read.')
