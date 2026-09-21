"""The weekly what-is-on email, built from the calendar rather than written by hand.

    manage.py send_whats_on                              dry run: prints the mail and who would get it
    manage.py send_whats_on --send                       deliver it
    manage.py send_whats_on --lede-en "We are open!" --lede-es "¡Ya abrimos!" --send
    manage.py send_whats_on --lede-file /var/lib/iguana/newsletter-lede.json --send
    manage.py send_whats_on --list Newsletter --send     only that list, instead of everyone subscribed

Dry run by default, like `send_newsletter`: `--send` is the only thing that delivers, so a cron that fires twice
or a hand-run rehearsal cannot mail the club's whole list by accident.

Two refusals worth knowing about. It will not send a week with nothing on it, because an empty newsletter is how
people learn to ignore the ones that matter. And it will not send the same week twice: each run is recorded as a
Campaign named for its Monday, and a second run of the same week needs `--again` said out loud.

`--lede-file` is how a one-off announcement rides along with the next scheduled send, rather than somebody having
to remember to run the command by hand that morning. It holds `{"en": "...", "es": "..."}`, it is used once, and
after a successful send it is renamed out of the way so the following week goes out plain. A missing file is the
normal case and is not an error: that is what every week after the announcement looks like.
"""

import datetime as dt
import json
import pathlib

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
        # default=None, not '': argparse skips `type` on a default, and pathlib.Path('') is Path('.'), which
        # exists and is a directory, so an empty default would read the working directory as the announcement.
        parser.add_argument('--lede-file', default=None, type=pathlib.Path,
                            help='JSON {"en": "...", "es": "..."} used once, then renamed aside. Missing is fine.')
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
        lede_file = opts['lede_file']
        if lede_file and lede_file.exists():
            try:
                announcement = json.loads(lede_file.read_text())
            except (OSError, ValueError) as exc:
                raise CommandError(f'{lede_file} is not readable JSON: {exc}')
            # Whatever was passed on the command line wins, so a hand-run can still override the file.
            lede['lede_en'] = lede['lede_en'] or str(announcement.get('en', ''))
            lede['lede_es'] = lede['lede_es'] or str(announcement.get('es', ''))
            self.stdout.write(f'one-off announcement from {lede_file}')
        elif lede_file:
            self.stdout.write(f'no announcement waiting at {lede_file}, sending the plain weekly mail')
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
        if sent and lede_file and lede_file.exists():
            # Renamed rather than deleted: next week goes out plain, and what was announced stays on the box.
            used = lede_file.with_suffix(f'{lede_file.suffix}.sent-{monday}')
            lede_file.rename(used)
            self.stdout.write(f'announcement used once; moved to {used}')
        self.stdout.write(self.style.SUCCESS(f'sent {sent}, skipped {skipped} unsubscribed, recorded as '
                                             f'{campaign_name}'))
        if sent:
            self.stdout.write('Language is recorded when somebody clicks: every link is marked with the contact, '
                              'and which of the two blocks they clicked from says which language they read.')
