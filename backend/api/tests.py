import hashlib
import json
from zoneinfo import ZoneInfo
import pathlib
import re
from unittest.mock import patch
from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Artist, Event, FormEndpoint, LineupEntry, TicketType, Venue
from crm.models import Contact
from sales.models import LoginToken, Membership, MembershipPlan, Order, OrderItem, Ticket

CANCUN_TZ = ZoneInfo('America/Cancun')

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

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_a_real_payment_webhook_completes_the_order(self):
        """The one test that matters here, and the one that was missing.

        Only the bad-signature path was covered, so nothing ever ran a real event through the handler. It
        500'd on every single `payment_intent.succeeded` because `construct_event` hands back a Stripe object
        and the code called `.get()` on it. The browser normally completes the order itself, so the webhook is
        the backstop for when it does not come back: precisely the case where nobody is watching, and a paid
        order sits PENDING with no ticket and nobody complaining.
        """
        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='paid@example.com',
                                     currency='mxn', total_amount_cents=30000, status=Order.PENDING)
        OrderItem.objects.create(order=order, ticket_type=self.ga, name='GA', quantity=1, unit_price_cents=30000)
        body = self._signed({
            'id': 'evt_1', 'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_1', 'object': 'payment_intent', 'latest_charge': 'ch_1',
                                'metadata': {'purpose': 'tickets', 'order_id': order.id}}},
        })
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post('/api/stripe/webhook', data=body['payload'], content_type='application/json',
                                   HTTP_STRIPE_SIGNATURE=body['signature'])
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertEqual(order.stripe_charge_id, 'ch_1')
        self.assertEqual(order.tickets.count(), 1)

    def _signed(self, event):
        """A payload signed the way Stripe signs one, so `construct_event` returns a real Stripe object and the
        handler is exercised as it is in production rather than against a convenient dict."""
        import hashlib
        import hmac
        import time

        payload = json.dumps(event)
        timestamp = int(time.time())
        digest = hmac.new(b'whsec_test', f'{timestamp}.{payload}'.encode(), hashlib.sha256).hexdigest()
        return {'payload': payload, 'signature': f't={timestamp},v1={digest}'}

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
        # No drinks in the checkout. Over the two days it ran on a free seat it was ordered by nobody, while
        # sitting between the last form field and the reserve button, so every visitor paid for it in scroll.
        # The menu goes out after the seat is held instead. `SELL_DRINKS_AT_CHECKOUT` turns it back on.
        self.assertFalse(spanish.ticket_types.filter(is_addon=True, active=True).exists())
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
        self.assertEqual(spanish.ticket_types.count(), 1, 'the seat, and only ever one of it')

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

    def test_the_window_shown_is_the_one_holding_the_most(self):
        """Two in the last hour and two more this afternoon is four people, not two.

        Preferring the tightest window that cleared the floor threw the older pair away and advertised the
        smaller number. Every window here is a true statement about the same orders; this picks the fullest.
        """
        from sales.demand import demand

        self.reserve(2, 'a@example.com', timedelta(minutes=30))
        self.reserve(2, 'b@example.com', timedelta(hours=4))
        d = demand(self.mic)
        self.assertEqual((d['recent'], d['recentWindow']), (4, 'in the last few hours'))

    def test_a_window_can_never_claim_more_than_it_holds(self):
        """The rule it replaced existed to stop "the last hour" describing something that took a day. It still
        cannot: a window is only ever offered its own count."""
        from sales.demand import demand

        self.reserve(3, 'a@example.com', timedelta(hours=20))
        d = demand(self.mic)
        self.assertEqual(d['recentWindow'], 'in the last day')
        self.assertEqual(d['recentByWindow']['in the last hour'], 0)

    def test_every_window_is_published_so_a_page_can_add_nights_up(self):
        """The home page shows one line for both nights. Without the per-window counts it had to sum each
        night's own window and label the total with the widest, which undercounts: 4 and 3 came out as 5."""
        from sales.demand import demand, demand_for

        other = Event.objects.create(name='Other mic', slug='mic-demand-2', status=Event.ACTIVE, venue=self.venue,
                                     currency='mxn', date=timezone.now() + timedelta(days=3), tags=['open-mic'])
        seat = TicketType.objects.create(event=other, name='Free reserved seat', price_cents=0, capacity=60)
        from sales.models import Order, OrderItem
        for i, ago in enumerate((timedelta(hours=3), timedelta(hours=3), timedelta(hours=3))):
            o = Order.objects.create(event=other, event_name=other.name, customer_email=f'o{i}@example.com',
                                     currency='mxn', status=Order.COMPLETED, completed_at=timezone.now() - ago)
            OrderItem.objects.create(order=o, ticket_type=seat, name='seat', quantity=1, unit_price_cents=0)

        self.reserve(2, 'a@example.com', timedelta(minutes=30))   # this night narrows to the hour
        self.reserve(2, 'b@example.com', timedelta(hours=4))

        mine = demand(self.mic)
        theirs = demand_for([self.mic, other])[other.id]
        total = mine['recentByWindow']['in the last few hours'] + theirs['recentByWindow']['in the last few hours']
        self.assertEqual(total, 7, 'four seats and three seats is seven, whatever each night calls its own window')
        self.assertEqual(demand_for([self.mic, other])[self.mic.id], mine, 'and both code paths agree')

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

    def test_the_listing_carries_it_too(self):
        """The site puts the same line under the home page hero and on every event card, so it has to come back
        from the list endpoint and not only from the single-event payload the iframe reads."""
        self.reserve(1, 'a@example.com', timedelta(minutes=5))
        self.reserve(1, 'b@example.com', timedelta(minutes=6))
        rows = self.api('get', '/api/public/v1/events').json()['events']
        mine = next(e for e in rows if e['id'] == self.mic.id)
        self.assertEqual(mine['demand']['recent'], 2)
        self.assertEqual(mine['demand']['recentWindow'], 'in the last hour')

    def test_the_bulk_and_single_counts_cannot_drift(self):
        """`demand_for` exists only so a listing page is not 2N queries. The moment the two disagree, the home
        page and the reserve button start telling a visitor different things about the same night."""
        from sales.demand import demand, demand_for

        self.reserve(3, 'a@example.com', timedelta(minutes=5))
        self.reserve(19, 'b@example.com', timedelta(hours=30), drinks=6)
        other = Event.objects.create(name='Quiet night', slug='quiet-demand', status=Event.ACTIVE, venue=self.venue,
                                     date=timezone.now() + timedelta(days=3))
        TicketType.objects.create(event=other, name='GA', price_cents=0, capacity=40)

        events = [self.mic, other, self.event]
        self.assertEqual(demand_for(events), {e.id: demand(e) for e in events if demand(e)})

    def test_a_listing_does_not_cost_a_query_per_row(self):
        from sales.demand import demand_for

        self.reserve(2, 'a@example.com')
        events = list(Event.objects.all())
        with self.assertNumQueries(2):
            demand_for(events)

    def test_a_host_page_can_take_the_line_over_without_it_showing_twice(self):
        """The open mic lander prints it in its own header, beside the date, rather than under the night pills.
        Two copies of the same sentence on one page reads as a glitch."""
        self.reserve(1, 'a@example.com', timedelta(minutes=5))
        self.reserve(1, 'b@example.com', timedelta(minutes=6))
        on = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=es').content.decode()
        off = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=es&demand=0').content.decode()
        self.assertIn('id="demand-line"', on)
        self.assertNotIn('id="demand-line"', off)
        # The numbers still travel, so the host page has something to print.
        self.assertIn('"recent": 2', off)

    def test_it_is_in_the_json_the_widget_reads(self):
        self.reserve(1, 'a@example.com', timedelta(minutes=5))
        self.reserve(1, 'b@example.com', timedelta(minutes=6))
        page = self.client.get(f'/embed/event/{self.mic.id}?embedded=1&lang=es').content.decode()
        self.assertIn('"recent": 2', page)
        self.assertIn('personas reservaron', page)


CHECKOUT_TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / 'templates' / 'embed' / 'checkout.html'


class CheckoutJsStringsTests(TestCase):
    """Every `T("...")` in the checkout script has to be in `CHECKOUT_JS_STRINGS`, or it is not translated.

    `T()` falls back to the key, so a string left off that tuple renders the English to a Spanish customer and
    nothing anywhere fails. That is exactly how "plus drinks" shipped in the middle of "Pagar $300.00 MXN ·
    1 boleto". TranslationTests cannot catch it: it scans `tr()` and `{% t %}`, and this list is neither.
    """

    def test_every_js_string_is_bootstrapped_and_translated(self):
        import re

        from api.embed_views import CHECKOUT_JS_STRINGS
        from sales.i18n import normalize, tr

        used = set(re.findall(r'\bT\("((?:[^"\\]|\\.)*)"', CHECKOUT_TEMPLATE.read_text()))
        # T(d.recentWindow) passes a value through, so the window labels are used without appearing literally.
        self.assertGreater(len(used), 20, 'the scan must actually be finding strings')

        missing = sorted(used - set(CHECKOUT_JS_STRINGS))
        self.assertEqual(missing, [], f'not bootstrapped, so these render in English: {missing}')

        no_spanish = sorted(text for text in CHECKOUT_JS_STRINGS if tr('es', text) == text and text != tr('en', text))
        self.assertEqual(no_spanish, [], f'bootstrapped but untranslated: {no_spanish}')
        self.assertEqual(normalize('es'), 'es')


class DrinksAreNotSeatsTests(ApiTestCase):
    """A round of drinks ordered ahead is not a person at the door, and every count has to agree about that."""

    def setUp(self):
        self.mic = Event.objects.create(name='Open Mic', slug='mic-drinks', status=Event.ACTIVE, venue=self.venue,
                                        currency='mxn', date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        self.seat = TicketType.objects.create(event=self.mic, name='Free reserved seat', price_cents=0, capacity=60)
        self.drinks = TicketType.objects.create(event=self.mic, name='2 drinks', price_cents=10000, is_addon=True)

    def test_a_drink_never_gets_a_ticket(self):
        """One seat and three rounds used to produce four QR codes, four lines in the confirmation email and
        three things at the door that cannot be checked in."""
        from sales.models import Order, OrderItem
        from sales.services import complete_order

        order = Order.objects.create(event=self.mic, event_name=self.mic.name, customer_email='a@example.com',
                                     currency='mxn', total_amount_cents=30000)
        OrderItem.objects.create(order=order, ticket_type=self.seat, name='seat', quantity=1, unit_price_cents=0,
                                 is_addon=False)
        OrderItem.objects.create(order=order, ticket_type=self.drinks, name='2 drinks', quantity=3,
                                 unit_price_cents=10000, is_addon=True)
        complete_order(order)
        self.assertEqual(order.tickets.count(), 1)
        self.assertEqual(order.tickets.first().ticket_type_name, 'seat')

    def test_checkout_records_which_lines_are_add_ons(self):
        """`is_addon` is snapshotted rather than read back off the ticket type, which is nullable. Without it a
        deleted drinks type turns every old drink into a seat."""
        from sales.services import create_order, price_cart

        cart = price_cart(self.mic, {self.seat.id: 1, self.drinks.id: 2}, contact=None)
        order = create_order(self.mic, cart, name='A', email='a@example.com', phone='', contact=None, locale='en')
        by_name = {item.name: item for item in order.items.all()}
        self.assertFalse(by_name['Free reserved seat'].is_addon)
        self.assertTrue(by_name['2 drinks'].is_addon)

    def test_the_button_counts_seats_and_the_drinks_are_named_separately(self):
        page = CHECKOUT_TEMPLATE.read_text()
        self.assertNotIn('sub = n === 1 ? T("1 ticket")', page, 'the basket total is not a ticket count')
        self.assertIn('var seats = seatCount();', page)
        self.assertIn('T("plus drinks")', page)


class OpenMicSetupTests(TestCase):
    """`setup_open_mics` is re-runnable, and the thing that breaks re-runnability is renaming a ticket type."""

    def test_renaming_the_drinks_row_re_prices_it_instead_of_doubling_it(self):
        """Matching on the current name alone would leave 31 nights each offering the old bundle AND the new
        single drink, side by side, at two different prices."""
        from catalog.management.commands.setup_open_mics import DRINKS

        self.assertIn('2 drinks, ordered in advance', DRINKS['legacy_names'])
        self.assertIn('2 bebidas, pedidas por adelantado', DRINKS['legacy_names'])
        self.assertNotIn(DRINKS['name'], DRINKS['legacy_names'])

    def test_a_drink_is_priced_one_at_a_time(self):
        """The stepper beside the row counts whatever the row is. Sold as a bundle it showed "2 drinks" next to
        a 4, which is eight drinks, and nothing on the page said so."""
        from catalog.management.commands.setup_open_mics import DRINKS

        for name in (DRINKS['name'], DRINKS['name_es']):
            self.assertNotRegex(name, r'^\s*\d', f'{name!r} names a quantity the stepper already shows')


class ProbeOrderTests(ApiTestCase):
    """The end-to-end test books a real seat, and a test booking must never reach Meta as a sale."""

    def _order(self, email):
        return Order.objects.create(event=self.event, event_name=self.event.name, customer_email=email,
                                    currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())

    def test_a_test_booking_is_not_reported_as_a_sale(self):
        """Meta cannot be told to forget a Purchase. Left unfiltered, a run of the suite taught the algorithm
        that a robot was a customer and flattered the cost per reservation the campaigns are judged on."""
        from sales.ad_reporting import report_purchase

        with patch('crm.meta_capi.send') as send:
            report_purchase(self._order('e2e-seat-123@iguanacomedy.com'))
        send.assert_not_called()

    def test_a_real_booking_still_is(self):
        from sales.ad_reporting import report_purchase

        with patch('crm.meta_capi.send') as send:
            report_purchase(self._order('someone@example.com'))
        send.assert_called_once()
        self.assertEqual(send.call_args[0][0], 'Purchase')

    def test_the_marker_matches_what_the_test_actually_sends(self):
        """If the e2e script's address ever stops starting with the prefix, this filter silently stops working
        and nothing fails: the only symptom is a slowly inflating purchase count."""
        import pathlib

        script = (pathlib.Path(__file__).resolve().parent.parent.parent / 'tests' / 'reserve-flow.mjs').read_text()
        from sales.ad_reporting import PROBE_EMAIL_PREFIX

        self.assertIn(f'`{PROBE_EMAIL_PREFIX}', script, 'the e2e booking address must carry the probe prefix')


class RevenuePageTests(ApiTestCase):
    """The staff revenue page. Its whole job is to be true, so the tests are about what it must never say."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        # Staff AND allowed to see the money: /revenue/ deliberately asks for more than is_staff, so that the
        # bar's own account cannot read customer names and takings. See can_see_the_money.
        self.staff = get_user_model().objects.create_user('till', password='x', is_staff=True, is_superuser=True)
        self.bar = get_user_model().objects.create_user('barkeep', password='x', is_staff=True)

    def test_it_is_staff_only(self):
        """It lists customer names and what the club is taking. A logged-out request must not see it."""
        response = self.client.get('/revenue/')
        self.assertIn(response.status_code, (302, 403))
        self.assertNotIn(b'Revenue', response.content)

    def test_being_staff_is_not_enough(self):
        """The bar has a staff account with a password its staff can type on a phone in a dark room. It works
        the table board and must not open the page with customer names and takings on it."""
        self.client.force_login(self.bar)
        response = self.client.get('/revenue/')
        self.assertIn(response.status_code, (302, 403))
        self.assertNotIn(b'Where it is lost', response.content)

    def test_and_the_bar_can_still_work_its_own_board(self):
        self.client.force_login(self.bar)
        self.assertEqual(self.client.get('/tables/').status_code, 200)

    def test_it_renders_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get('/revenue/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Where it is lost', response.content)

    def test_a_pay_at_the_door_reservation_is_not_revenue_yet(self):
        """It is a real booking and worth optimising for, but the club has not been paid. Counting it as taken
        online would flatter every number on the page."""
        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='a@example.com',
                                     currency='mxn', status=Order.COMPLETED, completed_at=timezone.now(),
                                     total_amount_cents=5000, pay_at_door_cents=5000)
        self.client.force_login(self.staff)
        page = self.client.get('/revenue/').content.decode()
        self.assertIn('0.00 MXN', page, 'nothing has been taken online')
        self.assertIn('50.00 MXN', page, 'and the door is owed the 50')
        self.assertEqual(order.pay_at_door_cents, 5000)

    def test_the_funnel_never_prints_an_impossible_percentage(self):
        """The beacon that counts the first step was added after orders already existed, so for a while the top
        is narrower than the bottom. It must say so rather than print 400%."""
        Order.objects.create(event=self.event, event_name=self.event.name, customer_email='b@example.com',
                             currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())
        self.client.force_login(self.staff)
        page = self.client.get('/revenue/').content.decode()
        self.assertIn('only been counted since', page)

    def test_pesos_are_never_added_to_dollars(self):
        """The English nights sell in USD and the Spanish ones in MXN. One combined total is not a rounding
        problem, it is a wrong number, and it printed a ten dollar order as "10.00 MXN"."""
        for currency, cents in (('mxn', 30000), ('usd', 1000)):
            Order.objects.create(event=self.event, event_name=self.event.name, customer_email=f'{currency}@example.com',
                                 currency=currency, status=Order.COMPLETED, completed_at=timezone.now(),
                                 total_amount_cents=cents)
        self.client.force_login(self.staff)
        page = self.client.get('/revenue/').content.decode()
        self.assertIn('300.00 MXN', page)
        self.assertIn('10.00 USD', page)
        self.assertNotIn('310.00', page, 'the two currencies must never be summed')

    def test_the_window_cannot_be_driven_out_of_range(self):
        self.client.force_login(self.staff)
        for value in ('0', '-5', '99999', 'lots'):
            self.assertEqual(self.client.get(f'/revenue/?days={value}').status_code, 200)


class NewsletterLinkTests(ApiTestCase):
    """Each line in the weekly mail has to open the night it names."""

    def _mic(self, when, language, name):
        return Event.objects.create(name=name, slug=f'mic-{when:%Y-%m-%d}-{language}', status=Event.ACTIVE,
                                    venue=self.venue, currency='mxn', language=language, date=when,
                                    tags=['open-mic'], doors_open='20:00', show_time='21:00')

    def test_an_open_mic_link_pins_its_own_night(self):
        """The lander offers four dates and defaults to the next one, so an unpinned link sent on a Monday about
        Wednesday put the reader in front of Tuesday. They book the wrong night and find out at the door."""
        tuesday = timezone.now() + timedelta(days=1)
        wednesday = timezone.now() + timedelta(days=2)
        self._mic(tuesday, 'es', 'Noche de Open Mic')
        self._mic(wednesday, 'en', 'Open Mic Night')
        from crm.whats_on import body as weekly_body, week_events

        body = weekly_body(week_events())
        self.assertIn(f'night=es&date={timezone.localtime(tuesday).date().isoformat()}', body)
        self.assertIn(f'night=en&date={timezone.localtime(wednesday).date().isoformat()}', body)

    def test_the_click_marker_survives_the_query_it_is_added_to(self):
        """`tag` joins with & when the URL already has a query. Getting that wrong makes every link 404."""
        from crm.email_links import tag
        from crm.models import Contact

        contact = Contact.objects.create(email='reader@example.com')
        self.assertIn('?night=es&date=2026-09-22&ic=', tag('https://x/es/open-mic/?night=es&date=2026-09-22', contact))


class EmailedUnsubscribeTests(ApiTestCase):
    """An unsubscribe that arrives as an email has to work, and must not take innocent people with it."""

    def _mbox(self, messages):
        import pathlib
        import tempfile

        path = pathlib.Path(tempfile.mkdtemp()) / 'inbox'
        path.write_text('\n'.join(
            f'From someone Thu Sep 23 14:00:00 2026\nFrom: {frm}\nSubject: {subject}\n\n{body}\n'
            for frm, subject, body in messages))
        return str(path)

    def test_it_honours_a_client_that_used_the_mailto(self):
        """Apple Mail chose the mailto out of List-Unsubscribe, sent it to a mailbox nothing was reading, and
        the person stayed on the list having done everything right."""
        from django.core.management import call_command
        from crm.models import Contact

        person = Contact.objects.create(email='reader@example.com', subscribed=True)
        box = self._mbox([('Reader <reader@example.com>', 'unsubscribe', 'Apple Mail sent this email to unsubscribe.')])
        call_command('process_unsubscribe_mail', '--mailbox', box, '--apply', verbosity=0)
        person.refresh_from_db()
        self.assertFalse(person.subscribed)

    def test_mentioning_the_word_is_not_asking(self):
        """The body is read now, but a mention is not a request. Every newsletter carries the word in its own
        footer and a copy lands in this mailbox, so the line between the two has to hold."""
        from django.core.management import call_command
        from crm.models import Contact

        person = Contact.objects.create(email='innocent@example.com', subscribed=True)
        box = self._mbox([('innocent@example.com', 'Re: your show on Friday',
                           'Looks great. PS the footer says I can unsubscribe here.')])
        call_command('process_unsubscribe_mail', '--mailbox', box, '--apply', verbosity=0)
        person.refresh_from_db()
        self.assertTrue(person.subscribed, 'mentioning the word is not asking')

    def test_it_refuses_a_message_that_looks_like_it_came_from_us(self):
        from django.core.management import call_command
        from crm.models import Contact

        us = Contact.objects.create(email='hello@site.test', subscribed=True)
        box = self._mbox([('no-reply@site.test', 'unsubscribe', 'x')])
        call_command('process_unsubscribe_mail', '--mailbox', box, '--apply', verbosity=0)
        us.refresh_from_db()
        self.assertTrue(us.subscribed)

    def test_a_dry_run_changes_nothing(self):
        from django.core.management import call_command
        from crm.models import Contact

        person = Contact.objects.create(email='reader2@example.com', subscribed=True)
        box = self._mbox([('reader2@example.com', 'Unsubscribe', 'please')])
        call_command('process_unsubscribe_mail', '--mailbox', box, verbosity=0)
        person.refresh_from_db()
        self.assertTrue(person.subscribed)

    def test_the_header_offers_only_the_link_that_works_by_itself(self):
        """A mailto beside the URL lets a client pick the one that needs somebody to be reading a mailbox."""
        from crm.unsubscribe import bulk_headers

        headers = bulk_headers('reader@example.com')
        self.assertNotIn('mailto:', headers['List-Unsubscribe'])
        self.assertEqual(headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')


class MarketingSendTests(ApiTestCase):
    """`send_marketing` has to actually send. It did not, for as long as it has existed."""

    def test_it_delivers_rather_than_raising_on_the_first_recipient(self):
        """`fail_silently` belongs to the connection, not the message: passing it to a message that carries a
        connection raises TypeError on the first recipient, so the run ends having sent nothing. The weekly
        newsletter did exactly that every Monday, and the only evidence was a traceback in the journal."""
        from crm.mail import send_marketing
        from crm.models import Contact

        people = [Contact.objects.create(email=f'reader{i}@example.com', subscribed=True) for i in range(3)]
        sent, skipped = send_marketing('What is on', 'Three shows this week.', people)
        self.assertEqual((sent, skipped), (3, 0))
        self.assertEqual(len(mail.outbox), 3)

    def test_the_tolerance_lives_on_the_connection(self):
        """One refused address must not end the run, and that is the connection's job. Asserting on where the
        flag is set rather than on a mocked backend, because a mock that swallows the error would pass whether
        or not the code was right."""
        from unittest.mock import patch

        from crm.mail import send_marketing
        from crm.models import Contact

        person = Contact.objects.create(email='r@example.com', subscribed=True)
        with patch('crm.mail.get_connection', wraps=__import__('django.core.mail', fromlist=['get_connection']).get_connection) as made:
            send_marketing('What is on', 'body', [person])
        made.assert_called_once_with(fail_silently=True)


class PublicLinkTests(ApiTestCase):
    """A link a PERSON follows goes to iguanacomedy.com, not api.iguanacomedy.com.

    `api.` in an inbox reads as somebody else's domain, and it is the first thing a phishing filter looks at.
    nginx serves these paths on both hosts, so every QR already printed and every link already emailed still
    works; only what is generated from here on uses the short one.
    """

    def _order(self):
        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='a@example.com',
                                     currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())
        Ticket.objects.create(order=order, ticket_type_name='GA')
        return order

    def test_the_ticket_link_in_the_confirmation_is_on_the_site(self):
        from sales.services import send_order_confirmation

        order = self._order()
        send_order_confirmation(order)
        body = mail.outbox[-1].body
        self.assertIn(f'{SITE}/orders/{order.public_view_token}/', body)
        self.assertNotIn('api.', body)

    def test_the_door_scan_link_is_on_the_site(self):
        order = self._order()
        fan = self.sign_in('a@example.com')
        rows = self.api('get', '/api/fan/v1/tickets', fan=fan).json()
        urls = [t['checkinUrl'] for row in rows.get('tickets', rows if isinstance(rows, list) else [])
                for t in (row.get('tickets') or [row])] if rows else []
        self.assertTrue(all(u.startswith(SITE) for u in urls) or not urls, urls)

    def test_the_public_base_follows_the_live_setting(self):
        """Read at call time, not frozen at import: a setting computed once cannot be overridden in a test, and
        that is exactly how the first version of this shipped pointing at a developer's laptop."""
        from sales.links import public_base

        self.assertEqual(public_base(), SITE)

    def test_the_embed_itself_stays_on_the_api_host(self):
        """The checkout iframe is a separate origin on purpose; moving it is not part of this."""
        from django.conf import settings

        row = next(e for e in self.api('get', '/api/public/v1/events').json()['events'] if e['id'] == self.event.id)
        self.assertTrue(row['embedUrl'].startswith(settings.BACKEND_URL), row['embedUrl'])


class MediaUrlTests(ApiTestCase):
    """Posters are served from the site, not the API host."""

    def test_an_uploaded_poster_is_same_origin_with_the_page_showing_it(self):
        """It used to be absolute against BACKEND_URL, which put a DNS lookup and a TLS handshake in front of
        the largest image on every show page."""
        self.event.image_url = '/media/events/poster.jpg'
        self.event.save()
        row = next(e for e in self.api('get', '/api/public/v1/events').json()['events'] if e['id'] == self.event.id)
        self.assertEqual(row['imageUrl'], f'{SITE}/media/events/poster.jpg')

    def test_an_absolute_url_is_left_exactly_as_it_is(self):
        """Archive images point at wherever they were recovered from; rewriting their host would break them."""
        self.event.image_url = 'https://framerusercontent.com/images/abc.jpg'
        self.event.save()
        row = next(e for e in self.api('get', '/api/public/v1/events').json()['events'] if e['id'] == self.event.id)
        self.assertEqual(row['imageUrl'], 'https://framerusercontent.com/images/abc.jpg')


class TableMenuTests(ApiTestCase):
    """The bar menu, and a round ordered from a table by its QR code."""

    def setUp(self):
        from catalog.models import MenuCategory, MenuItem

        self.beer = MenuCategory.objects.create(name='Beer', name_es='Cerveza', sort_order=0)
        self.draught = MenuItem.objects.create(category=self.beer, name='Draught beer', name_es='Cerveza de barril',
                                               price_cents=5000, currency='mxn')
        self.gone = MenuItem.objects.create(category=self.beer, name='Sold out lager', price_cents=5000,
                                            currency='mxn', available=False)

    def test_the_menu_comes_back_in_the_visitor_s_language(self):
        rows = self.api('get', '/api/public/v1/menu?locale=es').json()
        self.assertEqual(rows['categories'][0]['name'], 'Cerveza')
        self.assertEqual(rows['categories'][0]['items'][0]['name'], 'Cerveza de barril')

    def test_an_item_turned_off_for_the_night_is_not_offered(self):
        """Turned off rather than deleted, so it comes back without being retyped and an old order still names
        what it was. It must not appear on the menu while it is off."""
        rows = self.api('get', '/api/public/v1/menu').json()
        names = [i['name'] for c in rows['categories'] for i in c['items']]
        self.assertIn('Draught beer', names)
        self.assertNotIn('Sold out lager', names)

    def test_an_empty_category_is_not_an_empty_heading(self):
        from catalog.models import MenuCategory

        MenuCategory.objects.create(name='Wine', sort_order=1)
        rows = self.api('get', '/api/public/v1/menu').json()
        self.assertEqual([c['name'] for c in rows['categories']], ['Beer'])

    def test_a_round_knows_which_table_it_goes_to(self):
        """That is the entire feature: the QR carries the table, so nobody has to catch a waiter's eye."""
        from sales.models import TableOrder

        res = self.api('post', '/api/public/v1/table-orders',
                       {'table': 7, 'lang': 'es', 'items': {self.draught.id: 2}, 'note': 'sin hielo'})
        self.assertEqual(res.status_code, 200)
        order = TableOrder.objects.get(pk=res.json()['id'])
        self.assertEqual(order.table_number, 7)
        self.assertEqual(order.total_cents, 10000)
        self.assertEqual(order.note, 'sin hielo')
        self.assertEqual(order.items.get().name, 'Cerveza de barril', 'snapshotted in the language they read')

    def test_a_table_that_does_not_exist_is_refused(self):
        for table in (0, 101, 'seven', None):
            res = self.api('post', '/api/public/v1/table-orders', {'table': table, 'items': {self.draught.id: 1}})
            self.assertEqual(res.status_code, 400, table)

    def test_an_empty_round_is_refused(self):
        self.assertEqual(self.api('post', '/api/public/v1/table-orders', {'table': 7, 'items': {}}).status_code, 400)

    def test_an_unavailable_item_cannot_be_ordered_by_id(self):
        """The page will not offer it, so anyone sending it is sending an id they kept from earlier."""
        res = self.api('post', '/api/public/v1/table-orders', {'table': 7, 'items': {self.gone.id: 1}})
        self.assertEqual(res.status_code, 400)

    def test_the_price_is_the_menu_s_and_never_the_browser_s(self):
        res = self.api('post', '/api/public/v1/table-orders',
                       {'table': 7, 'items': {self.draught.id: 1}, 'priceCents': 1, 'totalCents': 1})
        self.assertEqual(res.json()['totalCents'], 5000)

    def test_it_tells_the_bar(self):
        with self.settings(NOTIFY_EMAILS=['hello@iguanacomedy.com']), self.captureOnCommitCallbacks(execute=True):
            self.api('post', '/api/public/v1/table-orders', {'table': 12, 'items': {self.draught.id: 3}})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Table 12', mail.outbox[0].subject)
        self.assertIn('3 x Draught beer', mail.outbox[0].subject)

    def test_a_mail_server_having_a_bad_night_cannot_lose_the_round(self):
        from sales.models import TableOrder

        with self.settings(NOTIFY_EMAILS=['hello@iguanacomedy.com']), \
                patch('django.core.mail.EmailMessage.send', side_effect=OSError('smtp down')), \
                self.captureOnCommitCallbacks(execute=True):
            res = self.api('post', '/api/public/v1/table-orders', {'table': 3, 'items': {self.draught.id: 1}})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(TableOrder.objects.filter(table_number=3).exists())


class SoldElsewhereTests(ApiTestCase):
    """A guest promoter selling the same night is selling the same chairs."""

    def setUp(self):
        self.show = Event.objects.create(name='Guest headliner', slug='guest-headliner', status=Event.ACTIVE,
                                         venue=self.venue, currency='mxn',
                                         date=timezone.now() + timedelta(days=3))
        self.seat = TicketType.objects.create(event=self.show, name='General admission', price_cents=30000,
                                              capacity=80, sold_elsewhere=25)

    def test_the_checkout_cannot_sell_the_room_twice(self):
        """Without this our checkout offers all eighty chairs while the promoter is selling the same eighty,
        and the second person to arrive is turned away at the door having paid."""
        from api.serializers import remaining

        self.assertEqual(remaining(self.seat), 55)

    def test_it_refuses_an_order_that_would_overfill_the_room(self):
        # Squeezed to 10 left so the capacity guard is what refuses it, rather than the 20-per-order limit
        # refusing it first and the test passing for the wrong reason.
        self.seat.sold_elsewhere = 70
        self.seat.save()
        self.assertEqual(self.api('post', f'/api/checkout/{self.show.id}/quote',
                                  {'items': {self.seat.id: 11}}).status_code, 400)
        self.assertEqual(self.api('post', f'/api/checkout/{self.show.id}/quote',
                                  {'items': {self.seat.id: 10}}).status_code, 200)

    def test_the_page_counts_them_as_taken(self):
        """Leaving them out told a visitor the night was emptier than it is, which is the opposite of what the
        demand line exists to do."""
        from sales.demand import demand, demand_for

        d = demand(self.show)
        self.assertEqual((d['taken'], d['left']), (25, 55))
        self.assertEqual(demand_for([self.show])[self.show.id], d, 'and both code paths still agree')

    def test_zero_changes_nothing_for_every_other_show(self):
        from api.serializers import remaining
        from sales.demand import demand

        plain = TicketType.objects.create(event=self.show, name='Second tier', price_cents=10000, capacity=10)
        self.assertEqual(remaining(plain), 10)
        self.assertEqual(demand(self.show)['capacity'], 90)


class DrinksMovedOutOfCheckoutTests(ApiTestCase):
    """The upsell moved from before the reserve button to after the seat is held."""

    def test_an_existing_drinks_row_is_switched_off_not_deleted(self):
        """Deleting it would take its name off orders that already carry it. Off means the checkout stops
        offering it while an old order still says what was bought."""
        from catalog.management.commands.setup_open_mics import DRINKS, SELL_DRINKS_AT_CHECKOUT

        self.assertFalse(SELL_DRINKS_AT_CHECKOUT)
        mic = Event.objects.create(name='Open Mic Night in Spanish', slug='mic-drinks-off', status=Event.ACTIVE,
                                   venue=self.venue, currency='mxn', language='es',
                                   date=timezone.now() + timedelta(days=2), tags=['open-mic', 'open-mic-es'])
        drinks = TicketType.objects.create(event=mic, name=DRINKS['name'], price_cents=5000, is_addon=True)
        from django.core.management import call_command
        call_command('setup_open_mics', verbosity=0)
        drinks.refresh_from_db()
        self.assertFalse(drinks.active)
        self.assertTrue(TicketType.objects.filter(pk=drinks.pk).exists(), 'off, not gone')

    def test_the_order_page_offers_the_menu_once_the_seat_is_held(self):
        mic = Event.objects.create(name='Open Mic', slug='mic-menu', status=Event.ACTIVE, venue=self.venue,
                                   currency='mxn', date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        order = Order.objects.create(event=mic, event_name=mic.name, customer_email='a@example.com',
                                     currency='mxn', status=Order.COMPLETED, completed_at=timezone.now(),
                                     locale='es')
        page = self.client.get(f'/orders/{order.public_view_token}/').content.decode()
        self.assertIn('¿Con sed?', page)
        # Unprefixed, the same link the table codes carry, so it works in whichever language they read it.
        self.assertIn(f'{SITE}/menu/', page)

    def test_a_ticketed_show_is_not_sent_to_the_open_mic_bar_pitch(self):
        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='b@example.com',
                                     currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())
        page = self.client.get(f'/orders/{order.public_view_token}/').content.decode()
        self.assertNotIn('/menu/', page)


class WalletTests(ApiTestCase):
    """Apple Pay and Google Pay, which are the whole point of a phone-first checkout with a paid upsell."""

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_the_api_stops_claiming_a_wallet_is_impossible(self):
        """These flags were hardcoded False while the account, the domain and the checkout were all ready for a
        wallet. A site reading them had no way to know better."""
        config = self.api('get', '/api/fan/v1/config').json()
        self.assertEqual(config['wallets'], {'apple': True, 'google': True})

    def test_and_says_no_when_there_are_no_keys(self):
        self.assertEqual(self.api('get', '/api/fan/v1/config').json()['wallets'], {'apple': False, 'google': False})

    def test_the_wallet_and_the_card_button_share_one_checkout(self):
        """The two ways of paying differ only in how the payment method is collected. If they ever grow separate
        order-creation paths, one of them drifts and the drift is discovered by a customer, not by us."""
        page = CHECKOUT_TEMPLATE.read_text()
        self.assertEqual(page.count('/api/checkout/" + ev.id + "/start'), 1,
                         'the order is created in exactly one place')
        self.assertEqual(page.count('stripe.confirmPayment('), 1, 'and confirmed in exactly one place')
        self.assertIn('express.on("confirm"', page)
        self.assertIn('finish(checkout())', page)

    def test_the_wallet_never_takes_a_card_the_customer_cannot_be_reached_at(self):
        """`emailRequired` is what lets a wallet booking fill in a blank email; without it the sheet completes and
        we have a paid order with no way to send the tickets."""
        page = CHECKOUT_TEMPLATE.read_text()
        self.assertIn('emailRequired: true', page)
        self.assertIn('validDetails()', page)


class InviteAFriendTests(ApiTestCase):
    """After reserving, the one moment where asking somebody to bring a friend costs nothing.

    They have already decided, the seat they would be recommending is free, and they are about to tell
    somebody anyway. The link has to land on the night they just booked, not on a generic page.
    """

    def setUp(self):
        from catalog.models import Event, TicketType

        self.mic = Event.objects.create(name='Open Mic Night in Spanish', slug='mic-share', status=Event.ACTIVE,
                                        venue=self.venue, currency='mxn', language='es',
                                        date=timezone.now() + timedelta(days=2), tags=['open-mic'])
        self.seat = TicketType.objects.create(event=self.mic, name='Free reserved seat', price_cents=0, capacity=60)

    def reserve(self, lang='es'):
        with self.captureOnCommitCallbacks(execute=True):
            body = self.client.post(f'/api/checkout/{self.mic.id}/start', content_type='application/json',
                                    data=json.dumps({'items': {self.seat.id: 1}, 'name': 'Ada',
                                                     'email': 'fan@example.com', 'lang': lang})).json()
        from sales.models import Order

        return Order.objects.get(pk=body['orderId'])

    def test_the_link_points_at_the_night_they_just_booked(self):
        from sales.sharing import share_url

        url = share_url(self.reserve())
        self.assertIn('/es/open-mic/', url)
        self.assertIn('night=es', url, 'a friend must land on this show, not a choice of two')
        self.assertIn(f'date={self.mic.date.astimezone().date().isoformat()}', url)
        self.assertIn('ref=share', url, 'shared traffic has to be tellable from bought traffic')

    def test_the_order_page_offers_whatsapp_and_a_copyable_link(self):
        order = self.reserve()
        page = self.client.get(f'/orders/{order.public_view_token}/').content.decode()
        self.assertIn('¿Vienes con alguien?', page)
        self.assertIn('https://wa.me/?text=', page)
        # The message rides in the href, so it only appears percent-encoded.
        self.assertIn('Voy%20al%20open%20mic%20de%20Iguana%20Comedy', page)
        self.assertIn('id="copy-invite"', page)
        # The script has to sit in a block the base template actually renders: it was first written into
        # {% block scripts_extra %}, which the base does not define, so it silently rendered nothing at all.
        self.assertIn('navigator.share', page)
        # And the ask comes after the tickets. Somebody who just booked wants their QR code first.
        self.assertGreater(page.index('¿Vienes con alguien?'), page.index('data-qr'))

    def test_the_confirmation_email_carries_it_too(self):
        self.reserve()
        body = mail.outbox[0].body
        self.assertIn('¿Vienes con alguien?', body)
        self.assertIn('/es/open-mic/?night=es', body)

    def test_an_english_booker_shares_an_english_page(self):
        from sales.sharing import share_url

        url = share_url(self.reserve(lang='en'))
        self.assertIn('/en/open-mic/', url, 'the path follows the sharer, who writes the message')
        self.assertIn('night=es', url, 'the night follows the show, which is in Spanish')

    def test_a_ticketed_show_shares_its_own_page_never_the_open_mic(self):
        """Somebody who has just paid for two tickets is at least as willing to tell people as somebody who
        reserved a free seat. What changes is where the friend should land: the show being recommended, where
        they can buy it, and not the open mic lander, which sells a different night entirely."""
        from sales.sharing import share_message, share_url
        from sales.models import Order

        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='a@example.com',
                                     currency='usd', status=Order.COMPLETED, locale='en')
        link = share_url(order)
        self.assertIn(f'/en/events/{self.event.slug}/', link)
        self.assertIn('ref=share', link)
        # The lander's own query, which is what would mean it had been sent to the open mic instead.
        self.assertNotIn('night=', link)
        self.assertIn(self.event.name, share_message(order))

    def test_a_show_happening_tonight_is_still_shared(self):
        """The stored date can sit earlier in the day than the show itself, and comparing it to the clock made
        every night 'past' from midnight, which removed the share block on the one day people talk about it."""
        from sales.sharing import share_url
        from sales.models import Order

        self.event.date = timezone.localtime(timezone.now()).replace(hour=0, minute=1)
        self.event.save(update_fields=['date'])
        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='a@example.com',
                                     currency='usd', status=Order.COMPLETED, locale='en')
        self.assertNotEqual(share_url(order), '')

    def test_a_show_that_has_already_happened_is_not_shared(self):
        from sales.sharing import share_url
        from sales.models import Order

        self.event.date = timezone.now() - timedelta(days=1)
        self.event.save(update_fields=['date'])
        order = Order.objects.create(event=self.event, event_name=self.event.name, customer_email='a@example.com',
                                     currency='usd', status=Order.COMPLETED)
        self.assertEqual(share_url(order), '', 'a link to a finished show wastes the one ask we get')


class CheckoutReserveTests(ApiTestCase):
    """The page holds the checkout's height open before the iframe exists, and only the backend knows how much.

    A card form is roughly three times the height of a name-and-email one, so getting this wrong is the jump
    itself: the whole page moves under the reader a second after it loads, at the moment they are reaching for
    the button. `collectsPayment` is the one fact the site cannot work out for itself.
    """

    def test_no_stripe_keys_means_no_card_form(self):
        data = self.api('get', f'/api/public/v1/events/{self.event.id}').json()['event']
        self.assertFalse(data['collectsPayment'])
        self.assertEqual(data['ticketTypeCount'], 2)

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_paid_event_collects_payment(self):
        data = self.api('get', f'/api/public/v1/events/{self.event.id}').json()['event']
        self.assertTrue(data['collectsPayment'])

    @override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')
    def test_pay_at_door_draws_no_card_form(self):
        self.event.ticket_types.all().update(pay_at_door=True)
        data = self.api('get', f'/api/public/v1/events/{self.event.id}').json()['event']
        self.assertFalse(data['collectsPayment'])

    def test_the_card_form_is_never_pinned_to_a_height(self):
        """Stripe sizes its own element. Anything we pin it to is a guess, and a guess that overshoots shows
        up as a white hole above the Pay button, which looks broken in a way a brief movement does not."""
        html = self.client.get(f'/embed/event/{self.event.id}?embedded=1&lang=en').content.decode()
        self.assertIn('<div id="payment-element" hidden>', html)
        self.assertNotIn('#payment-element.reserve', html)

    def test_the_checkout_says_when_it_has_settled(self):
        """That is the signal the page waits for before it stops holding space open."""
        html = self.client.get(f'/embed/event/{self.event.id}?embedded=1&lang=en').content.decode()
        self.assertIn('settled: settled', html)
        self.assertIn('card.on("ready", settleWhenStable)', html)


class AfterShowTests(ApiTestCase):
    """The morning-after note: thank them, ask them to tell somebody, ask what could have been better.

    The things worth protecting are the ones that would embarrass us: sending it twice, sending it to somebody
    who has unsubscribed, sending English to a Spanish booking, or claiming they came when nobody is scanned at
    the door and we cannot know.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.last_night = Event.objects.create(name='Open Mic Night in Spanish', slug='mic-last-night',
                                              status=Event.ACTIVE, venue=cls.venue, language='es',
                                              date=timezone.now() - timedelta(days=1), tags=['open-mic'])
        TicketType.objects.create(event=cls.last_night, name='Free reserved seat', price_cents=0, capacity=60)
        cls.soon = Event.objects.create(name='Open Mic Night in Spanish', slug='mic-next', status=Event.ACTIVE,
                                        venue=cls.venue, language='es', tags=['open-mic'],
                                        date=timezone.now() + timedelta(days=6))

    def booking(self, email, name='Ana Lopez', locale='es', event=None):
        contact = Contact.objects.create(email=email, locale=locale)
        return Order.objects.create(event=event or self.last_night, event_name=(event or self.last_night).name,
                                    customer_email=email, customer_name=name, contact=contact, locale=locale,
                                    currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())

    def run_command(self, **kwargs):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('send_after_show', stdout=out, **kwargs)
        return out.getvalue()

    def test_it_sends_one_note_per_booking_in_the_booking_language(self):
        self.booking('ana@example.com')
        mail.outbox = []
        self.run_command(send=True)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, '¿Qué tal estuvo anoche?')
        self.assertIn('Tenías lugar para', message.body)
        self.assertIn('/es/open-mic/', message.body)
        self.assertIn('ref=after-show', message.body)

    def test_it_never_claims_they_turned_up(self):
        """Nobody is scanned at the door, so attendance is not a fact we hold."""
        self.booking('ana@example.com', locale='en')
        mail.outbox = []
        self.run_command(send=True)
        body = mail.outbox[0].body.lower()
        self.assertIn('we hope you made it', body)
        self.assertNotIn('thanks for coming', body)

    def test_it_asks_for_a_reply_to_an_address_a_person_reads(self):
        self.booking('ana@example.com')
        mail.outbox = []
        with override_settings(MARKETING_REPLY_TO='hello@iguanacomedy.com'):
            self.run_command(send=True)
        self.assertEqual(mail.outbox[0].reply_to, ['hello@iguanacomedy.com'])
        self.assertIn('responde a este correo', mail.outbox[0].body)

    def test_a_second_run_sends_nothing(self):
        self.booking('ana@example.com')
        mail.outbox = []
        self.run_command(send=True)
        self.run_command(send=True)
        self.assertEqual(len(mail.outbox), 1)

    def test_an_unsubscribed_guest_is_skipped_but_still_stamped(self):
        order = self.booking('ana@example.com')
        order.contact.subscribed = False
        order.contact.save(update_fields=['subscribed'])
        mail.outbox = []
        self.run_command(send=True)
        self.assertEqual(mail.outbox, [])
        order.refresh_from_db()
        self.assertIsNotNone(order.follow_up_sent_at, 'otherwise every run picks them up again forever')

    def test_two_bookings_by_one_person_get_one_note(self):
        first = self.booking('ana@example.com')
        second = Order.objects.create(event=self.last_night, event_name=self.last_night.name, locale='es',
                                      customer_email='ana@example.com', customer_name='Ana Lopez',
                                      contact=first.contact, currency='mxn', status=Order.COMPLETED,
                                      completed_at=timezone.now())
        mail.outbox = []
        self.run_command(send=True)
        self.assertEqual(len(mail.outbox), 1)
        second.refresh_from_db()
        self.assertIsNotNone(second.follow_up_sent_at)

    def test_tonights_show_is_not_followed_up_yet(self):
        tonight = Event.objects.create(name='Tonight', slug='tonight', status=Event.ACTIVE, venue=self.venue,
                                       date=timezone.now())
        self.booking('ana@example.com', event=tonight)
        mail.outbox = []
        self.run_command(send=True)
        self.assertEqual(mail.outbox, [])

    def test_a_dry_run_delivers_nothing_and_shows_the_note(self):
        self.booking('ana@example.com')
        mail.outbox = []
        output = self.run_command()
        self.assertEqual(mail.outbox, [])
        self.assertIn('Dry run', output)
        self.assertIn('¿Qué tal estuvo anoche?', output)


class NewsletterLanguageTests(ApiTestCase):
    """Which language the weekly mail leads with, and what the subject line says.

    The body carries both languages, so nobody is ever locked out of the content. What the locale decides is
    the order and the subject, and the subject is the only part of a bilingual email that cannot carry both.
    595 of 666 mailable contacts came from the Kintana import and have never told us anything, and a blank
    locale used to resolve to English by accident, through `normalize('')`, rather than by any decision.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.event.tags = ['open-mic', 'open-mic-es']
        cls.event.language = 'es'
        cls.event.date = timezone.now() + timedelta(days=2)
        cls.event.save()

    def week(self):
        from crm.whats_on import week_events

        return list(week_events())

    def test_a_spanish_reader_gets_spanish_first(self):
        from crm.whats_on import body

        contact = Contact.objects.create(email='es@example.com', locale='es')
        text = body(self.week(), contact)
        self.assertLess(text.index('Hola'), text.index('Hi there'))

    def test_an_english_reader_gets_english_first(self):
        from crm.whats_on import body

        contact = Contact.objects.create(email='en@example.com', locale='en')
        text = body(self.week(), contact)
        self.assertLess(text.index('Hi there'), text.index('Hola'))

    def test_a_reader_we_know_nothing_about_gets_spanish_first(self):
        """The club is in Playa del Carmen and 31 of 47 completed orders were made in Spanish."""
        from crm.whats_on import body

        contact = Contact.objects.create(email='unknown@example.com', locale='')
        text = body(self.week(), contact)
        self.assertLess(text.index('Hola'), text.index('Hi there'))

    def test_both_languages_are_always_in_the_body(self):
        from crm.whats_on import body

        for locale in ('es', 'en', ''):
            text = body(self.week(), Contact.objects.create(email=f'{locale or "x"}@example.com', locale=locale))
            self.assertIn('Hola', text)
            self.assertIn('Hi there', text)

    def test_the_subject_follows_the_same_rule(self):
        from io import StringIO

        from django.core.management import call_command

        Contact.objects.create(email='unknown2@example.com', locale='', subscribed=True)
        out = StringIO()
        call_command('send_whats_on', stdout=out)
        self.assertIn('Esta semana en Iguana Comedy', out.getvalue())


class ReservationsBoardTests(ApiTestCase):
    """The board that answers "how many have we got for Tuesday", and doubles as the door list."""

    def staff(self, name, **extra):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(name, password='x', is_staff=True, **extra)
        self.client.force_login(user)
        return user

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.event.date = timezone.now() + timedelta(days=3)
        cls.event.save(update_fields=['date'])
        cls.order = Order.objects.create(event=cls.event, event_name=cls.event.name, customer_name='Ana Lopez',
                                         customer_email='ana@example.com', currency='usd', locale='en',
                                         status=Order.COMPLETED, completed_at=timezone.now())
        Ticket.objects.create(order=cls.order, ticket_type_name='GA')
        Ticket.objects.create(order=cls.order, ticket_type_name='GA')

    def test_it_is_staff_only(self):
        res = self.client.get('/reservations/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login/', res['Location'])

    def test_it_counts_the_seats_and_names_the_guests(self):
        self.staff('door')
        page = self.client.get('/reservations/').content.decode()
        self.assertIn('Ana Lopez', page)
        self.assertIn('2 seats booked', page)

    def test_plain_staff_do_not_get_the_mailing_list(self):
        """The door needs a name to check somebody in. It does not need 600 email addresses."""
        self.staff('door2')
        page = self.client.get('/reservations/').content.decode()
        self.assertIn('Ana Lopez', page)
        self.assertNotIn('ana@example.com', page)

    def test_an_owner_sees_the_email(self):
        self.staff('boss', is_superuser=True)
        page = self.client.get('/reservations/').content.decode()
        self.assertIn('ana@example.com', page)

    def test_a_cancelled_order_is_not_counted(self):
        self.staff('door3')
        self.order.status = Order.CANCELLED
        self.order.save(update_fields=['status'])
        page = self.client.get('/reservations/').content.decode()
        self.assertNotIn('Ana Lopez', page)
        self.assertIn('Nobody yet', page)

    def test_it_reads_in_spanish_when_the_phone_does(self):
        self.staff('door4')
        page = self.client.get('/reservations/', HTTP_ACCEPT_LANGUAGE='es-MX,es;q=0.9').content.decode()
        self.assertIn('Reservaciones', page)
        self.assertIn('Quién viene', page)


class StatsPageTests(ApiTestCase):
    """The page that answers "what does a reservation cost us right now", free against paid.

    Its whole value is that the two halves come from different places and it never mixes them up: seats are
    ours, counted live; spend is Meta's, read from a snapshot a cron wrote. Meta's own purchase count is shown
    beside ours and never divided by, because it has run both above and below the orders we actually hold.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from crm.models import AdSpend

        today = timezone.localdate()
        AdSpend.objects.create(day=today, campaign_id='1', campaign_name='Open mic Spanish · reservations',
                               kind=AdSpend.FREE, spend_cents=10000, reported_purchases=9)
        AdSpend.objects.create(day=today, campaign_id='2', campaign_name='Privilegio · Fredy El Regio · boletos',
                               kind=AdSpend.PAID, spend_cents=20000, reported_purchases=4)
        free = Order.objects.create(event=cls.event, event_name=cls.event.name, customer_email='free@example.com',
                                    currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())
        Ticket.objects.create(order=free, ticket_type_name='Free reserved seat')
        Ticket.objects.create(order=free, ticket_type_name='Free reserved seat')
        paid = Order.objects.create(event=cls.event, event_name=cls.event.name, customer_email='paid@example.com',
                                    currency='mxn', status=Order.COMPLETED, completed_at=timezone.now(),
                                    total_amount_cents=60000)
        Ticket.objects.create(order=paid, ticket_type_name='General')

    def as_owner(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user('owner', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(user)
        return user

    def test_plain_staff_cannot_see_the_money(self):
        from django.contrib.auth import get_user_model

        self.client.force_login(get_user_model().objects.create_user('barkeep2', password='x', is_staff=True))
        self.assertEqual(self.client.get('/stats/').status_code, 302)

    def test_cost_per_seat_divides_spend_by_OUR_seats(self):
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('$50.00', page)   # 100.00 of free spend over our 2 seats
        self.assertIn('$200.00', page)  # 200.00 of paid spend over our 1 seat

    def test_metas_purchase_count_is_shown_but_never_divided_by(self):
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('13 purchases', page)   # Meta says 9 + 4
        self.assertIn('2 bookings', page)     # we hold 2
        self.assertNotIn('$23.07', page)      # 300.00 over Meta's 13, which nothing should ever compute

    def test_a_probe_booking_does_not_flatter_the_numbers(self):
        probe = Order.objects.create(event=self.event, event_name=self.event.name, currency='mxn',
                                     customer_email='e2e-probe@example.com', status=Order.COMPLETED,
                                     completed_at=timezone.now())
        Ticket.objects.create(order=probe, ticket_type_name='Free reserved seat')
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('$50.00', page, 'the probe seat would have made it $33.33')

    def test_it_says_when_the_spend_figures_went_stale(self):
        from crm.models import AdSpend

        self.as_owner()
        AdSpend.objects.update(fetched_at=timezone.now() - timedelta(hours=3))
        page = self.client.get('/stats/').content.decode()
        self.assertIn('not fresh', page)

    def test_a_campaign_is_classified_by_what_it_sells(self):
        from crm.ad_spend import classify
        from crm.models import AdSpend

        self.assertEqual(classify('Open mic English · reservations'), AdSpend.FREE)
        self.assertEqual(classify('Open mic Spanish · local reach'), AdSpend.FREE)
        self.assertEqual(classify('Privilegio · Fredy El Regio · boletos'), AdSpend.PAID)


class StatsAtAGlanceTests(ApiTestCase):
    """The parts of /stats/ that are not about money: how full each night is, and the funnel into it."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from crm.models import TrackedEvent

        cls.event.date = timezone.now() + timedelta(days=2)
        cls.event.save(update_fields=['date'])
        order = Order.objects.create(event=cls.event, event_name=cls.event.name, customer_email='a@example.com',
                                     currency='mxn', status=Order.COMPLETED, completed_at=timezone.now())
        OrderItem.objects.create(order=order, ticket_type=cls.ga, name='GA', quantity=1, unit_price_cents=1000)
        Ticket.objects.create(order=order, ticket_type_name='GA')
        for _ in range(9):
            TrackedEvent.objects.create(kind='pageview')
        for _ in range(3):
            TrackedEvent.objects.create(kind='checkout', name='checkout_engaged')

    def as_owner(self):
        from django.contrib.auth import get_user_model

        self.client.force_login(get_user_model().objects.create_user('owner2', password='x', is_staff=True,
                                                                     is_superuser=True))

    def test_each_night_shows_taken_against_the_room(self):
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('The room, night by night', page)
        self.assertIn('/3', page, 'the GA capacity of the fixture event')
        self.assertIn('2 left', page)

    def test_the_funnel_counts_visits_then_form_then_bookings(self):
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('>9<', page)   # visits
        self.assertIn('>3<', page)   # started booking
        self.assertIn('>1<', page)   # booked

    def test_money_from_two_currencies_is_never_added_up(self):
        """A dollar night and a peso night in one window must not become one number."""
        usd = Event.objects.create(name='Dollar night', slug='dollar-night', status=Event.ACTIVE, venue=self.venue,
                                   currency='usd', date=timezone.now() + timedelta(days=4))
        for event, currency, cents in ((self.event, 'mxn', 60000), (usd, 'usd', 2500)):
            paid = Order.objects.create(event=event, event_name=event.name, customer_email=f'{currency}@example.com',
                                        currency=currency, status=Order.COMPLETED, completed_at=timezone.now(),
                                        total_amount_cents=cents)
            Ticket.objects.create(order=paid, ticket_type_name='GA')
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('600.00 MXN', page)
        self.assertIn('25.00 USD', page)
        self.assertNotIn('625.00', page, 'adding pesos to dollars is a wrong number, not a rounding error')


class TableTabTests(ApiTestCase):
    """What a table owes for the night, which is not the same number as what is waiting to be carried over.

    They pay at the end, so a round already delivered is still money sitting on that table. The board only ever
    showed open orders, so the moment the bar pressed Delivered the amount vanished from the only screen
    anybody looks at.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from sales.models import TableOrder, TableOrderItem

        self.client.force_login(get_user_model().objects.create_user('bar3', password='x', is_staff=True))
        self.first = TableOrder.objects.create(table_number=7, currency='mxn', total_cents=18000)
        TableOrderItem.objects.create(order=self.first, name='Margarita', quantity=2, unit_price_cents=9000)

    def board(self):
        return self.client.get('/tables/').content.decode()

    def test_an_open_round_shows_both_what_is_waiting_and_what_is_owed(self):
        page = self.board()
        self.assertIn('180 MXN', page)
        self.assertIn('Due', page)

    def test_a_delivered_round_still_shows_as_owed(self):
        from sales.models import TableOrder

        self.client.post('/tables/7/close/')
        page = self.board()
        self.assertIn('Nothing waiting', page)
        self.assertIn('180 MXN', page, 'delivered is not paid')
        self.assertEqual(TableOrder.objects.get(pk=self.first.pk).status, TableOrder.DELIVERED)

    def test_a_second_round_adds_to_the_tab(self):
        from sales.models import TableOrder

        self.client.post('/tables/7/close/')
        TableOrder.objects.create(table_number=7, currency='mxn', total_cents=9000)
        page = self.board()
        self.assertIn('270 MXN', page)
        self.assertIn('2 rounds', page)

    def test_a_cancelled_round_is_not_owed(self):
        from sales.models import TableOrder

        self.first.status = TableOrder.CANCELLED
        self.first.save(update_fields=['status'])
        self.assertNotIn('180 MXN', self.board())

    def test_a_tab_that_crosses_midnight_is_one_tab(self):
        """A show starting at nine runs past midnight, and the people are still sitting there at 00:05."""
        from api.tables_views import service_start

        small_hours = timezone.now().astimezone(CANCUN_TZ).replace(hour=0, minute=5)
        self.assertEqual(service_start(small_hours).date(), (small_hours - timedelta(days=1)).date())
        evening = timezone.now().astimezone(CANCUN_TZ).replace(hour=21, minute=0)
        self.assertEqual(service_start(evening).date(), evening.date())


class TableSettleTests(ApiTestCase):
    """Paying closes the table out, and a mis-tap has to be recoverable.

    Marking a table paid that has not paid is money walking out of the door, and this is a tap on a phone in a
    dark room by somebody holding a tray. So it toggles rather than commits.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from sales.models import TableOrder

        self.client.force_login(get_user_model().objects.create_user('bar4', password='x', is_staff=True))
        self.round_one = TableOrder.objects.create(table_number=9, currency='mxn', total_cents=18000)

    def board(self):
        return self.client.get('/tables/').content.decode()

    def test_marking_it_paid_settles_every_round_on_the_table(self):
        from sales.models import TableOrder

        TableOrder.objects.create(table_number=9, currency='mxn', total_cents=9000,
                                  status=TableOrder.DELIVERED, delivered_at=timezone.now())
        self.client.post('/tables/9/settle/')
        self.assertEqual(TableOrder.objects.filter(table_number=9, status=TableOrder.PAID).count(), 2)
        page = self.board()
        self.assertIn('Paid', page)
        self.assertIn('Undo', page)

    def test_an_open_round_is_also_recorded_as_delivered(self):
        """If they are paying for it, it reached the table."""
        from sales.models import TableOrder

        self.client.post('/tables/9/settle/')
        settled = TableOrder.objects.get(pk=self.round_one.pk)
        self.assertEqual(settled.status, TableOrder.PAID)
        self.assertIsNotNone(settled.delivered_at)
        self.assertIsNotNone(settled.paid_at)

    def test_undo_puts_it_back(self):
        from sales.models import TableOrder

        self.client.post('/tables/9/settle/')
        self.client.post('/tables/9/settle/', {'undo': '1'})
        back = TableOrder.objects.get(pk=self.round_one.pk)
        self.assertEqual(back.status, TableOrder.DELIVERED)
        self.assertIsNone(back.paid_at)
        self.assertIn('Mark paid', self.board())

    def test_a_round_ordered_after_paying_reopens_the_tab(self):
        """They settle, then order one more. The table owes again and must not read as settled."""
        from sales.models import TableOrder

        self.client.post('/tables/9/settle/')
        TableOrder.objects.create(table_number=9, currency='mxn', total_cents=5000)
        page = self.board()
        self.assertIn('Mark paid', page)
        self.assertIn('230 MXN', page)

    def test_a_settled_table_is_not_counted_as_waiting(self):
        self.client.post('/tables/9/settle/')
        self.assertIn('Nothing waiting', self.board())

    def test_only_staff_can_settle(self):
        self.client.logout()
        res = self.client.post('/tables/9/settle/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login/', res['Location'])


class BarHistoryTests(ApiTestCase):
    """What the bar sold, per show, kept rather than left as a pile of timestamps."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tonight = Event.objects.create(name='Fredy El Regio', slug='fredy-night', status=Event.ACTIVE,
                                           venue=cls.venue, date=timezone.now().replace(hour=21, minute=0),
                                           show_time='21:00')

    def staff(self, name, **extra):
        from django.contrib.auth import get_user_model

        self.client.force_login(get_user_model().objects.create_user(name, password='x', is_staff=True, **extra))

    def test_a_round_is_stamped_with_the_show_it_was_poured_on(self):
        from sales.models import TableOrder

        res = self.client.post('/api/public/v1/table-orders',
                               data=json.dumps({'table': 5, 'items': {}, 'lang': 'en'}),
                               content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {KEY}')
        self.assertEqual(res.status_code, 400, 'an empty basket is still refused')
        order = TableOrder.objects.create(table_number=5, currency='mxn', total_cents=9000,
                                          event=self.tonight)
        self.assertEqual(order.event, self.tonight)

    def test_the_board_names_tonights_show(self):
        self.staff('bar5')
        page = self.client.get('/tables/').content.decode()
        self.assertIn('Fredy El Regio', page)

    def test_the_board_totals_the_night(self):
        from sales.models import TableOrder

        TableOrder.objects.create(table_number=5, currency='mxn', total_cents=9000, event=self.tonight,
                                  status=TableOrder.PAID, paid_at=timezone.now())
        TableOrder.objects.create(table_number=6, currency='mxn', total_cents=18000, event=self.tonight)
        self.staff('bar6')
        page = self.client.get('/tables/').content.decode()
        self.assertIn('2 rounds tonight', page)
        self.assertIn('90 MXN', page)     # taken
        self.assertIn('180 MXN', page)    # still owed

    def test_stats_keeps_the_history_per_show(self):
        from sales.models import TableOrder, TableOrderItem

        order = TableOrder.objects.create(table_number=5, currency='mxn', total_cents=9000, event=self.tonight,
                                          status=TableOrder.PAID, paid_at=timezone.now())
        TableOrderItem.objects.create(order=order, name='Margarita', quantity=3, unit_price_cents=3000)
        self.staff('boss2', is_superuser=True)
        page = self.client.get('/stats/').content.decode()
        self.assertIn('The bar, night by night', page)
        self.assertIn('Fredy El Regio', page)
        self.assertIn('1 round · 3 drinks', page)
        self.assertIn('90.00 MXN', page)


class ServiceShowTests(ApiTestCase):
    """Which show the bar's evening belongs to."""

    def test_tomorrows_show_is_not_tonights(self):
        """An event's date sits early in its own day, so a timestamp window caught the NEXT night's show from
        this afternoon: the board announced Friday's headliner on a Thursday with nothing on."""
        from api.tables_views import current_show

        now = timezone.localtime(timezone.now()).replace(hour=15, minute=30)
        Event.objects.create(name='Tomorrow', slug='tomorrow-show', status=Event.ACTIVE, venue=self.venue,
                             date=(now + timedelta(days=1)).replace(hour=0, minute=0))
        self.assertIsNone(current_show(now), 'nothing is on tonight')

    def test_tonights_show_is_found_from_the_afternoon_and_after_midnight(self):
        from api.tables_views import current_show

        now = timezone.localtime(timezone.now()).replace(hour=15, minute=30)
        tonight = Event.objects.create(name='Tonight', slug='tonight-show', status=Event.ACTIVE, venue=self.venue,
                                       date=now.replace(hour=0, minute=0))
        self.assertEqual(current_show(now), tonight)
        after_midnight = (now + timedelta(days=1)).replace(hour=0, minute=40)
        self.assertEqual(current_show(after_midnight), tonight, 'the tab has not changed hands at 00:40')


class TableQueueAndBreakdownTests(ApiTestCase):
    """The queue across the room, and the per-table breakdown behind it."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from sales.models import TableOrder, TableOrderItem

        self.client.force_login(get_user_model().objects.create_user('bar7', password='x', is_staff=True))
        self.old = TableOrder.objects.create(table_number=2, currency='mxn', total_cents=12000,
                                             created_at=timezone.now() - timedelta(minutes=18))
        TableOrderItem.objects.create(order=self.old, name='Mezcal', quantity=2, unit_price_cents=6000)
        self.fresh = TableOrder.objects.create(table_number=8, currency='mxn', total_cents=5000)
        TableOrderItem.objects.create(order=self.fresh, name='Cerveza', quantity=1, unit_price_cents=5000)

    def board(self, **params):
        return self.client.get('/tables/', params).content.decode()

    def test_the_queue_lists_every_waiting_table_longest_first(self):
        page = self.board()
        self.assertIn('Waiting now', page)
        self.assertLess(page.index('Table 2'), page.index('Table 8'), '18 minutes waiting outranks just now')

    def test_a_table_with_nothing_waiting_is_not_in_the_queue(self):
        self.client.post('/tables/2/close/')
        queue = self.board().split('<div class="board">')[0]
        self.assertNotIn('Table 2', queue)
        self.assertIn('Table 8', queue)

    def test_the_breakdown_is_closed_until_asked_for(self):
        page = self.board()
        # The card always summarises what is waiting; the breakdown is the itemised panel behind it.
        self.assertIn('2 x Mezcal', page)
        self.assertNotIn('<div class="rounds-list">', page)
        self.assertIn('See breakdown', page)

    def test_the_breakdown_itemises_that_table_only(self):
        page = self.board(open='2')
        self.assertEqual(page.count('<div class="rounds-list">'), 1, 'one table opens at a time')
        self.assertIn('120 MXN', page)
        self.assertIn('round-state', page)
        panel = page.split('<div class="rounds-list">')[1].split('</form>')[0]
        self.assertIn('Mezcal', panel)
        self.assertNotIn('Cerveza', panel, 'table 8 is a different table')

    def test_the_open_table_rides_in_the_url_so_a_refresh_keeps_it(self):
        """The board reloads itself every twenty seconds; a panel that snaps shut mid-read is worse than none."""
        page = self.board(open='2')
        self.assertIn('id="t2"', page)
        self.assertIn('Hide breakdown', page)
        self.assertIn('?open=8#t8', page, 'the other tables still offer to open')

    def test_a_delivered_round_stays_in_the_breakdown(self):
        self.client.post('/tables/2/close/')
        page = self.board(open='2')
        self.assertIn('2 x Mezcal', page)
        self.assertIn('Delivered at the table', page)

    def test_nonsense_in_the_url_does_not_break_the_board(self):
        self.assertIn('Waiting now', self.board(open='not-a-table'))


class RepliedUnsubscribeTests(ApiTestCase):
    """The commonest real request: a reply to their own ticket email, subject unchanged, asking in the body.

    Subject-only matching read those as ordinary replies and left the person on the list, which is how a
    polite request becomes a spam complaint, and a complaint costs the whole list's deliverability.
    """

    def _mbox(self, messages):
        import pathlib
        import tempfile

        path = pathlib.Path(tempfile.mkdtemp()) / 'inbox'
        path.write_text('\n'.join(
            f'From someone Thu Sep 25 14:00:00 2026\nFrom: {frm}\nSubject: {subject}\n\n{body}\n'
            for frm, subject, body in messages))
        return str(path)

    def run_on(self, messages, apply=True):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        args = ['process_unsubscribe_mail', '--mailbox', self._mbox(messages)]
        if apply:
            args.append('--apply')
        call_command(*args, stdout=out)
        return out.getvalue()

    def asking(self, email, subject, body):
        from crm.models import Contact

        person = Contact.objects.create(email=email, subscribed=True)
        self.run_on([(email, subject, body)])
        person.refresh_from_db()
        return person

    def test_a_spanish_reply_is_honoured(self):
        person = self.asking('ana@example.com', 'Re: Tus boletos: Privilegio',
                             'Hola, ya no quiero recibir correos. Gracias.')
        self.assertFalse(person.subscribed)

    def test_an_english_reply_is_honoured(self):
        person = self.asking('bob@example.com', 'Re: Your tickets', 'Please take me off your list, thanks.')
        self.assertFalse(person.subscribed)

    def test_a_one_word_reply_is_honoured(self):
        person = self.asking('cara@example.com', 'Re: Your tickets', 'Unsubscribe')
        self.assertFalse(person.subscribed)

    def test_our_own_footer_quoted_back_is_not_a_request(self):
        """A reply quotes the message underneath it, and our messages say the word."""
        body = ('Great show, thanks!\n\n'
                'On Wed, Sep 24, 2026 at 9:02 AM Iguana Comedy wrote:\n'
                '> You are booked. To stop receiving these, unsubscribe me here: https://x/y\n'
                '> Iguana Comedy')
        person = self.asking('dan@example.com', 'Re: Your tickets', body)
        self.assertTrue(person.subscribed, 'that was our own footer, quoted')

    def test_a_long_conversation_is_left_for_a_person_to_read(self):
        body = ('I wanted to ask about the show on Friday. ' * 20) + ' also please take me off your list'
        person = self.asking('eve@example.com', 'Re: Your tickets', body)
        self.assertTrue(person.subscribed, 'past a few lines it is a conversation, not a request')

    def test_an_address_we_do_not_hold_is_remembered_anyway(self):
        """They are not on the list today. This address has been imported from a spreadsheet once already."""
        from crm.models import Contact

        output = self.run_on([('stranger@example.com', 'unsubscribe', 'please')])
        self.assertIn('remembered anyway', output)
        remembered = Contact.objects.get(email='stranger@example.com')
        self.assertFalse(remembered.subscribed)
        self.assertIsNotNone(remembered.unsubscribed_at)

    def test_a_dry_run_remembers_nothing(self):
        from crm.models import Contact

        self.run_on([('stranger2@example.com', 'unsubscribe', 'please')], apply=False)
        self.assertFalse(Contact.objects.filter(email='stranger2@example.com').exists())


class AdFrequencyTests(ApiTestCase):
    """Reach and frequency, and the one arithmetic rule that makes them worth showing.

    Reach counts PEOPLE. Summing seven days of it counts somebody who saw the ad on Monday and again on
    Thursday twice, and a frequency derived from that sum reads LOWER than the truth, which is the direction
    that hides ad fatigue. So the seven-day row is asked for as a seven-day window and stored separately.
    """

    def rows(self, **kw):
        from crm.models import AdSpend

        base = dict(campaign_id='1', campaign_name='Open mic Spanish · reservations', kind=AdSpend.FREE,
                    spend_cents=10000, impressions=900, clicks=40, reach=300, frequency=3.0)
        base.update(kw)
        return AdSpend.objects.create(**base)

    def as_owner(self):
        from django.contrib.auth import get_user_model

        self.client.force_login(get_user_model().objects.create_user('boss3', password='x', is_staff=True,
                                                                     is_superuser=True))

    def test_the_week_row_is_stored_apart_from_the_days_that_make_it_up(self):
        from crm.models import AdSpend

        today = timezone.localdate()
        self.rows(day=today, window=AdSpend.DAY, reach=120, frequency=1.4)
        self.rows(day=today, window=AdSpend.WEEK, reach=300, frequency=3.0)
        self.assertEqual(AdSpend.objects.filter(day=today).count(), 2, 'same day, same campaign, two windows')

    def test_spend_totals_never_double_count_the_week_row(self):
        """The cost cards sum daily spend; a WEEK row is the same money again."""
        from crm.ad_spend import spend_between
        from crm.models import AdSpend

        today = timezone.localdate()
        self.rows(day=today, window=AdSpend.DAY, spend_cents=10000)
        self.rows(day=today, window=AdSpend.WEEK, spend_cents=70000)
        self.assertEqual(spend_between(today, today)[AdSpend.FREE], 10000)

    def test_the_page_shows_people_and_times_each(self):
        from crm.models import AdSpend

        self.rows(day=timezone.localdate(), window=AdSpend.WEEK, reach=412, frequency=2.4)
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('The ads, campaign by campaign', page)
        self.assertIn('412', page)
        self.assertIn('2.4', page)

    def test_a_saturated_campaign_is_called_out(self):
        from crm.models import AdSpend

        self.rows(day=timezone.localdate(), window=AdSpend.WEEK, frequency=4.2)
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertIn('same people over and over', page)
        self.assertIn('class="hot"', page)

    def test_a_healthy_frequency_is_not_called_out(self):
        from crm.models import AdSpend

        self.rows(day=timezone.localdate(), window=AdSpend.WEEK, frequency=1.6)
        self.as_owner()
        page = self.client.get('/stats/').content.decode()
        self.assertNotIn('same people over and over', page)
        self.assertNotIn('class="hot"', page)
