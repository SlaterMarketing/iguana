"""Put the point of sale in a usable state. Re-runnable: it only creates what is missing.

    manage.py pos_setup                                   # zone + tables from the old board's table count
    manage.py pos_setup --manager "Andrew" --pin 4821     # and a first manager, if none has that name

The map starts as the tables the bar already had (catalog.FloorSettings.tables, with any names it gave them),
laid out six to a row. Somebody with a manager PIN drags them into place at /pos/mesas/.
"""

from django.core.management.base import BaseCommand, CommandError

from catalog.models import FloorSettings
from pos.models import Staff, Table, Zone


class Command(BaseCommand):
    help = 'Create the default zone, the tables and optionally a first manager for the point of sale'

    def add_arguments(self, parser):
        parser.add_argument('--manager', default='')
        parser.add_argument('--pin', default='')

    def handle(self, *args, **opts):
        zone = Zone.objects.order_by('sort_order').first() or Zone.objects.create(name='Salón')
        settings = FloorSettings.load()
        labels = settings.labels or {}
        made = 0
        for n in range(1, (settings.tables or 12) + 1):
            if not Table.objects.filter(number=n).exists():
                row, col = divmod(n - 1, 6)
                Table.objects.create(zone=zone, number=n, name=str(labels.get(str(n), ''))[:40],
                                     x=4 + col * 16, y=6 + row * 22, w=12, h=15)
                made += 1
        self.stdout.write(f'{Table.objects.count()} table(s) on the map, {made} new')
        if opts['manager']:
            pin = str(opts['pin'])
            if not (pin.isdigit() and 4 <= len(pin) <= 6):
                raise CommandError('--pin must be 4 to 6 digits')
            staff = Staff.objects.filter(name=opts['manager']).first()
            if staff is None:
                clash = Staff.by_pin(pin)
                if clash:
                    raise CommandError(f'that PIN already belongs to {clash.name}')
                staff = Staff(name=opts['manager'], role=Staff.GERENTE)
                staff.set_pin(pin)
                staff.save()
                self.stdout.write(f'manager {staff.name} created')
            else:
                self.stdout.write(f'manager {staff.name} already exists, PIN left alone')
