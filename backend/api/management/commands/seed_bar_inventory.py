"""Give the count sheet a starting point, and only where the arithmetic is honest.

The bar's menu splits in two, and the split decides what can be seeded and what cannot.

Eight items are sold AS the unit: four beers and four bottled soft drinks. One sale is one bottle out of the
fridge, so a 1:1 recipe is not an assumption, it is the fact. Those are seeded wired up.

Five are pours: two shots, and three mixed drinks built from a spirit plus a mixer. One sale is some fraction
of a bottle, and the fraction depends on this bar's glassware and how they pour. Seeding a guess there would
make the count sheet drift every night, and the drift is invisible until somebody counts by hand and finds the
numbers lying. So the bottles are created, the quantities are left at zero, and the RECIPE is left blank on
purpose: `/mesas/carta/` shows those items as `sin receta` so the hole is visible instead of silent, and the
bar says what a pour is in the one place that knows.

Re-runnable. It never overwrites a count somebody has taken, never changes a recipe already defined, and
never resurrects an item that was archived.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import InventoryItem, MenuItem, MenuItemIngredient

# Sold as the unit: the menu name IS the thing in the fridge, so one sale is one of these.
UNIT_SOLD = {
    'Modelo Especial': 'botella',
    'XX': 'botella',
    'Victoria': 'botella',
    'Coors Light': 'botella',
    'Coca-Cola': 'botella',
    'Coca Zero': 'botella',
    'Topo Chico': 'botella',
    'Bottled water': 'botella',
}

# The bottles behind the pours. Created so they can be counted and so they appear in the recipe picker on
# `/mesas/carta/`; deliberately NOT linked to anything, because the measure is theirs to state.
POURED = {
    'Bacardi': 'botella',
    'Tequila': 'botella',
    'Mezcal Montelobos': 'botella',
    'Smirnoff': 'botella',
    'Hielo': 'kg',
    'Limones': 'kg',
    'Sal': 'kg',
}


class Command(BaseCommand):
    help = 'Create the bar inventory and wire the 1:1 items to it. Safe to re-run.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        made, linked, skipped = 0, 0, 0

        for name, unit in {**UNIT_SOLD, **POURED}.items():
            existing = InventoryItem.objects.filter(name=name).first()
            if existing:
                skipped += 1
                continue
            self.stdout.write(f'  + {name} ({unit})')
            if not dry:
                InventoryItem.objects.create(name=name, unit=unit, quantity=Decimal('0'), par=Decimal('0'))
            made += 1

        for menu_name, unit in UNIT_SOLD.items():
            item = MenuItem.objects.filter(name=menu_name).first()
            stock = InventoryItem.objects.filter(name=menu_name).first()
            if item is None or (stock is None and not dry):
                continue
            if item.ingredients.exists():
                continue   # somebody has already said what this consumes; leave it theirs
            self.stdout.write(f'  = {menu_name}: 1 {unit}')
            if not dry:
                MenuItemIngredient.objects.create(menu_item=item, inventory_item=stock, quantity=Decimal('1'))
            linked += 1

        # In a dry run nothing was written, so every item it WOULD have wired still reads as unwired. Reporting
        # that verbatim would make a dry run describe a state that will never exist, which is the kind of
        # honest-looking output that gets acted on.
        blank = [m.name for m in MenuItem.objects.filter(available=True)
                 if not m.ingredients.exists() and not (dry and m.name in UNIT_SOLD)]
        self.stdout.write(f'{made} item(s) created, {skipped} already there, {linked} recipe(s) wired'
                          + (' (dry run, nothing written)' if dry else ''))
        if blank:
            self.stdout.write(f'{len(blank)} menu item(s) still have no recipe, on purpose: {", ".join(blank)}')
            self.stdout.write('  The measure is theirs to set, at /mesas/carta/ under Receta.')
