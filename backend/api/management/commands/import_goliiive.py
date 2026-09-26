"""Bring a guest promoter's ticket sales into our own rows, so the door can work one list.

A show sold on two platforms has its guests in two places, and the door only has one phone. Until now the
promoter's share was a single number (`TicketType.sold_elsewhere`) that kept the counts honest and told the
door nothing: their buyers were invisible at `/mesas/reservas/` and unfindable at `/mesas/puerta/`.

🚨 Their QR codes are THEIRS and our scanner cannot read them. This does not pretend otherwise: it creates our
own ticket rows so the names can be found and admitted by hand, which is what the door does with them anyway.

🚨 It reads a file OUTSIDE this repository (`~/iguana-migration/`), and that is not incidental. The rows are
customers' names and addresses and the repository is public, so the data must never be a fixture, a default
path inside the tree, or an example in a docstring.

    manage.py import_goliiive ~/iguana-migration/goliiive-privilegio-2026-09-25.json [--apply]

Re-runnable: a buyer already imported for that event is left alone, so running it again after the promoter
sends an updated report only adds what is new.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import Event
from sales.models import Order, OrderItem, Ticket

# Marks the orders this command creates, so they can be told from our own sales and re-run safely.
SOURCE = 'goliiive'


class Command(BaseCommand):
    help = "Import a guest promoter's ticket sales so the door can find those guests by name."

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--apply', action='store_true', help='Actually write (otherwise a dry run)')

    def handle(self, *args, **opts):
        try:
            with open(opts['path'], encoding='utf-8') as handle:
                payload = json.load(handle)
        except OSError as exc:
            raise CommandError(f'cannot read {opts["path"]}: {exc}')

        event = Event.objects.filter(slug=payload.get('event')).first()
        if event is None:
            raise CommandError(f'no event with slug {payload.get("event")!r}')
        rows = payload.get('buyers') or []
        claimed = sum(int(b.get('tickets') or 0) for b in rows)

        # 🚨 One person can buy TWICE, and the report lists each purchase separately. Keying on the address
        # alone and skipping the repeat would silently drop a ticket: the file claims 37, a per-address import
        # would have created 36, and the missing seat would only surface as somebody turned away at the door.
        # So the purchases are summed per address and become one guest holding all of their seats.
        buyers = {}
        for row in rows:
            email = (row.get('email') or '').strip().lower()
            count = int(row.get('tickets') or 0)
            if not email or count < 1:
                continue
            held = buyers.setdefault(email, {'email': email, 'tickets': 0,
                                             'name': (row.get('name') or '').strip(),
                                             'tier': row.get('tier') or ''})
            held['tickets'] += count
            held['name'] = held['name'] or (row.get('name') or '').strip()
        buyers = list(buyers.values())

        # Whichever seat type the room sells, so the imported rows count against the same capacity.
        seat_type = event.ticket_types.filter(active=True).order_by('sort_order').first()

        made, seats, skipped = 0, 0, 0
        with transaction.atomic():
            for buyer in buyers:
                email = buyer['email']
                count = buyer['tickets']
                existing = Order.objects.filter(event=event, customer_email__iexact=email,
                                                source=SOURCE).first()
                if existing:
                    skipped += 1
                    continue
                self.stdout.write(f'  + {count} x {buyer.get("tier") or "?"} for {email[:3]}***')
                made += 1
                seats += count
                if not opts['apply']:
                    continue
                order = Order.objects.create(
                    event=event, event_name=event.name, currency='mxn',
                    customer_email=email, customer_name=(buyer.get('name') or '').strip()[:200],
                    status=Order.COMPLETED, completed_at=timezone.now(),
                    # No money on our side: the promoter took it. Recording a total here would double count
                    # the night's takings on `/stats/` and in the revenue page.
                    total_amount_cents=0, source=SOURCE,
                )
                tier = (buyer.get('tier') or 'General').title()
                for _ in range(count):
                    Ticket.objects.create(order=order, ticket_type_name=tier)
                # 🚨 An OrderItem as well, and not for tidiness: `sales.demand` counts `OrderItem.quantity`,
                # NOT ticket rows, so an import that creates only tickets is invisible to the room. It read
                # "39 of 80" straight after importing 37 more people, which is the number the board, the
                # nudges and the sold-out logic all trust. Price zero, because the promoter took the money.
                OrderItem.objects.create(order=order, ticket_type=seat_type, name=tier,
                                         quantity=count, unit_price_cents=0)

            if opts['apply'] and made:
                # 🚨 The promoter's share was a COUNT; now it is rows. Leaving both would count every one of
                # their guests twice, and the board would read the room as fuller than it is.
                for ticket_type in event.ticket_types.all():
                    if ticket_type.sold_elsewhere:
                        self.stdout.write(f'  sold_elsewhere {ticket_type.sold_elsewhere} -> 0 on '
                                          f'{ticket_type.name!r}, now that they are real rows')
                        ticket_type.sold_elsewhere = 0
                        ticket_type.save(update_fields=['sold_elsewhere'])

        self.stdout.write(f'{made} buyer(s), {seats} seat(s) imported, {skipped} already there'
                          + ('' if opts['apply'] else ' (dry run, pass --apply)'))
        # The promoter's report states its own total, so say when ours disagrees rather than leaving somebody
        # to notice at the door that the room is four people out.
        if skipped == 0 and seats != claimed:
            self.stdout.write(self.style.WARNING(
                f'  the file claims {claimed} tickets and {seats} were taken: check it before the doors open'))
