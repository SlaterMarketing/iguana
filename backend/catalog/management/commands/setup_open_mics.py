"""Put the weekly open mics on sale with paid seat reservations.

    manage.py setup_open_mics --dry-run
    manage.py setup_open_mics --show-time 20:00 --doors 19:30

Entry to an open mic is always free, but walk-ins can be turned away when the room is full. A reservation is paid
online when booked (50 MXN for the Spanish night, 5 USD for the English one), guarantees a seat and includes one
free drink. The room holds 80: 60 seats are sold as reservations and 20 are left for walk-ins.

Reservations are charged through Stripe, so the command refuses to publish them while Stripe is not configured:
a night nobody can pay for is worse than no Reserve button. `--pay-at-door` is the stopgap that takes the booking
online and collects the money on arrival instead.

Re-runnable. The reservation ticket type is updated in place and never duplicated, capacity is never set below seats
already booked, and an event that already has orders keeps its currency.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.serializers import sold_quantity
from catalog.models import Event, TicketType
from sales.models import Order
from sales.services import stripe_enabled

CANCUN = ZoneInfo('America/Cancun')
OPEN_MIC_TAG = 'open-mic'

# One reservation type, in both languages, for both nights: an English speaker can book the Spanish night too.
RESERVATION = {
    'name': 'Reserved seat + 1 free drink',
    'name_es': 'Lugar reservado + 1 bebida gratis',
    'description': ('Entry is always free, but without a reservation we may have to turn you away when it is full. '
                    'A reservation guarantees your seat and includes a free drink. Arrive when doors open.'),
    'description_es': ('La entrada siempre es gratis, pero sin reservación podemos negarte el paso si se llena. '
                       'Tu reservación te garantiza un lugar e incluye una bebida gratis. '
                       'Llega a la hora de apertura de puertas.'),
    'door_note': ' Pay at the door.',
    'door_note_es': ' Pagas en la puerta.',
}

SERIES = {
    'Noche de Open Mic - Espanol!': {'language': 'es', 'currency': 'mxn', 'price_cents': 5000},
    'Open Mic Night - English!': {'language': 'en', 'currency': 'usd', 'price_cents': 500},
}


class Command(BaseCommand):
    help = 'Publish the weekly open mics with paid seat reservations (seat + 1 free drink).'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='start', help='First show day, YYYY-MM-DD (default: today in Cancun)')
        parser.add_argument('--capacity', type=int, default=60, help='Reserved seats per night (default 60 of 80)')
        parser.add_argument('--max-per-order', type=int, default=6)
        parser.add_argument('--show-time', default='', help='24h clock, e.g. 20:00; blank leaves it unchanged')
        parser.add_argument('--doors', default='', help='24h clock, e.g. 19:30; blank leaves it unchanged')
        parser.add_argument('--pay-at-door', action='store_true',
                            help='Book online but collect the money on arrival (stopgap while Stripe is not set up)')
        parser.add_argument('--dry-run', action='store_true', help='Print what would change and roll back')

    def handle(self, *args, **opts):
        if not opts['pay_at_door'] and not stripe_enabled():
            raise CommandError('Stripe is not configured, so nobody could pay for a reservation. Set the Stripe keys '
                               'first, or pass --pay-at-door to take bookings now and collect at the door.')
        start = dt.date.fromisoformat(opts['start']) if opts['start'] else dt.datetime.now(CANCUN).date()
        since = dt.datetime.combine(start, dt.time.min, tzinfo=CANCUN)
        events = Event.objects.filter(name__in=SERIES, date__gte=since).select_related('venue').order_by('date')

        with transaction.atomic():
            for event in events:
                self.stdout.write(self.setup(event, SERIES[event.name], opts))
            mode = 'paid at the door' if opts['pay_at_door'] else 'paid online'
            self.stdout.write(f'{events.count()} open mic night(s) from {start}, reservations {mode}')
            if opts['dry_run']:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('dry run: nothing saved'))

    def setup(self, event, series, opts):
        notes = []
        if event.status == Event.DRAFT:
            event.status = Event.ACTIVE
        elif event.status != Event.ACTIVE:
            notes.append(f'left as {event.status}')

        if event.currency != series['currency']:
            if Order.objects.filter(event=event).exists():
                notes.append(f'kept currency {event.currency}: the event already has orders')
            else:
                event.currency = series['currency']
        event.language = series['language']
        event.ticketing_type = 'INTERNAL'
        # Member free tickets would turn a paid reservation into a free one.
        event.members_eligible = False
        event.tags = sorted(set(event.tags or []) | {OPEN_MIC_TAG})
        if opts['show_time']:
            event.show_time = opts['show_time']
        if opts['doors']:
            event.doors_open = opts['doors']
        event.save()

        # Before names were bilingual the Spanish night's type was named in Spanish; match either so it is updated.
        reservation = (event.ticket_types.filter(name__in=[RESERVATION['name'], RESERVATION['name_es']]).first()
                       or TicketType(event=event))
        booked = sold_quantity(reservation) if reservation.pk else 0
        door = opts['pay_at_door']
        reservation.name = RESERVATION['name']
        reservation.name_es = RESERVATION['name_es']
        reservation.description = RESERVATION['description'] + (RESERVATION['door_note'] if door else '')
        reservation.description_es = RESERVATION['description_es'] + (RESERVATION['door_note_es'] if door else '')
        reservation.price_cents = series['price_cents']
        reservation.capacity = max(opts['capacity'], booked)
        reservation.max_per_order = opts['max_per_order']
        reservation.pay_at_door = door
        reservation.active = True
        reservation.save()

        others = event.ticket_types.exclude(pk=reservation.pk).filter(active=True)
        if others.exists():
            notes.append(f'deactivated {", ".join(others.values_list("name", flat=True))}')
            others.update(active=False)

        venue = event.venue.name if event.venue else event.venue_label or 'no venue'
        price = f'{reservation.price_cents / 100:g} {event.currency.upper()}'
        return (f'{event.date.astimezone(CANCUN):%a %Y-%m-%d} {event.name:30} {event.status:7} {venue:14} '
                f'{price:>7} x {reservation.capacity} seats, {booked} booked'
                + (f' | {"; ".join(notes)}' if notes else ''))
