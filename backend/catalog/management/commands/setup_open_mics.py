"""Put the weekly open mics up with a FREE reserved seat, and sell drinks as the upsell.

    manage.py setup_open_mics --dry-run
    manage.py setup_open_mics --show-time 20:00 --doors 19:30

Entry is always free, but walk-ins can be turned away when the room is full. Reserving is free too and holds a
seat. The room holds 80: 60 are reservable and 20 are kept for walk-ins.

The seat used to cost 50 MXN and include a drink. It did not sell: the first day of ads produced 44 landing page
views and zero checkouts, because the thing the ad advertised as free asked for a card. The seat is now free and
the drinks are the sale, offered only after the details are filled in, so the free thing is claimed before money
is mentioned. Stripe is no longer a condition of publishing a night, only of the upsell appearing.

Re-runnable. The seat is matched by every name it has ever had and updated in place, never duplicated, capacity
is never set below seats already booked, and an event that already has orders keeps its currency.
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
    'name': 'Free reserved seat',
    'name_es': 'Lugar reservado gratis',
    'description': ('Entry is always free, but without a reservation we may have to turn you away when it is full. '
                    'Reserving costs nothing and holds your seat. Arrive when doors open.'),
    'description_es': ('La entrada siempre es gratis, pero sin reservación podemos negarte el paso si se llena. '
                       'Reservar no cuesta nada y te aparta el lugar. Llega a la hora de apertura de puertas.'),
    'door_note': ' Pay at the door.',
    'door_note_es': ' Pagas en la puerta.',
    # What this type has been called before. Without these the 31 nights already on sale would not be matched
    # and every one would get a SECOND seat type instead of having its price dropped to zero.
    'legacy_names': ['Reserved seat + 1 free drink', 'Lugar reservado + 1 bebida gratis'],
}

# The sale. Offered AFTER the details are filled in, because the reservation has to feel free to be worth
# advertising as free; the drinks are what the night actually earns.
# 🚨 OFF. Measured over the two days it ran on a free seat: 14 bookings, drinks pre-ordered by nobody, a 0%
# attach rate. It also sat between the last form field and the reserve button, so every visitor paid for it in
# scroll whether or not they wanted a drink.
#
# The offer was not wrong, the moment was. Somebody reserving a free seat three weeks out has not decided what
# they are drinking. The menu now goes to them AFTER they reserve, on the order page and in the confirmation,
# where they can also order from their table on the night.
#
# Turning it back on means flipping this and re-running the command; the existing rows are deactivated, not
# deleted, so nothing already ordered loses its name.
SELL_DRINKS_AT_CHECKOUT = False

DRINKS = {
    # Priced per drink, because the stepper beside it counts whatever this row is. Sold as a bundle of two it
    # read "2 drinks" next to a 4, which is eight drinks, and nothing on the page said so.
    'name': 'Drink, ordered in advance',
    'name_es': 'Bebida, pedida por adelantado',
    # The benefit in the owner's own words: the wait here is for a waiter, not a queue at the bar. Guessing at
    # "so you are not queuing at the bar" described a friction this room does not have.
    'description': 'Waiting for you at your seat when you arrive, so you do not have to wait for a waiter.',
    'description_es': 'Te esperan en tu lugar cuando llegues, para que no tengas que esperar al mesero.',
    'prices': {'mxn': 5000, 'usd': 300},
    'max_per_order': 12,
    # Matched so the nights already on sale are re-priced instead of getting a SECOND drinks row beside the old one.
    'legacy_names': ['2 drinks, ordered in advance', '2 bebidas, pedidas por adelantado'],
}

# Posters are made from hero video frames by scripts/make-banners.py: 16:9 for pages and Facebook, 4:5 for phones and
# Instagram, and one set per site language, since the artwork carries words.
# Every night gets the same explanation, in both site languages, with the language of the night dropped in.
BLURB = {
    'en': 'Free stand-up every week at Iguana Comedy, Playa del Carmen. Anyone can sign up for five minutes, or '
          'just come and watch. Entry is free, and reserving is free too: it just holds your seat.',
    'es': 'Stand-up gratis cada semana en Iguana Comedy, Playa del Carmen. Cualquiera puede anotarse para hacer '
          'cinco minutos, o simplemente venir a ver. La entrada es gratis, y reservar también: solo te aparta '
          'el lugar.',
}
# What this command used to write. A night still carrying one of these was never edited by hand, so the stale
# promise in it is ours to correct. Anything else is somebody's own copy and is never touched.
# Without this, "only fill blanks" meant all 31 nights kept advertising a free drink with the reservation for
# as long as they were on sale, hours after the seat became free and the drink became the thing being sold.
LEGACY_BLURBS = {
    'en': ['Free stand-up every week at Iguana Comedy, Playa del Carmen. Anyone can sign up for five minutes, '
           'or just come and watch. Entry is free, and a reservation holds your seat and includes a free drink.'],
    'es': ['Stand-up gratis cada semana en Iguana Comedy, Playa del Carmen. Cualquiera puede anotarse para hacer '
           'cinco minutos, o simplemente venir a ver. La entrada es gratis, y tu reservación te aparta el lugar e '
           'incluye una bebida gratis.'],
}

LONG_BLURB = {
    'en': ('{0}\n\nThe room holds 80 and the open mic fills up, so we reserve 60 seats online and keep the rest for '
           'walk-ins. Without a reservation we may have to turn you away once it is full.\n\nWant to perform? Sign '
           'up at the door when you arrive. Five minutes, any style, first time or hundredth.'),
    'es': ('{0}\n\nLa sala es de 80 lugares y el open mic se llena, así que apartamos 60 lugares en línea y '
           'dejamos el resto para quien llegue sin reservación. Si se llena, podemos negarte el paso.\n\n¿Quieres '
           'presentarte? Anótate en la puerta al llegar. Cinco minutos, el estilo que quieras, sea tu primera vez '
           'o la número cien.'),
}

SERIES = {
    'spanish-night': {
        'tag': 'open-mic-es',
        'legacy_names': ['Noche de Open Mic - Espanol!', 'Noche de Open Mic - Español!'],
        'name': 'Open Mic Night in Spanish',
        'name_es': 'Noche de Open Mic en Español',
        'language': 'es',
        'currency': 'mxn',
        'price_cents': 0,
        # From the night's own flyer: sign-up list at 8, show at 9.
        'doors': '20:00',
        'show_time': '21:00',
        'images': {'en': ('/media/events/open-mic-es-en-16x9.jpg', '/media/events/open-mic-es-en-4x5.jpg'),
                   'es': ('/media/events/open-mic-es-16x9.jpg', '/media/events/open-mic-es-4x5.jpg')},
    },
    'english-night': {
        'tag': 'open-mic-en',
        'legacy_names': ['Open Mic Night - English!'],
        'name': 'Open Mic Night in English',
        'name_es': 'Noche de Open Mic en Inglés',
        'language': 'en',
        'currency': 'usd',
        'price_cents': 0,
        # From the night's own flyer: doors at 8, show at 8:30.
        'doors': '20:00',
        'show_time': '20:30',
        'images': {'en': ('/media/events/open-mic-en-16x9.jpg', '/media/events/open-mic-en-4x5.jpg'),
                   'es': ('/media/events/open-mic-en-es-16x9.jpg', '/media/events/open-mic-en-es-4x5.jpg')},
    },
}


class Command(BaseCommand):
    help = 'Publish the weekly open mics with a free reserved seat and a drinks upsell.'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='start', help='First show day, YYYY-MM-DD (default: today in Cancun)')
        parser.add_argument('--capacity', type=int, default=60, help='Reserved seats per night (default 60 of 80)')
        parser.add_argument('--max-per-order', type=int, default=6)
        parser.add_argument('--show-time', default='', help="24h clock, e.g. 20:00; blank uses each series' own time")
        parser.add_argument('--doors', default='', help="24h clock, e.g. 19:30; blank uses each series' own time")
        parser.add_argument('--pay-at-door', action='store_true',
                            help='Book online but collect the money on arrival (stopgap while Stripe is not set up)')
        parser.add_argument('--dry-run', action='store_true', help='Print what would change and roll back')

    def handle(self, *args, **opts):
        if not stripe_enabled():
            self.stdout.write(self.style.WARNING(
                'Stripe is not configured. The free reservation still works; the drinks upsell will not appear.'))
        start = dt.date.fromisoformat(opts['start']) if opts['start'] else dt.datetime.now(CANCUN).date()
        since = dt.datetime.combine(start, dt.time.min, tzinfo=CANCUN)
        # Match on the tag this command sets, or on the names the series had before it was renamed. Tags are matched in
        # Python: a JSON "contains" lookup works on Postgres but not on SQLite, which the tests use.
        names = {name: series for series in SERIES.values() for name in [*series['legacy_names'], series['name']]}
        tags = {series['tag']: series for series in SERIES.values()}
        found = []
        for event in Event.objects.filter(date__gte=since).select_related('venue').order_by('date'):
            series = names.get(event.name) or next((tags[t] for t in (event.tags or []) if t in tags), None)
            if series:
                found.append((event, series))

        with transaction.atomic():
            for event, series in found:
                self.stdout.write(self.setup(event, series, opts))
            mode = ('paid at the door' if opts['pay_at_door'] else
                    'free, drinks sold as an upsell' if SELL_DRINKS_AT_CHECKOUT else
                    'free, menu sent after booking')
            self.stdout.write(f'{len(found)} open mic night(s) from {start}, reservations {mode}')
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
        event.name = series['name']
        event.name_es = series['name_es']
        # Fill a blank, and replace anything this command wrote before. A night given its own blurb in the
        # admin still keeps it.
        stale = {text for lang in ('en', 'es') for base in LEGACY_BLURBS[lang]
                 for text in (base, LONG_BLURB[lang].format(base))}
        for attr, text in (('description', BLURB['en']), ('description_es', BLURB['es']),
                           ('long_description', LONG_BLURB['en'].format(BLURB['en'])),
                           ('long_description_es', LONG_BLURB['es'].format(BLURB['es']))):
            current = getattr(event, attr)
            if not current or current in stale:
                setattr(event, attr, text)
        event.language = series['language']
        event.ticketing_type = 'INTERNAL'
        # Member free tickets would turn a paid reservation into a free one.
        event.members_eligible = False
        event.tags = sorted(set(event.tags or []) | {OPEN_MIC_TAG, series['tag']})
        # Only fill a missing poster: a night given its own poster in the admin keeps it.
        for attr, value in (('image_url', series['images']['en'][0]), ('image_url_mobile', series['images']['en'][1]),
                            ('image_url_es', series['images']['es'][0]), ('image_url_mobile_es', series['images']['es'][1])):
            if not getattr(event, attr):
                setattr(event, attr, value)
        # The two nights keep their own clocks; --show-time / --doors override both when they are passed.
        show_time = opts['show_time'] or series.get('show_time', '')
        doors = opts['doors'] or series.get('doors', '')
        if show_time:
            event.show_time = show_time
        if doors:
            event.doors_open = doors
        event.save()

        # Match what the type is called now AND everything it has been called before: the Spanish-only name from
        # before names were bilingual, and the paid "+ 1 free drink" name from before the seat became free.
        known = [RESERVATION['name'], RESERVATION['name_es'], *RESERVATION['legacy_names']]
        reservation = (event.ticket_types.filter(name__in=known, is_addon=False).first()
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

        # The upsell. Only where a card can actually be taken, because an add-on nobody can pay for is worse
        # than no add-on: it puts a price on a page that advertises the night as free.
        drinks = None
        if SELL_DRINKS_AT_CHECKOUT and stripe_enabled():
            known_drinks = [DRINKS['name'], DRINKS['name_es'], *DRINKS['legacy_names']]
            drinks = (event.ticket_types.filter(name__in=known_drinks, is_addon=True).first()
                      or TicketType(event=event))
            drinks.name = DRINKS['name']
            drinks.name_es = DRINKS['name_es']
            drinks.description = DRINKS['description']
            drinks.description_es = DRINKS['description_es']
            drinks.price_cents = DRINKS['prices'][event.currency]
            drinks.max_per_order = DRINKS['max_per_order']
            drinks.is_addon = True
            drinks.capacity = None
            drinks.active = True
            drinks.save()

        if not SELL_DRINKS_AT_CHECKOUT:
            known_drinks = [DRINKS['name'], DRINKS['name_es'], *DRINKS['legacy_names']]
            event.ticket_types.filter(name__in=known_drinks, is_addon=True, active=True).update(active=False)

        keep = [reservation.pk] + ([drinks.pk] if drinks else [])
        others = event.ticket_types.exclude(pk__in=keep).filter(active=True)
        if others.exists():
            notes.append(f'deactivated {", ".join(others.values_list("name", flat=True))}')
            others.update(active=False)

        venue = event.venue.name if event.venue else event.venue_label or 'no venue'
        price = 'free' if not reservation.price_cents else f'{reservation.price_cents / 100:g} {event.currency.upper()}'
        addon = (f'+ {drinks.price_cents / 100:g} {event.currency.upper()} drinks' if drinks else
                 'no checkout drinks' if not SELL_DRINKS_AT_CHECKOUT else 'no drinks (no Stripe)')
        return (f'{event.date.astimezone(CANCUN):%a %Y-%m-%d} {event.name:26} {event.status:7} {venue:14} '
                f'{price:>5} x {reservation.capacity} seats, {booked} booked, {addon}'
                + (f' | {"; ".join(notes)}' if notes else ''))
