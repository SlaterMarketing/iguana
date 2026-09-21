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
    """Sign-ups ask for confirmation; confirming joins "Newsletter", and a city page also joins its alert list.

    Joining used to be immediate. It is not any more: a bot filled this form 59 times with scraped addresses
    and nothing about the requests could be told from a person's. See NewsletterOptInTests.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        FormEndpoint.objects.create(slug='newsletter', intent='newsletter', title='Newsletter')

    def signup(self, email, context=None):
        return self.api('post', '/api/public/v1/endpoints/newsletter/submit',
                        {'email': email, 'fields': {'locale': 'es'}, 'context': context or {}})

    def confirm(self, email):
        from crm.optin import token_for

        return self.client.get(f'/newsletter/confirm/{token_for(email)}')

    def test_signup_asks_for_confirmation_and_never_alerts_the_owner(self):
        from crm.models import ContactList

        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            self.assertTrue(self.signup('Fan@Example.com').json()['ok'])
            self.signup('fan@example.com')  # signing up twice is harmless
        # One confirmation to the reader, and nothing at all to the owner: a sign-up is not an enquiry.
        self.assertEqual([m.to for m in mail.outbox], [['fan@example.com'], ['fan@example.com']])
        self.assertFalse(ContactList.objects.filter(name='Newsletter', contacts__email='fan@example.com').exists())

        self.confirm('fan@example.com')
        members = ContactList.objects.get(name='Newsletter').contacts.all()
        self.assertEqual([c.email for c in members], ['fan@example.com'])
        self.assertEqual(Contact.objects.get(email='fan@example.com').source, 'NEWSLETTER')

    def test_city_signup_also_joins_that_citys_alert_list(self):
        from crm.models import ContactList

        self.signup('cancun@example.com', {'citySlug': 'cancun', 'cityLabel': 'Cancún'})
        self.confirm('cancun@example.com')
        self.assertEqual(sorted(ContactList.objects.filter(contacts__email='cancun@example.com').values_list('name', flat=True)),
                         ['City alerts: Cancún', 'Newsletter'])
        self.signup('bad@example.com', {'citySlug': '<script>', 'cityLabel': 'x'})
        self.confirm('bad@example.com')
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

    def test_setup_publishes_without_stripe_but_offers_no_drinks(self):
        """It used to refuse outright, because a seat cost 50 pesos and nobody could pay. A free seat needs no
        card, so the night goes up regardless; only the upsell waits for Stripe. An add-on nobody can pay for
        would be worse than none, since it puts a price on a page advertising the night as free."""
        from io import StringIO

        from django.core.management import call_command

        spanish = self.spanish_night()
        call_command('setup_open_mics', stdout=StringIO())
        spanish.refresh_from_db()
        self.assertEqual(spanish.status, Event.ACTIVE)
        seat = spanish.ticket_types.get()
        self.assertEqual(seat.price_cents, 0)
        self.assertFalse(seat.is_addon)

    def test_pay_at_door_still_marks_the_seat_and_says_so(self):
        from io import StringIO

        from django.core.management import call_command

        spanish = self.spanish_night()
        call_command('setup_open_mics', '--pay-at-door', stdout=StringIO())
        seat = spanish.ticket_types.get(is_addon=False)
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
        seat = spanish.ticket_types.get(is_addon=False)
        self.assertEqual((seat.name, seat.name_es, seat.price_cents, seat.capacity, seat.max_per_order, seat.pay_at_door),
                         ('Free reserved seat', 'Lugar reservado gratis', 0, 60, 6, False))
        # The sale. Priced in the night's own currency and never auto-selected.
        drinks = spanish.ticket_types.get(is_addon=True)
        self.assertEqual((drinks.price_cents, drinks.max_per_order), (10000, 6))
        self.assertIn('bebidas', drinks.name_es)
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
        self.assertEqual(spanish.ticket_types.count(), 2, 'the seat and the drinks, never duplicated')

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_setup_renames_a_spanish_named_type_instead_of_duplicating_it(self):
        from io import StringIO

        from django.core.management import call_command

        spanish = self.spanish_night()
        TicketType.objects.create(event=spanish, name='Lugar reservado + 1 bebida gratis', price_cents=5000, pay_at_door=True)
        call_command('setup_open_mics', stdout=StringIO())
        seat = spanish.ticket_types.get(is_addon=False)
        self.assertEqual((seat.name, seat.name_es, seat.pay_at_door),
                         ('Free reserved seat', 'Lugar reservado gratis', False))
        self.assertEqual(seat.price_cents, 0, 'the 31 nights already on sale must be repriced, not duplicated')

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_the_paid_seat_already_live_is_made_free_rather_than_duplicated(self):
        """Production had 31 nights carrying "Reserved seat + 1 free drink" at 5000 cents when the seat became
        free. Matching only the new name would have left every one of them priced and added a second type."""
        from io import StringIO

        from django.core.management import call_command

        spanish = self.spanish_night()
        TicketType.objects.create(event=spanish, name='Reserved seat + 1 free drink', price_cents=5000)
        call_command('setup_open_mics', stdout=StringIO())
        self.assertEqual(spanish.ticket_types.filter(is_addon=False).count(), 1)
        self.assertEqual(spanish.ticket_types.get(is_addon=False).price_cents, 0)


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
    def test_starting_to_fill_the_form_is_what_reports_initiatecheckout(self):
        """The reservation ad sets optimise on InitiateCheckout because it should be commoner than Purchase.
        It was first wired to the submit, which made it nearly as rare and left the campaigns nothing to learn
        from: 44 landing page views produced 0 of them on the first day live."""
        from sales import ad_reporting

        sent = []
        original = ad_reporting.meta_capi.send
        ad_reporting.meta_capi.send = lambda name, **kw: sent.append((name, kw))
        try:
            response = self.client.post(
                f'/api/checkout/{self.event.id}/engaged', content_type='application/json',
                headers={'user-agent': self.UA},
                data=json.dumps({'lang': 'es', 'valueCents': 5000, 'key': 'abc',
                                 'attribution': {'fbp': 'fb.1.9.9', 'fbc': 'fb.1.9.click',
                                                 'pageUrl': f'{SITE}/es/open-mic/'}}))
        finally:
            ad_reporting.meta_capi.send = original
        self.assertEqual(response.status_code, 204)
        self.assertEqual([n for n, _ in sent], ['InitiateCheckout'])
        kw = sent[0][1]
        self.assertEqual(kw['user']['fbc'], 'fb.1.9.click')
        self.assertEqual(kw['user']['client_user_agent'], self.UA)
        self.assertEqual(kw['custom']['value'], 50.0)
        self.assertEqual(kw['event_id'], 'ic-abc', 'keyed so retyping is not three separate events')

    def test_the_engaged_beacon_never_breaks_and_never_500s(self):
        # It sits on the path to a sale. A bad body, an unknown show or a dead Meta must all be a quiet 204.
        for body in ('{}', '{"valueCents": "not a number"}', 'not json at all'):
            self.assertEqual(self.client.post(f'/api/checkout/{self.event.id}/engaged',
                                              content_type='application/json', data=body).status_code, 204)
        self.assertEqual(self.client.post('/api/checkout/does-not-exist/engaged',
                                          content_type='application/json', data='{}').status_code, 204)

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
        self.assertEqual(names, ['AddPaymentInfo', 'Purchase'])
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

    def test_an_empty_lede_file_option_is_not_the_working_directory(self):
        """`pathlib.Path('') == Path('.')`, which exists and is a directory, so an empty default would make every
        hand-run of the command die on "Is a directory". Found by running it on production."""
        from crm.management.commands.send_whats_on import Command

        parser = Command().create_parser('manage.py', 'send_whats_on')
        self.assertIsNone(parser.parse_args([]).lede_file)


class FormSpamTests(ApiTestCase):
    """The contact form had no gate and a bot found it: 15 submissions in three days, every one a random
    string, and every one emailed the owner. The rows were never the cost; the alert going unread was."""

    def submit(self, slug, fields, email='someone@example.com'):
        return self.api('post', f'/api/public/v1/endpoints/{slug}/submit', {'email': email, 'fields': fields})

    def test_a_real_enquiry_still_gets_through_and_still_alerts(self):
        from catalog.models import FormSubmission

        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            response = self.submit('contact', {'name': 'Ada', 'message': 'Do you take group bookings?'})
        self.assertEqual(response.status_code, 200)
        row = FormSubmission.objects.latest('created_at')
        self.assertFalse(row.handled)
        self.assertNotIn('spam', row.context)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_random_string_is_dropped_without_alerting(self):
        from catalog.models import FormSubmission

        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            # The exact shape the live bot sends: one unbroken run, no spaces, no name.
            response = self.submit('contact', {'message': 'qjWYpEHreBSHUKwJlWwkQGD'})
        # Answered exactly like a real one: telling a bot which gate caught it is how it learns to pass.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        row = FormSubmission.objects.latest('created_at')
        self.assertEqual(row.context.get('spam'), 'random_text')
        self.assertTrue(row.handled, 'spam must not sit in the backlog as a person waiting for an answer')
        self.assertEqual(mail.outbox, [])

    def test_a_filled_honeypot_is_dropped(self):
        from catalog.models import FormSubmission
        from catalog.spam import HONEYPOT_FIELD

        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            self.submit('contact', {'message': 'Hola, quiero reservar', HONEYPOT_FIELD: 'http://spam.example'})
        self.assertEqual(FormSubmission.objects.latest('created_at').context.get('spam'), 'honeypot')
        self.assertEqual(mail.outbox, [])

    def test_ordinary_short_answers_are_not_mistaken_for_tokens(self):
        from catalog.spam import looks_like_a_person_wrote_it

        for text in ('Hola', 'gracias!', 'Do you take group bookings?', '', 'si', 'Yes please'):
            self.assertTrue(looks_like_a_person_wrote_it(text), text)
        for text in ('qjWYpEHreBSHUKwJlWwkQGD', 'txfyHCRLeIwqciJGuOgYO', 'iCwiEKVTQCOsfZGlCg'):
            self.assertFalse(looks_like_a_person_wrote_it(text), text)

    def test_a_newsletter_signup_is_never_judged_on_free_text_it_does_not_have(self):
        from catalog.models import FormEndpoint, FormSubmission

        FormEndpoint.objects.create(slug='newsletter', intent='newsletter')
        self.submit('newsletter', {}, email='reader@example.com')
        self.assertFalse(FormSubmission.objects.latest('created_at').handled)


class NewsletterOptInTests(ApiTestCase):
    """An address joins the list only when somebody proves they can read it.

    Every newsletter sign-up this site ever received came from one bot: `Europe/Moscow` on all 59, arriving
    through Tor exits, paced so the rate never looked like a burst, carrying scraped addresses belonging to
    real strangers. It sent exactly what the real form sends, so no check on the request could tell them
    apart. The Monday send was hours from being this domain's first bulk mail, to 59 people who never asked.
    """

    def sign_up(self, email='reader@example.com', fields=None):
        from catalog.models import FormEndpoint

        FormEndpoint.objects.get_or_create(slug='newsletter', defaults={'intent': 'newsletter'})
        return self.api('post', '/api/public/v1/endpoints/newsletter/submit',
                        {'email': email, 'fields': fields or {'locale': 'en'}})

    def test_signing_up_does_not_put_you_on_the_list(self):
        from crm.models import ContactList

        mail.outbox.clear()
        self.assertEqual(self.sign_up().status_code, 200)
        contact = Contact.objects.get(email='reader@example.com')
        self.assertFalse(contact.subscribed, 'an unconfirmed address must never be mailable')
        self.assertFalse(contact.email_marketing_eligible)
        self.assertFalse(ContactList.objects.filter(name='Newsletter', contacts=contact).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Confirm', mail.outbox[0].subject)

    def test_the_unconfirmed_are_not_in_the_weekly_send(self):
        from crm.mail import marketing_recipients

        self.sign_up()
        contact = Contact.objects.get(email='reader@example.com')
        self.assertEqual(marketing_recipients([contact]), [])

    def test_clicking_the_link_is_what_subscribes_you(self):
        from crm.models import ContactList
        from crm.optin import token_for

        self.sign_up()
        response = self.client.get(f'/newsletter/confirm/{token_for("reader@example.com")}')
        self.assertEqual(response.status_code, 200)
        contact = Contact.objects.get(email='reader@example.com')
        self.assertTrue(contact.subscribed)
        self.assertTrue(ContactList.objects.filter(name='Newsletter', contacts=contact).exists())

    def test_a_forged_or_expired_token_subscribes_nobody(self):
        self.sign_up()
        for bad in ('not-a-token', 'YnJva2Vu:fake:sig'):
            self.assertEqual(self.client.get(f'/newsletter/confirm/{bad}').status_code, 200)
        self.assertFalse(Contact.objects.get(email='reader@example.com').subscribed)

    def test_an_unsubscribe_token_cannot_be_used_to_subscribe(self):
        """Different salts, so a link from the foot of an old newsletter cannot re-add a person who left."""
        from crm.unsubscribe import token_for as unsub_token

        self.sign_up()
        self.client.get(f'/newsletter/confirm/{unsub_token("reader@example.com")}')
        self.assertFalse(Contact.objects.get(email='reader@example.com').subscribed)

    def test_a_city_alert_signup_lands_on_the_city_list_after_confirming(self):
        from crm.models import ContactList
        from crm.optin import token_for

        from catalog.models import FormEndpoint

        FormEndpoint.objects.get_or_create(slug='newsletter', defaults={'intent': 'newsletter'})
        self.api('post', '/api/public/v1/endpoints/newsletter/submit',
                 {'email': 'tulum@example.com', 'fields': {'locale': 'en'},
                  'context': {'citySlug': 'tulum', 'cityLabel': 'Tulum'}})
        self.client.get(f'/newsletter/confirm/{token_for("tulum@example.com")}')
        contact = Contact.objects.get(email='tulum@example.com')
        self.assertTrue(ContactList.objects.filter(name='City alerts: Tulum', contacts=contact).exists())

    def test_a_filled_honeypot_sends_no_confirmation_at_all(self):
        """The opt-in gate alone keeps a scraped address off the list, but still puts our name in a stranger's
        inbox once. On its first night live the bot filled the contact form's honeypot 3 times out of 3, so it
        renders forms and fills hidden inputs: catching it here costs it the email too."""
        from catalog.models import FormSubmission
        from catalog.spam import HONEYPOT_FIELD

        mail.outbox.clear()
        self.sign_up('scraped@example.com', {'locale': 'en', HONEYPOT_FIELD: 'http://spam.example'})
        self.assertEqual(mail.outbox, [], 'a scraped address must not be emailed at all')
        self.assertEqual(FormSubmission.objects.latest('created_at').context.get('spam'), 'honeypot')
        self.assertFalse(Contact.objects.filter(email='scraped@example.com').exists(),
                         'a rejected sign-up should not even create a contact')

    def test_asking_again_does_not_unsubscribe_someone_already_confirmed(self):
        from crm.optin import token_for

        self.sign_up()
        self.client.get(f'/newsletter/confirm/{token_for("reader@example.com")}')
        self.sign_up()
        self.assertTrue(Contact.objects.get(email='reader@example.com').subscribed)


class FreeReservationTests(ApiTestCase):
    """The open mic seat is free and the drinks are the sale.

    At 50 MXN a seat the first day of ads produced 44 landing page views and zero checkouts. Free removes the
    payment barrier from the thing the ad promises, and moves the money to an upsell offered only after the
    free thing has been claimed.
    """

    def setUp(self):
        from catalog.models import Event, TicketType

        self.mic = Event.objects.create(
            name='Open Mic Night in Spanish', slug='mic-free', status=Event.ACTIVE, venue=self.venue,
            language='es', currency='mxn', date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        self.seat = TicketType.objects.create(event=self.mic, name='Free reserved seat', price_cents=0, capacity=60)
        self.drinks = TicketType.objects.create(event=self.mic, name='2 drinks', price_cents=10000,
                                                is_addon=True, max_per_order=6)

    def post(self, path, body):
        return self.client.post(path, data=json.dumps(body), content_type='application/json')

    def book(self, items, email='fan@example.com'):
        return self.post(f'/api/checkout/{self.mic.id}/start',
                         {'items': items, 'name': 'Ada Lovelace', 'email': email, 'lang': 'es'})

    def test_a_seat_alone_costs_nothing_and_completes_without_a_card(self):
        from sales.models import Order

        with self.captureOnCommitCallbacks(execute=True):
            body = self.book({self.seat.id: 1}).json()
        self.assertTrue(body['complete'], 'a free reservation must not ask for a card')
        self.assertNotIn('clientSecret', body)
        order = Order.objects.get(pk=body['orderId'])
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertEqual(order.total_amount_cents, 0)
        self.assertEqual(order.tickets.count(), 1)
        self.assertIn('fan@example.com', mail.outbox[-1].to)

    def test_adding_drinks_is_what_asks_for_payment(self):
        quote = self.post(f'/api/checkout/{self.mic.id}/quote',
                          {'items': {self.seat.id: 1, self.drinks.id: 1}}).json()
        self.assertEqual(quote['totalCents'], 10000)
        body = self.book({self.seat.id: 1, self.drinks.id: 1}).json()
        self.assertFalse(body['complete'], 'adding drinks must stop it completing for free')
        self.assertEqual(body['totalCents'], 10000)

    def test_one_free_reservation_per_email_per_night(self):
        """Nothing paid up front means nothing stops one person taking the whole room."""
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(self.book({self.seat.id: 1}).json()['complete'])
        second = self.book({self.seat.id: 1})
        self.assertEqual(second.status_code, 400, 'the refusal must reach the customer, not 500 at them')
        # Booked in Spanish, so the refusal comes back in Spanish: the guard goes through the same translation
        # as every other checkout error.
        self.assertIn('Ya tienes una reservación', second.json()['error'])

    def test_a_paid_order_is_not_blocked_by_the_free_guard(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.book({self.seat.id: 1})
        # Same person coming back to buy drinks must not be turned away by the free-seat limit.
        second = self.book({self.seat.id: 1, self.drinks.id: 1})
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()['complete'])

    def test_the_addon_is_marked_as_one_in_the_json_the_widget_reads(self):
        page = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=en').content.decode()
        self.assertIn('"isAddon": true', page)
        self.assertIn('"isAddon": false', page)
        self.assertIn('Want to order your drinks in advance?', page)
        spanish = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=es').content.decode()
        self.assertIn('¿Quieres pedir tus bebidas por adelantado?', spanish)


class ConfirmationEmailCannotBreakABookingTests(ApiTestCase):
    """A completed reservation must survive a refused confirmation email.

    Found on production the night reservations became free: the confirmation is sent on_commit, so it runs
    inside the request, and an address the mail server refused raised SMTPRecipientsRefused straight through a
    checkout that had already created AND completed the order. The customer saw a 500 and held a valid ticket.
    Free bookings mean far more addresses typed by people with nothing at stake, so a typo must cost the email
    and nothing else.
    """

    def setUp(self):
        from catalog.models import Event, TicketType

        self.mic = Event.objects.create(name='Open Mic', slug='mic-mail', status=Event.ACTIVE, venue=self.venue,
                                        currency='mxn', date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        self.seat = TicketType.objects.create(event=self.mic, name='Free reserved seat', price_cents=0, capacity=60)

    def test_a_refused_address_does_not_500_a_completed_reservation(self):
        import smtplib
        from unittest import mock

        from sales.models import Order

        refused = smtplib.SMTPRecipientsRefused({'nope@example.com': (550, b'User unknown')})
        # Patch the SMTP socket, not Django's send_messages: `fail_silently` is implemented INSIDE the backend,
        # so mocking the backend method tests the mock instead of the protection.
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'), \
                mock.patch('smtplib.SMTP') as smtp:
            smtp.return_value.sendmail.side_effect = refused
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f'/api/checkout/{self.mic.id}/start', content_type='application/json',
                    data=json.dumps({'items': {self.seat.id: 1}, 'name': 'Ada', 'email': 'nope@example.com'}))
        self.assertEqual(response.status_code, 200, 'the booking succeeded; the email is not the booking')
        self.assertTrue(response.json()['complete'])
        order = Order.objects.get(pk=response.json()['orderId'])
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertEqual(order.tickets.count(), 1, 'the seat is held even though we could not write about it')


class TemplateCommentTests(TestCase):
    """Django's `{# ... #}` is a SINGLE LINE comment. Spread one over two lines and it is not a comment at
    all, it is text, and it renders to whoever is looking at the page.

    That is not hypothetical: a note explaining why the drinks upsell sits below the name and email was
    written that way and appeared, in full, in the middle of the live checkout, between a customer's email
    field and the thing it was trying to sell them.
    """

    def test_no_hash_comment_spans_more_than_one_line(self):
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for path in root.rglob('templates/**/*.html'):
            text = path.read_text()
            for match in re.finditer(r'\{#', text):
                end = text.find('#}', match.start())
                body = text[match.start():end + 2] if end != -1 else text[match.start():]
                if '\n' in body:
                    line = text[:match.start()].count('\n') + 1
                    offenders.append(f'{path.relative_to(root)}:{line}')
        self.assertEqual(offenders, [], 'use {% comment %}...{% endcomment %} for anything over one line')


class StaleBlurbTests(ApiTestCase):
    """A night already on sale must stop advertising something that is no longer true.

    `setup_open_mics` only ever filled BLANK descriptions, so when the seat became free and the drink became
    the thing being sold, all 31 nights carried on promising "incluye una bebida gratis" on their own pages.
    A hand-written blurb still has to survive, so the rule is: replace what this command wrote before, never
    what somebody typed.
    """

    def spanish_night(self):
        from catalog.models import Event

        return Event.objects.create(name='Noche de Open Mic - Espanol!', slug='noche-open-mic-blurb',
                                    venue=self.venue, date=timezone.now() + timedelta(days=6))

    def run_setup(self):
        from io import StringIO

        from django.core.management import call_command

        call_command('setup_open_mics', stdout=StringIO())

    def test_a_blurb_this_command_wrote_before_is_corrected(self):
        from catalog.models import Event

        old_es = ('Stand-up gratis cada semana en Iguana Comedy, Playa del Carmen. Cualquiera puede anotarse '
                  'para hacer cinco minutos, o simplemente venir a ver. La entrada es gratis, y tu reservación '
                  'te aparta el lugar e incluye una bebida gratis.')
        night = self.spanish_night()
        Event.objects.filter(pk=night.pk).update(description_es=old_es)
        self.run_setup()
        night.refresh_from_db()
        self.assertNotIn('bebida gratis', night.description_es)
        self.assertIn('reservar también', night.description_es.lower())

    def test_a_blurb_somebody_wrote_by_hand_is_left_alone(self):
        from catalog.models import Event

        mine = 'Esta noche es especial: viene un invitado sorpresa.'
        night = self.spanish_night()
        Event.objects.filter(pk=night.pk).update(description_es=mine)
        self.run_setup()
        night.refresh_from_db()
        self.assertEqual(night.description_es, mine)


class ReservationAlertTests(ApiTestCase):
    """The club is told when a seat goes.

    Contact enquiries have always emailed hello@; bookings never did. The first two reservations this club
    ever took online were found by querying the database by hand, half an hour after they happened.
    """

    def setUp(self):
        from catalog.models import Event, TicketType

        self.mic = Event.objects.create(name='Open Mic Night in Spanish', slug='mic-alert', status=Event.ACTIVE,
                                        venue=self.venue, currency='mxn',
                                        date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        self.seat = TicketType.objects.create(event=self.mic, name='Free reserved seat', price_cents=0, capacity=60)
        self.drinks = TicketType.objects.create(event=self.mic, name='2 drinks', price_cents=10000, is_addon=True)

    def book(self, items, email='fan@example.com'):
        return self.client.post(f'/api/checkout/{self.mic.id}/start', content_type='application/json',
                                data=json.dumps({'items': items, 'name': 'Ada Lovelace', 'email': email}))

    def alert(self):
        return next(m for m in mail.outbox if 'hello@example.com' in m.to)

    def test_a_free_reservation_alerts_the_club_with_what_the_door_needs(self):
        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            with self.captureOnCommitCallbacks(execute=True):
                self.book({self.seat.id: 2})
        alert = self.alert()
        # The subject is all a phone shows, so it has to carry the count and the night.
        self.assertIn('2 seats reserved', alert.subject)
        self.assertIn('Open Mic Night in Spanish', alert.subject)
        self.assertIn('fan@example.com', alert.body)
        self.assertIn('nothing, the seat is free', alert.body)
        self.assertIn('Total reserved for this night so far: 2', alert.body)

    def test_drinks_ordered_in_advance_are_named_in_the_alert(self):
        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            with self.captureOnCommitCallbacks(execute=True):
                start = self.book({self.seat.id: 1, self.drinks.id: 2}).json()
                self.client.post(f'/api/checkout/orders/{start["orderId"]}/confirm', content_type='application/json',
                                 data='{}')
        alert = self.alert()
        self.assertIn('1 seat reserved', alert.subject)
        self.assertIn('200 MXN', alert.subject, 'the bar needs to know money came in')
        self.assertIn('2 x 2 drinks', alert.body)

    def test_the_customer_still_gets_their_own_confirmation(self):
        mail.outbox.clear()
        with self.settings(NOTIFY_EMAILS=['hello@example.com']):
            with self.captureOnCommitCallbacks(execute=True):
                self.book({self.seat.id: 1})
        self.assertEqual(sorted(sum((m.to for m in mail.outbox), [])), ['fan@example.com', 'hello@example.com'])

    def test_an_undeliverable_alert_cannot_undo_a_booking(self):
        import smtplib
        from unittest import mock

        from sales.models import Order

        refused = smtplib.SMTPRecipientsRefused({'hello@example.com': (550, b'nope')})
        with self.settings(NOTIFY_EMAILS=['hello@example.com'],
                           EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'), \
                mock.patch('smtplib.SMTP') as smtp:
            smtp.return_value.sendmail.side_effect = refused
            with self.captureOnCommitCallbacks(execute=True):
                response = self.book({self.seat.id: 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.get(pk=response.json()['orderId']).status, Order.COMPLETED)


class DemandLineTests(ApiTestCase):
    """The line above the reserve button has to be true, and worth saying.

    Urgency that overstates is worse than none: the visitor either notices and stops trusting the page, or
    does not and we have taught ourselves to read a number that means nothing.
    """

    def setUp(self):
        from catalog.models import Event, TicketType

        self.mic = Event.objects.create(name='Open Mic', slug='mic-demand', status=Event.ACTIVE, venue=self.venue,
                                        currency='mxn', date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        self.seat = TicketType.objects.create(event=self.mic, name='Free reserved seat', price_cents=0, capacity=60)
        self.drinks = TicketType.objects.create(event=self.mic, name='2 drinks', price_cents=10000, is_addon=True)

    def reserve(self, seats, email, ago=timedelta(0), drinks=0):
        from sales.models import Order, OrderItem

        order = Order.objects.create(event=self.mic, event_name=self.mic.name, customer_email=email,
                                     currency='mxn', status=Order.COMPLETED,
                                     completed_at=timezone.now() - ago)
        OrderItem.objects.create(order=order, ticket_type=self.seat, name='seat', quantity=seats, unit_price_cents=0)
        if drinks:
            OrderItem.objects.create(order=order, ticket_type=self.drinks, name='drinks', quantity=drinks,
                                     unit_price_cents=10000)
        return order

    def test_the_window_named_is_the_tightest_one_that_is_true(self):
        from sales.demand import demand

        self.reserve(1, 'a@example.com', timedelta(minutes=20))
        self.reserve(1, 'b@example.com', timedelta(minutes=40))
        self.assertEqual(demand(self.mic)['recentWindow'], 'in the last hour')

    def test_an_older_pair_is_described_as_older(self):
        from sales.demand import demand

        self.reserve(1, 'a@example.com', timedelta(hours=9))
        self.reserve(1, 'b@example.com', timedelta(hours=10))
        d = demand(self.mic)
        self.assertEqual(d['recent'], 2)
        self.assertEqual(d['recentWindow'], 'in the last day',
                         'two bookings from yesterday must never be called "the last hour"')

    def test_a_single_booking_says_nothing(self):
        from sales.demand import demand

        self.reserve(1, 'a@example.com')
        self.assertEqual(demand(self.mic)['recent'], 0, 'one reservation is not social proof')

    def test_drinks_do_not_count_as_seats(self):
        from sales.demand import demand

        self.reserve(1, 'a@example.com', drinks=4)
        self.assertEqual(demand(self.mic)['taken'], 1, 'a round of drinks is not four more people in the room')

    def test_the_bar_stays_hidden_while_the_room_looks_empty(self):
        from sales.demand import demand

        self.reserve(2, 'a@example.com')
        self.assertFalse(demand(self.mic)['showBar'], '2 of 60 tells somebody not to bother coming')
        self.reserve(20, 'b@example.com')
        self.assertTrue(demand(self.mic)['showBar'])

    def test_it_is_in_the_json_the_widget_reads(self):
        self.reserve(1, 'a@example.com', timedelta(minutes=5))
        self.reserve(1, 'b@example.com', timedelta(minutes=6))
        page = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=es').content.decode()
        self.assertIn('"recent": 2', page)
        self.assertIn('personas reservaron', page)
