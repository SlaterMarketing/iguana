import json
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
        self.assertTrue(seat.description.endswith('Pagas en la puerta.'))

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
        self.assertEqual((seat.name, seat.price_cents, seat.capacity, seat.max_per_order, seat.pay_at_door),
                         ('Lugar reservado + 1 bebida gratis', 5000, 60, 6, False))
