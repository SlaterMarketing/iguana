import hashlib
import json
import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Artist, Event, FormEndpoint, LineupEntry, TicketType, Venue
from crm.models import Contact
from sales.models import LoginToken, Membership, MembershipPlan, Order

KEY = 'ipk_test'
SITE = 'http://site.test'


@override_settings(PUBLIC_API_KEYS=[KEY], SECRET_API_KEYS=[], SITE_URLS=[SITE], BACKEND_URL='http://api.test',
                   STRIPE_SECRET_KEY='', STRIPE_PUBLISHABLE_KEY='', NOTIFY_EMAILS=[], DEBUG=True)
class ApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name='Iguana Comedy', city='Playa del Carmen', address='Calle 6 Nte 189')
        cls.event = Event.objects.create(name='Open Mic', slug='open-mic', status=Event.ACTIVE, venue=cls.venue,
                                         date=timezone.now() + timedelta(days=7), doors_open='19:00', show_time='20:00')
        cls.ga = TicketType.objects.create(event=cls.event, name='GA', price_cents=1000, capacity=3)
        cls.vip = TicketType.objects.create(event=cls.event, name='Front row', price_cents=2500, member_access='MEMBERS_ONLY')
        cls.draft = Event.objects.create(name='Hidden', slug='hidden', date=timezone.now() + timedelta(days=3))
        cls.artist = Artist.objects.create(name='Trevor Green', bio='Mysterious.', bio_es='Misterioso.')
        LineupEntry.objects.create(event=cls.event, artist=cls.artist, headliner=True)
        cls.plan = MembershipPlan.objects.create(name='Iguana Member', monthly_cents=9900, annual_cents=99900)
        FormEndpoint.objects.create(slug='contact')

    def api(self, method, path, body=None, fan=None):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {KEY}'}
        if fan:
            headers['HTTP_X_CUSTOMER_AUTHORIZATION'] = f'Bearer {fan}'
        kwargs = {'data': json.dumps(body), 'content_type': 'application/json'} if body is not None else {}
        return getattr(self.client, method)(path, **kwargs, **headers)

    def sign_in(self, email):
        self.api('post', '/api/fan/v1/auth/request', {'email': email, 'redirectUrl': f'{SITE}/en/account/verify/'})
        login = LoginToken.objects.filter(email=email).latest('created_at')
        return self.api('post', '/api/fan/v1/auth/verify', {'token': login.token}).json()['accessToken']

    def make_member(self, email):
        contact = Contact.objects.create(email=email)
        Membership.objects.create(contact=contact, plan=self.plan, status=Membership.ACTIVE, ends_at=timezone.now() + timedelta(days=30))
        return contact


class PublicApiTests(ApiTestCase):
    def test_requires_key(self):
        self.assertEqual(self.client.get('/api/public/v1/events').status_code, 401)

    def test_events_hide_drafts_and_match_sdk_shape(self):
        events = self.api('get', '/api/public/v1/events?limit=10').json()['events']
        self.assertEqual([e['slug'] for e in events], ['open-mic'])
        e = events[0]
        self.assertEqual(e['status'], 'on-sale')
        self.assertEqual(e['priceFrom'], 1000)
        self.assertEqual(e['headliner']['slug'], self.artist.slug)
        self.assertEqual(e['venue']['city'], 'Playa del Carmen')
        self.assertRegex(e['date'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(e['goldMembership']['freeTickets'], 2)
        self.assertEqual(self.api('get', '/api/public/v1/events/hidden').status_code, 404)

    def test_past_filter(self):
        Event.objects.filter(pk=self.event.pk).update(date=timezone.now() - timedelta(days=3))
        rows = self.api('get', '/api/public/v1/events?status=past').json()['events']
        self.assertEqual(rows[0]['status'], 'past')
        self.assertEqual(self.api('get', f'/api/public/v1/events?from={timezone.now().date()}').json()['events'], [])

    def test_artist_detail_locale_and_upcoming(self):
        data = self.api('get', f'/api/public/v1/artists/{self.artist.slug}?locale=es').json()['artist']
        self.assertEqual(data['bio'], 'Misterioso.')
        self.assertEqual(len(data['upcomingEvents']), 1)

    def test_form_submit_creates_contact(self):
        res = self.api('post', '/api/public/v1/endpoints/contact/submit', {'email': 'A@Example.com', 'fields': {'message': 'hi'}})
        self.assertTrue(res.json()['ok'])
        self.assertTrue(Contact.objects.filter(email='a@example.com', source='CONTACT_FORM').exists())
        self.assertEqual(self.api('post', '/api/public/v1/endpoints/nope/submit', {'email': 'a@example.com'}).status_code, 404)


class EventLanguageTests(ApiTestCase):
    """Event name, text and poster come back in the language the site asks for."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Event.objects.filter(pk=cls.event.pk).update(
            name='Open Mic Night in Spanish', name_es='Noche de Open Mic en Español',
            description='Free entry.', description_es='Entrada libre.',
            image_url='/media/events/en.jpg', image_url_es='/media/events/es.jpg',
            image_url_mobile='/media/events/en-4x5.jpg', image_url_mobile_es='/media/events/es-4x5.jpg')

    def test_events_and_detail_answer_in_the_requested_language(self):
        for path in ('/api/public/v1/events?limit=10', '/api/public/v1/events/open-mic'):
            english = self.api('get', path).json()
            spanish = self.api('get', f'{path}{"&" if "?" in path else "?"}locale=es').json()
            pick = (lambda data: data['events'][0]) if 'events' in english else (lambda data: data['event'])
            self.assertEqual(pick(english)['name'], 'Open Mic Night in Spanish')
            self.assertEqual(pick(spanish)['name'], 'Noche de Open Mic en Español')
            self.assertEqual(pick(english)['description'], 'Free entry.')
            self.assertEqual(pick(spanish)['description'], 'Entrada libre.')
            self.assertTrue(pick(english)['imageUrl'].endswith('/media/events/en.jpg'))
            self.assertTrue(pick(spanish)['imageUrl'].endswith('/media/events/es.jpg'))
            self.assertTrue(pick(spanish)['imageUrlMobile'].endswith('/media/events/es-4x5.jpg'))

    def test_missing_spanish_falls_back_to_the_english_row(self):
        Event.objects.filter(pk=self.event.pk).update(name_es='', description_es='', image_url_es='')
        spanish = self.api('get', '/api/public/v1/events/open-mic?locale=es').json()['event']
        self.assertEqual(spanish['name'], 'Open Mic Night in Spanish')
        self.assertEqual(spanish['description'], 'Free entry.')
        self.assertTrue(spanish['imageUrl'].endswith('/media/events/en.jpg'))

    def test_artist_page_upcoming_events_follow_the_locale(self):
        data = self.api('get', f'/api/public/v1/artists/{self.artist.slug}?locale=es').json()['artist']
        self.assertEqual(data['upcomingEvents'][0]['name'], 'Noche de Open Mic en Español')

    def test_checkout_header_uses_the_localized_name(self):
        page = self.client.get(f'/embed/event/{self.event.id}?lang=es').content.decode()
        self.assertIn('Noche de Open Mic en Español', page)


class NewsletterTests(ApiTestCase):
    """Home page sign-ups join "Newsletter"; empty city pages also join that city's alert list. No alert emails."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        FormEndpoint.objects.create(slug='newsletter', intent='newsletter', title='Newsletter')

    def signup(self, email, context=None):
        return self.api('post', '/api/public/v1/endpoints/newsletter/submit',
                        {'email': email, 'fields': {'locale': 'es'}, 'context': context or {}})

    def test_signup_joins_newsletter_without_an_alert_email(self):
        from crm.models import ContactList

        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            self.assertTrue(self.signup('Fan@Example.com').json()['ok'])
            self.signup('fan@example.com')  # signing up twice is harmless
        members = ContactList.objects.get(name='Newsletter').contacts.all()
        self.assertEqual([c.email for c in members], ['fan@example.com'])
        self.assertEqual(Contact.objects.get(email='fan@example.com').source, 'NEWSLETTER')
        self.assertEqual(mail.outbox, [])

    def test_city_signup_also_joins_that_citys_alert_list(self):
        from crm.models import ContactList

        self.signup('cancun@example.com', {'citySlug': 'cancun', 'cityLabel': 'Cancún'})
        self.assertEqual(sorted(ContactList.objects.filter(contacts__email='cancun@example.com').values_list('name', flat=True)),
                         ['City alerts: Cancún', 'Newsletter'])
        self.signup('bad@example.com', {'citySlug': '<script>', 'cityLabel': 'x'})
        self.assertEqual(list(ContactList.objects.filter(contacts__email='bad@example.com').values_list('name', flat=True)),
                         ['Newsletter'])


class VisitorLoggingTests(ApiTestCase):
    """Sign-ups and bookings record language, time zone and IP location on the contact, submission and order."""

    FAKE_PLACE = {'country': 'MX', 'region': 'Quintana Roo', 'city': 'Playa del Carmen'}

    def setUp(self):
        from unittest import mock

        patcher = mock.patch('crm.geo.locate', side_effect=lambda ip: dict(self.FAKE_PLACE) if ip == '189.203.10.20' else {})
        patcher.start()
        self.addCleanup(patcher.stop)
        FormEndpoint.objects.get_or_create(slug='newsletter', defaults={'intent': 'newsletter'})

    def test_real_ip_only_trusted_from_the_local_proxy(self):
        from django.test import RequestFactory

        from crm.geo import client_ip

        factory = RequestFactory()
        self.assertEqual(client_ip(factory.get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='189.203.10.20')), '189.203.10.20')
        self.assertEqual(client_ip(factory.get('/', REMOTE_ADDR='200.1.1.1', HTTP_X_REAL_IP='189.203.10.20')), '200.1.1.1')

    def test_newsletter_signup_records_language_and_location(self):
        from catalog.models import FormSubmission

        self.client.post(
            '/api/public/v1/endpoints/newsletter/submit', content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {KEY}',
            HTTP_X_REAL_IP='189.203.10.20',
            data=json.dumps({'email': 'geo@example.com', 'fields': {'locale': 'es'},
                             'context': {'browserLanguage': 'es-MX', 'timeZone': 'America/Cancun'}}))
        contact = Contact.objects.get(email='geo@example.com')
        self.assertEqual((contact.locale, contact.browser_language, contact.time_zone, contact.geo_country, contact.geo_region,
                          contact.geo_city, contact.last_ip),
                         ('es', 'es-MX', 'America/Cancun', 'MX', 'Quintana Roo', 'Playa del Carmen', '189.203.10.20'))
        submission = FormSubmission.objects.get(email='geo@example.com')
        self.assertEqual(submission.ip, '189.203.10.20')
        self.assertEqual(submission.context['visitor']['city'], 'Playa del Carmen')

    def test_booking_records_language_and_location_on_order_and_contact(self):
        start = self.client.post(f'/api/checkout/{self.event.id}/start', content_type='application/json', HTTP_X_REAL_IP='189.203.10.20',
                                 data=json.dumps({'lang': 'en', 'items': {self.ga.id: 1}, 'name': 'Geo Fan', 'email': 'geofan@example.com',
                                                  'client': {'browserLanguage': 'en-US', 'timeZone': 'America/Chicago'}})).json()
        order = Order.objects.get(pk=start['orderId'])
        self.assertEqual(order.attribution['visitor'], {'ip': '189.203.10.20', 'locale': 'en', 'browserLanguage': 'en-US',
                                                        'timeZone': 'America/Chicago', **self.FAKE_PLACE})
        self.assertEqual((order.contact.locale, order.contact.time_zone, order.contact.geo_city), ('en', 'America/Chicago', 'Playa del Carmen'))

    def test_missing_database_never_breaks_a_signup(self):
        from unittest import mock

        from crm import geo

        with self.settings(GEOIP_DB='/nonexistent/dbip.mmdb'), mock.patch.dict(geo._state, {'mtime': None, 'reader': None, 'warned': False}):
            self.assertEqual(geo._reader(), None)
            self.assertTrue(self.api('post', '/api/public/v1/endpoints/newsletter/submit', {'email': 'nogeo@example.com'}).json()['ok'])


class FanAuthTests(ApiTestCase):
    def test_magic_link_flow(self):
        res = self.api('post', '/api/fan/v1/auth/request', {'email': 'fan@example.com', 'redirectUrl': f'{SITE}/en/account/verify/'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('token=', mail.outbox[0].body)
        login = LoginToken.objects.get(email='fan@example.com')
        token = self.api('post', '/api/fan/v1/auth/verify', {'email': 'fan@example.com', 'code': login.code}).json()['accessToken']
        profile = self.api('get', '/api/fan/v1/account/profile', fan=token).json()['profile']
        self.assertEqual(profile['email'], 'fan@example.com')

    def test_rejects_foreign_redirect_and_bad_code(self):
        res = self.api('post', '/api/fan/v1/auth/request', {'email': 'fan@example.com', 'redirectUrl': 'https://evil.test/x'})
        self.assertEqual(res.status_code, 400)
        self.api('post', '/api/fan/v1/auth/request', {'email': 'fan@example.com', 'redirectUrl': f'{SITE}/v'})
        res = self.api('post', '/api/fan/v1/auth/verify', {'email': 'fan@example.com', 'code': '000000x'})
        self.assertEqual(res.status_code, 401)

    def test_used_token_expires_after_replay_window(self):
        self.api('post', '/api/fan/v1/auth/request', {'email': 'fan@example.com', 'redirectUrl': f'{SITE}/v'})
        login = LoginToken.objects.get(email='fan@example.com')
        self.assertEqual(self.api('post', '/api/fan/v1/auth/verify', {'token': login.token}).status_code, 200)
        self.assertEqual(self.api('post', '/api/fan/v1/auth/verify', {'token': login.token}).status_code, 200)
        LoginToken.objects.filter(pk=login.pk).update(used_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(self.api('post', '/api/fan/v1/auth/verify', {'token': login.token}).status_code, 401)

    def test_membership_status_requires_sign_in(self):
        self.assertEqual(self.api('get', '/api/fan/v1/membership/status').status_code, 401)
        self.make_member('member@example.com')
        token = self.sign_in('member@example.com')
        status = self.api('get', '/api/fan/v1/membership/status', fan=token).json()
        self.assertEqual(status['memberships'][0]['plan']['name'], 'Iguana Member')

    def test_subscribe_without_stripe_reports_not_configured(self):
        token = self.sign_in('fan@example.com')
        res = self.api('post', '/api/fan/v1/membership/subscribe', {'planId': self.plan.id, 'interval': 'month'}, fan=token).json()
        self.assertIsNone(res['stripePublishableKey'])


class CheckoutTests(ApiTestCase):
    def post(self, path, body):
        return self.client.post(path, data=json.dumps(body), content_type='application/json')

    def test_quote_and_dev_payment_completes_order(self):
        quote = self.post(f'/api/checkout/{self.event.id}/quote', {'items': {self.ga.id: 2}}).json()
        self.assertEqual(quote['totalCents'], 2000)
        start = self.post(f'/api/checkout/{self.event.id}/start',
                          {'items': {self.ga.id: 2}, 'name': 'Buyer One', 'email': 'buyer@example.com'}).json()
        self.assertTrue(start['devPayment'])
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {})
        order = Order.objects.get(pk=start['orderId'])
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertEqual(order.tickets.count(), 2)
        self.assertIn('Your tickets', mail.outbox[-1].subject)
        self.assertEqual(self.client.get(f'/orders/{order.public_view_token}/').status_code, 200)

    def test_checkout_page_has_one_button_and_no_separate_payment_step(self):
        page = self.client.get(f'/embed/event/{self.event.id}?embedded=1&lang=en').content.decode()
        self.assertEqual(page.count('<button'), 1)
        self.assertEqual(len(re.findall(r'<form\b', page)), 1)
        for gone in ('Your details', '>Continue<', 'id="payment"', 'id="pay"'):
            self.assertNotIn(gone, page)
        for label in ('Reserve {0} seats', 'Pay {0} at the door', 'Up to {0} per order'):
            self.assertIn(label, page)

    def test_capacity_and_members_only_enforced(self):
        self.assertEqual(self.post(f'/api/checkout/{self.event.id}/quote', {'items': {self.ga.id: 4}}).status_code, 400)
        self.assertEqual(self.post(f'/api/checkout/{self.event.id}/quote', {'items': {self.vip.id: 1}}).status_code, 400)

    def test_member_free_tickets_then_guest_discount(self):
        self.make_member('member@example.com')
        token = self.sign_in('member@example.com')
        quote = self.post(f'/api/checkout/{self.event.id}/quote', {'items': {self.ga.id: 3, self.vip.id: 1}, 'fanToken': token}).json()
        # 2500 + 1000 free, 10% off the remaining 2000
        self.assertEqual((quote['subtotalCents'], quote['discountCents'], quote['totalCents']), (5500, 3700, 1800))

    def test_member_pricing_ignored_for_other_email(self):
        self.make_member('member@example.com')
        token = self.sign_in('member@example.com')
        start = self.post(f'/api/checkout/{self.event.id}/start',
                          {'items': {self.ga.id: 1}, 'fanToken': token, 'name': 'X', 'email': 'someone@else.com'}).json()
        self.assertEqual(Order.objects.get(pk=start['orderId']).total_amount_cents, 1000)

    def test_free_order_completes_immediately(self):
        self.make_member('member@example.com')
        token = self.sign_in('member@example.com')
        start = self.post(f'/api/checkout/{self.event.id}/start',
                          {'items': {self.ga.id: 2}, 'fanToken': token, 'name': 'M', 'email': 'member@example.com'}).json()
        self.assertTrue(start['complete'])

    def test_sold_out_status(self):
        start = self.post(f'/api/checkout/{self.event.id}/start', {'items': {self.ga.id: 3}, 'name': 'B', 'email': 'b@example.com'}).json()
        self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {})
        TicketType.objects.filter(pk=self.vip.pk).update(active=False)
        self.assertEqual(self.api('get', '/api/public/v1/events/open-mic').json()['event']['status'], 'sold-out')

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_webhook_rejects_bad_signature(self):
        res = self.client.post('/api/stripe/webhook', data='{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='t=1,v1=bad')
        self.assertEqual(res.status_code, 400)

    def test_tracker_script_served(self):
        res = self.client.get('/_t/k.js')
        self.assertEqual(res.status_code, 200)
        self.assertIn('data-kintana-widget', res.content.decode())


class ReservationTests(ApiTestCase):
    """Open mic seat reservations: 60 of 80 seats, one free drink each, paid online or (stopgap) at the door."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.mic = Event.objects.create(name='Open Mic Night - English!', slug='open-mic-english', status=Event.ACTIVE,
                                       venue=cls.venue, currency='usd', members_eligible=False,
                                       date=timezone.now() + timedelta(days=5), show_time='20:00')
        cls.seat = TicketType.objects.create(event=cls.mic, name='Reserved seat + 1 free drink', price_cents=500,
                                             description='Entry is free. Pay at the door.', capacity=3,
                                             max_per_order=2, pay_at_door=True)
        cls.paid = TicketType.objects.create(event=cls.mic, name='Front row', price_cents=1500)

    def post(self, path, body):
        return self.client.post(path, data=json.dumps(body), content_type='application/json')

    def reserve(self, qty, email, extra=None):
        items = {self.seat.id: qty, **(extra or {})}
        return self.post(f'/api/checkout/{self.mic.id}/start', {'items': items, 'name': 'Fan', 'email': email})

    def test_reservation_completes_without_payment_and_records_what_the_door_collects(self):
        quote = self.post(f'/api/checkout/{self.mic.id}/quote', {'items': {self.seat.id: 2}}).json()
        self.assertTrue(quote['payAtDoor'])
        with self.captureOnCommitCallbacks(execute=True):
            res = self.reserve(2, 'Fan@Example.com').json()
        # With DEBUG and no Stripe keys a paid order answers devPayment; a reservation must never reach payment.
        self.assertTrue(res['complete'])
        order = Order.objects.get(pk=res['orderId'])
        self.assertEqual((order.status, order.total_amount_cents, order.pay_at_door_cents), (Order.COMPLETED, 1000, 1000))
        self.assertEqual(order.stripe_payment_intent_id, '')
        self.assertEqual(order.tickets.count(), 2)
        message = mail.outbox[-1]
        self.assertEqual(message.subject, 'Your reservation: Open Mic Night - English!')
        self.assertIn('Pay 10 USD at the door for your 2 seats. Nothing was charged online.', message.body)
        self.assertIn('Entry is free. Pay at the door.', message.body)
        self.assertIn('Pay 10 USD at the door.', self.client.get(f'/orders/{order.public_view_token}/').content.decode())

    def test_max_per_order_then_capacity(self):
        self.assertIn('up to 2', self.reserve(3, 'a@example.com').json()['error'])
        self.assertEqual(self.reserve(2, 'a@example.com').status_code, 200)
        self.assertIn('Only 1', self.reserve(2, 'b@example.com').json()['error'])
        self.assertEqual(self.reserve(1, 'b@example.com').status_code, 200)
        self.assertIn('sold out', self.reserve(1, 'c@example.com').json()['error'])

    def test_one_reservation_per_email_per_night(self):
        self.assertEqual(self.reserve(1, 'fan@example.com').status_code, 200)
        self.assertIn('already have a reservation', self.reserve(1, 'FAN@example.com').json()['error'])
        self.assertEqual(Order.objects.filter(customer_email='fan@example.com').count(), 1)

    def test_reservation_cannot_be_mixed_with_paid_tickets(self):
        self.assertEqual(self.reserve(1, 'mix@example.com', {self.paid.id: 1}).status_code, 400)
        self.assertFalse(Order.objects.filter(customer_email='mix@example.com').exists())

    def test_door_checkin_says_what_to_collect(self):
        from django.contrib.auth.models import User

        order = Order.objects.get(pk=self.reserve(1, 'door@example.com').json()['orderId'])
        ticket = order.tickets.get()
        self.client.force_login(User.objects.create_user('door', is_staff=True))
        self.assertIn('collect 5 USD for this seat', self.client.get(f'/checkin/{ticket.checkin_token}/').content.decode())
        self.client.post(f'/checkin/{ticket.checkin_token}/')
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.checked_in_at)

    def test_online_reservation_goes_through_payment_and_email_says_what_it_includes(self):
        online = TicketType.objects.create(event=self.mic, name='Reserved seat + 1 free drink (online)', price_cents=500,
                                           description='Includes a free drink. Arrive when doors open.', capacity=60)
        start = self.post(f'/api/checkout/{self.mic.id}/start',
                          {'items': {online.id: 1}, 'name': 'Fan', 'email': 'online@example.com'}).json()
        # Charged when booked: the order waits for payment instead of completing like a pay-at-the-door booking.
        self.assertFalse(start['complete'])
        self.assertTrue(start['devPayment'])
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {})
        order = Order.objects.get(pk=start['orderId'])
        self.assertEqual((order.status, order.pay_at_door_cents), (Order.COMPLETED, 0))
        self.assertIn('Includes a free drink. Arrive when doors open.', mail.outbox[-1].body)

    def spanish_night(self):
        return Event.objects.create(name='Noche de Open Mic - Espanol!', slug='noche-open-mic', venue=self.venue,
                                    date=timezone.now() + timedelta(days=6))

    def test_setup_refuses_paid_reservations_without_stripe(self):
        from io import StringIO

        from django.core.management import CommandError, call_command

        spanish = self.spanish_night()
        with self.assertRaisesMessage(CommandError, 'Stripe is not configured'):
            call_command('setup_open_mics', stdout=StringIO())
        spanish.refresh_from_db()
        self.assertEqual(spanish.status, Event.DRAFT)

        call_command('setup_open_mics', '--pay-at-door', stdout=StringIO())
        seat = spanish.ticket_types.get()
        self.assertTrue(seat.pay_at_door)
        self.assertTrue(seat.description.endswith('Pay at the door.'))
        self.assertTrue(seat.description_es.endswith('Pagas en la puerta.'))

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_setup_publishes_paid_online_reservations_idempotently(self):
        from io import StringIO

        from django.core.management import call_command

        spanish = self.spanish_night()
        for _ in range(2):
            call_command('setup_open_mics', stdout=StringIO())
        spanish.refresh_from_db()
        self.assertEqual((spanish.status, spanish.currency, spanish.language, spanish.members_eligible),
                         (Event.ACTIVE, 'mxn', 'es', False))
        self.assertIn('open-mic', spanish.tags)
        seat = spanish.ticket_types.get()
        self.assertEqual((seat.name, seat.name_es, seat.price_cents, seat.capacity, seat.max_per_order, seat.pay_at_door),
                         ('Reserved seat + 1 free drink', 'Lugar reservado + 1 bebida gratis', 5000, 60, 6, False))
        # Posters carry words, so each night has one per site language; the Spanish night's English-worded poster is
        # the default and its Spanish-worded one is the _es field.
        self.assertEqual((spanish.image_url, spanish.image_url_es),
                         ('/media/events/open-mic-es-en-16x9.jpg', '/media/events/open-mic-es-16x9.jpg'))
        self.assertEqual((spanish.name, spanish.name_es), ('Open Mic Night in Spanish', 'Noche de Open Mic en Español'))
        # A poster set in the admin is kept on re-runs, and the renamed night is still matched (by its tag).
        Event.objects.filter(pk=spanish.pk).update(image_url='/media/events/custom.jpg')
        call_command('setup_open_mics', stdout=StringIO())
        spanish.refresh_from_db()
        self.assertEqual(spanish.image_url, '/media/events/custom.jpg')
        self.assertEqual(spanish.ticket_types.count(), 1)

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_setup_renames_a_spanish_named_type_instead_of_duplicating_it(self):
        from io import StringIO

        from django.core.management import call_command

        spanish = self.spanish_night()
        TicketType.objects.create(event=spanish, name='Lugar reservado + 1 bebida gratis', price_cents=5000, pay_at_door=True)
        call_command('setup_open_mics', stdout=StringIO())
        seat = spanish.ticket_types.get()
        self.assertEqual((seat.name, seat.name_es, seat.pay_at_door), ('Reserved seat + 1 free drink',
                                                                       'Lugar reservado + 1 bebida gratis', False))


class TranslationTests(TestCase):
    """Every customer-facing backend string has Spanish, with the same slots."""

    def test_every_translatable_string_has_spanish(self):
        import pathlib
        import re

        from api.embed_views import CHECKOUT_JS_STRINGS
        from sales.i18n import ES

        root = pathlib.Path(__file__).resolve().parent.parent
        patterns = [
            (('api', 'sales', 'crm'), '*.py', r"\btr\(\s*\w+\s*,\s*'((?:[^'\\]|\\.)+)'"),
            (('api', 'sales'), '*.py', r"CheckoutError\(\s*'((?:[^'\\]|\\.)+)'"),
            (('api',), '*.py', r"\berror\(\s*'((?:[^'\\]|\\.)+)'"),
            (('templates/embed',), '*.html', r'\{% t \w+ "([^"]+)"'),
            (('templates/embed',), '*.html', r"\{% t \w+ '([^']+)'"),
        ]
        found = set(CHECKOUT_JS_STRINGS)
        for folders, glob, pattern in patterns:
            for folder in folders:
                for path in (root / folder).rglob(glob):
                    if path.name == 'tests.py':
                        continue
                    found.update(re.findall(pattern, path.read_text()))
        # A scan that silently matched nothing would pass; there are well over 100 of these.
        self.assertGreater(len(found), 100)
        self.assertEqual(sorted(text for text in found if text not in ES), [])

    def test_spanish_keeps_every_slot(self):
        import re

        from sales.i18n import ES

        slots = lambda text: sorted(re.findall(r'\{\d+\}', text))
        self.assertEqual([k for k, v in ES.items() if slots(k) != slots(v)], [])

    def test_every_order_status_has_spanish(self):
        from sales.i18n import ES

        self.assertEqual([label for _, label in Order.STATUS_CHOICES if label.lower() not in ES], [])


class SpanishCustomerTests(ApiTestCase):
    """A fan on /es/ gets Spanish from the checkout through the email, and from API errors."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.mic = Event.objects.create(name='Noche de Open Mic - Espanol!', slug='noche-open-mic', status=Event.ACTIVE,
                                       venue=cls.venue, currency='mxn', language='es', members_eligible=False,
                                       date=timezone.now() + timedelta(days=5), doors_open='19:30', show_time='20:00')
        cls.seat = TicketType.objects.create(event=cls.mic, name='Reserved seat + 1 free drink', price_cents=5000,
                                             name_es='Lugar reservado + 1 bebida gratis', capacity=1,
                                             description='Includes a free drink.', description_es='Incluye una bebida gratis.')

    def post(self, path, body, **headers):
        return self.client.post(path, data=json.dumps(body), content_type='application/json', **headers)

    def test_checkout_order_page_and_email_in_spanish(self):
        import re

        page = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=es').content.decode()
        self.assertIn('<html lang="es">', page)
        for text in ('Nombre completo', 'Reservar {0} lugares', 'Pagas {0} en la puerta', 'Lugar reservado + 1 bebida gratis',
                     'Incluye una bebida gratis.'):
            self.assertIn(text, page)
        self.assertNotIn('Full name', page)

        start = self.post(f'/api/checkout/{self.mic.id}/start', {'lang': 'es', 'items': {self.seat.id: 1},
                                                                  'name': 'Ana', 'email': 'ana@example.com'}).json()
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {'lang': 'es'})
        order = Order.objects.get(pk=start['orderId'])
        self.assertEqual((order.locale, order.items.get().name), ('es', 'Lugar reservado + 1 bebida gratis'))

        message = mail.outbox[-1]
        self.assertEqual(message.subject, 'Tus boletos: Noche de Open Mic - Espanol!')
        self.assertIn('Hola, Ana:', message.body)
        self.assertRegex(message.body, r'(lunes|martes|miércoles|jueves|viernes|sábado|domingo) \d+ de \w+ de \d{4}')
        self.assertIn('Puertas 19:30 · Show 20:00', message.body)
        self.assertIn('Incluye una bebida gratis.', message.body)
        self.assertIn('¡Nos vemos ahí!', message.body)

        order_page = self.client.get(f'/orders/{order.public_view_token}/').content.decode()
        for text in ('Tus boletos', 'Boleto 1 de 1', 'puertas 7:30 p. m.', 'Volver a Iguana Comedy'):
            self.assertIn(text, order_page)

        # Sold out now, and the refusal comes back in Spanish too.
        refused = self.post(f'/api/checkout/{self.mic.id}/quote', {'lang': 'es', 'items': {self.seat.id: 1}}).json()
        self.assertEqual(refused['error'], '«Lugar reservado + 1 bebida gratis» está agotado.')

    def test_api_errors_follow_the_page_language(self):
        body = {'email': 'not-an-email', 'redirectUrl': f'{SITE}/es/account/verify/'}
        spanish = self.api('post', '/api/fan/v1/auth/request', body)
        self.assertEqual(spanish.json()['error'], 'Enter a valid email address')
        translated = self.client.post('/api/fan/v1/auth/request', data=json.dumps(body), content_type='application/json',
                                      HTTP_AUTHORIZATION=f'Bearer {KEY}', HTTP_X_IGUANA_LOCALE='es')
        self.assertEqual(translated.json()['error'], 'Escribe un correo electrónico válido.')
        self.assertEqual(int(translated['Content-Length']), len(translated.content))

    def test_sign_in_email_matches_the_site_language(self):
        self.api('post', '/api/fan/v1/auth/request', {'email': 'fan@example.com', 'redirectUrl': f'{SITE}/es/cuenta/verificar/'})
        self.assertTrue(mail.outbox[-1].subject.startswith('Tu código para iniciar sesión en Iguana Comedy:'))
        self.assertIn('O escribe este código:', mail.outbox[-1].body)
        self.api('post', '/api/fan/v1/auth/request', {'email': 'fan2@example.com', 'redirectUrl': f'{SITE}/en/account/verify/'})
        self.assertTrue(mail.outbox[-1].subject.startswith('Your Iguana Comedy sign-in code:'))

    def test_door_checkin_follows_the_phone_language(self):
        from django.contrib.auth.models import User

        start = self.post(f'/api/checkout/{self.mic.id}/start', {'lang': 'es', 'items': {self.seat.id: 1},
                                                                  'name': 'Ana', 'email': 'ana@example.com'}).json()
        self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {})
        ticket = Order.objects.get(pk=start['orderId']).tickets.get()
        self.client.force_login(User.objects.create_user('puerta', is_staff=True))
        page = self.client.get(f'/checkin/{ticket.checkin_token}/', HTTP_ACCEPT_LANGUAGE='es-MX,es;q=0.9').content.decode()
        self.assertIn('Registro en la puerta', page)
        self.assertIn('Registrar', page)


class MetaConversionTests(ApiTestCase):
    """What Meta gets told about a sale, and that a booking survives Meta being broken."""

    # Meta matches a server-side event on the browser that made it, so a real phone's header is part of the path.
    UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15'

    def post(self, path, body):
        return self.client.post(path, data=json.dumps(body), content_type='application/json',
                                headers={'user-agent': self.UA})

    def book(self, **body):
        payload = {'items': {self.ga.id: 2}, 'name': 'Ada Lovelace', 'email': 'Ada@Example.com', **body}
        return self.post(f'/api/checkout/{self.event.id}/start', payload).json()

    def test_hashes_match_metas_normalisation(self):
        from crm import meta_capi

        # Meta hashes the trimmed, lowercased value; a mismatch here means every conversion goes unattributed.
        self.assertEqual(meta_capi.hash_email('  Ada@Example.COM '),
                         hashlib.sha256(b'ada@example.com').hexdigest())
        self.assertEqual(meta_capi.hash_place('Playa del Carmen'),
                         hashlib.sha256(b'playadelcarmen').hexdigest())
        # Accents are stripped, not encoded: "Yucatán" and "Yucatan" must hash the same.
        self.assertEqual(meta_capi.hash_place('Yucatán'), meta_capi.hash_place('Yucatan'))
        self.assertEqual(meta_capi.hash_country('MX'), hashlib.sha256(b'mx').hexdigest())

    def test_phone_without_a_country_code_is_dropped_rather_than_guessed(self):
        from crm import meta_capi

        self.assertEqual(meta_capi.hash_phone('+52 984 123 4567'),
                         hashlib.sha256(b'529841234567').hexdigest())
        # A bare 10-digit number is Mexican or American and there is no telling which. Sending a wrong hash is
        # worse than sending none: it cannot match, and it drags the event match quality down.
        self.assertEqual(meta_capi.hash_phone('984 123 4567'), '')
        self.assertEqual(meta_capi.hash_phone(''), '')

    @override_settings(META_PIXEL_ID='123', META_CAPI_TOKEN='tok')
    def test_purchase_carries_the_click_ids_the_site_collected(self):
        from sales import ad_reporting

        sent = []
        original = ad_reporting.meta_capi.send
        ad_reporting.meta_capi.send = lambda name, **kw: sent.append((name, kw))
        try:
            start = self.book(attribution={'fbp': 'fb.1.123.456', 'fbc': 'fb.1.123.abc', 'pageUrl': f'{SITE}/en/open-mic/'})
            with self.captureOnCommitCallbacks(execute=True):
                self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {})
        finally:
            ad_reporting.meta_capi.send = original

        names = [name for name, _ in sent]
        self.assertEqual(names, ['InitiateCheckout', 'Purchase'])
        purchase = dict(sent[-1][1])
        # Without fbp/fbc Meta cannot tie the sale to the click, and the campaign reads as having sold nothing.
        self.assertEqual(purchase['user']['fbp'], 'fb.1.123.456')
        self.assertEqual(purchase['user']['fbc'], 'fb.1.123.abc')
        self.assertEqual(purchase['user']['em'], [hashlib.sha256(b'ada@example.com').hexdigest()])
        self.assertEqual(purchase['user']['client_user_agent'], self.UA)
        self.assertEqual(purchase['custom']['value'], 20.0)
        self.assertEqual(purchase['custom']['currency'], 'USD')
        self.assertEqual(purchase['source_url'], f'{SITE}/en/open-mic/')
        # Keyed on the order, so a Stripe webhook retry cannot report the same sale twice.
        self.assertEqual(purchase['event_id'], f'purchase-{start["orderId"]}')

    @override_settings(META_PIXEL_ID='123', META_CAPI_TOKEN='tok')
    def test_a_sale_completes_even_when_meta_fails(self):
        from crm import meta_capi

        original = meta_capi._post
        meta_capi._post = lambda payload: (_ for _ in ()).throw(OSError('graph.facebook.com is down'))
        try:
            start = self.book()
            with self.captureOnCommitCallbacks(execute=True):
                self.post(f'/api/checkout/orders/{start["orderId"]}/confirm', {})
        finally:
            meta_capi._post = original
        order = Order.objects.get(pk=start['orderId'])
        # The threads have their own try/except, but the point stands regardless: reporting is not the sale.
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertEqual(order.tickets.count(), 2)

    def test_nothing_is_sent_when_no_pixel_is_configured(self):
        from crm import meta_capi

        posted = []
        original = meta_capi._post
        meta_capi._post = posted.append
        try:
            meta_capi.send('Purchase', event_id='x', user={'em': ['abc']})
        finally:
            meta_capi._post = original
        self.assertEqual(posted, [])


class WeeklyEmailTests(ApiTestCase):
    """The weekly what-is-on mail: both languages, working links, and a language learned from a click."""

    def setUp(self):
        from catalog.models import Event, TicketType

        self.mic = Event.objects.create(
            name='Open Mic Night in Spanish', name_es='Noche de Open Mic en Español', slug='mic-es',
            status=Event.ACTIVE, venue=self.venue, language='es', currency='mxn',
            date=timezone.now() + timedelta(days=1), doors_open='20:00', show_time='21:00', tags=['open-mic'])
        TicketType.objects.create(event=self.mic, name='Reserved seat', price_cents=5000, capacity=60)

    def test_carries_both_languages_with_the_readers_own_first(self):
        from crm.whats_on import body, week_events

        events = week_events()
        contact = Contact.objects.create(email='lector@example.com', locale='es')
        text = body(events, contact)
        self.assertIn('Esta semana en Iguana Comedy', text)
        self.assertIn('This week at Iguana Comedy', text)
        # Their own language leads; the other follows, because 92% of this list has no language recorded and a
        # mail somebody cannot read is worse than one that is twice as long.
        self.assertLess(text.index('Esta semana'), text.index('This week'))

        english = body(events, Contact.objects.create(email='reader@example.com', locale='en'))
        self.assertLess(english.index('This week'), english.index('Esta semana'))

    def test_every_link_is_marked_with_the_contact(self):
        from crm.whats_on import body, week_events

        contact = Contact.objects.create(email='clicker@example.com')
        text = body(week_events(), contact)
        links = re.findall(r'https?://\S+', text)
        self.assertTrue(links)
        # A link with no marker teaches us nothing about who read it, which is the whole point of sending it.
        self.assertEqual([link for link in links if f'ic={contact.id}' not in link], [])

    def test_a_click_records_the_language_and_ties_the_visitor_to_the_contact(self):
        from crm.email_links import remember_click

        contact = Contact.objects.create(email='quien@example.com')
        self.assertEqual(contact.locale, '')
        remember_click(f'{SITE}/es/open-mic/?ic={contact.id}', visitor_key='v-123')
        contact.refresh_from_db()
        self.assertEqual(contact.locale, 'es')
        self.assertEqual(contact.page_visitor_key, 'v-123')
        # The English block of the same mail says the opposite, and the later click wins.
        remember_click(f'{SITE}/en/events/?ic={contact.id}')
        contact.refresh_from_db()
        self.assertEqual(contact.locale, 'en')

    def test_a_click_with_no_marker_or_no_language_changes_nothing(self):
        from crm.email_links import remember_click

        contact = Contact.objects.create(email='nobody@example.com')
        self.assertIsNone(remember_click(f'{SITE}/es/open-mic/'))
        self.assertIsNone(remember_click(f'{SITE}/?ic={contact.id}'))
        self.assertIsNone(remember_click(f'{SITE}/es/open-mic/?ic=cdoesnotexist'))
        contact.refresh_from_db()
        self.assertEqual(contact.locale, '')

    def test_the_tracking_endpoint_records_the_language(self):
        contact = Contact.objects.create(email='ingested@example.com')
        response = self.client.post('/api/ingest/pageview', content_type='application/json', data=json.dumps({
            'token': KEY, 'visitorKey': 'v-9', 'url': f'{SITE}/es/open-mic/?ic={contact.id}'}))
        self.assertEqual(response.status_code, 204)
        contact.refresh_from_db()
        self.assertEqual(contact.locale, 'es')

    def test_a_signed_in_fan_records_their_language_by_using_the_site(self):
        contact = Contact.objects.create(email='socio@example.com')
        token = self.sign_in('socio@example.com')
        self.client.get('/api/fan/v1/account/profile', HTTP_AUTHORIZATION=f'Bearer {KEY}',
                        HTTP_X_CUSTOMER_AUTHORIZATION=f'Bearer {token}', HTTP_X_IGUANA_LOCALE='es')
        contact.refresh_from_db()
        self.assertEqual(contact.locale, 'es')

    def test_the_email_route_table_matches_the_sites_real_routes(self):
        """The links are built in Python from a copy of src/i18n/routes.ts. A dead link in a newsletter is only
        ever found by the person who clicked it, so the copy is checked against the original."""
        import pathlib
        import re as regex

        from crm.whats_on import PATHS

        routes = (pathlib.Path(__file__).resolve().parents[2] / 'src' / 'i18n' / 'routes.ts').read_text()
        blocks = dict(regex.findall(r'\b(en|es):\s*\{(.*?)\n  \}', routes, regex.S)[:2])
        self.assertEqual(sorted(blocks), ['en', 'es'])
        for key, by_lang in PATHS.items():
            for lang, path in by_lang.items():
                match = regex.search(rf'\b{key}:\s*"([^"]+)"', blocks[lang])
                self.assertIsNotNone(match, f'{key} is not in routes.ts under {lang}')
                expected = f'/{lang}{match.group(1)}'.replace(':slug', '{slug}')
                self.assertEqual(path, expected, f'{key} ({lang}) has drifted from routes.ts')

    def test_nothing_on_means_no_email(self):
        from catalog.models import Event
        from crm.whats_on import week_events

        Event.objects.all().update(status=Event.DRAFT)
        self.assertEqual(week_events(), [])
