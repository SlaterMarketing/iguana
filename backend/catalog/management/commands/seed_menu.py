"""Put the club's drinks menu in the database.

The menu is the one the bar actually prints, typed from `drinks eng pdf-1.pdf` and `menu iguana bebidas esp.pdf`
(2026-09-22), so /menu/ is real text a search engine can read and a phone can zoom, rather than a PDF nobody
opens on mobile. Prices are the same on both sheets; only the wording differs.

Re-runnable. `--overwrite` resets names and prices on rows that already exist, which is how a price change goes
out; without it, an edit made in the admin is left alone. Anything this command seeded earlier and no longer
lists is removed, so the placeholder menu that stood in before the real one arrived does not linger.
"""

from django.core.management.base import BaseCommand

from catalog.models import MenuCategory, MenuItem

# (category en, category es, [(item en, item es, price in pesos)])
MENU = [
    ('Beers', 'Cervezas', [
        ('Modelo Especial', 'Modelo Especial', 60),
        ('XX', 'XX', 50),
        ('Victoria', 'Victoria', 50),
        ('Coors Light', 'Coors Light', 50),
    ]),
    ('Cocktails', 'Cócteles', [
        ('Bacardi + Coke', 'Bacardi + Coca', 60),
        ('Topo Chico Margarita', 'Topo Chico margarita', 60),
        ('Flavored Smirnoff', 'Smirnoff sabor', 60),
    ]),
    ('Non-alcoholic', 'Sin alcohol', [
        ('Coca-Cola', 'Coca Cola', 40),
        ('Coca Zero', 'Coca Zero', 40),
        ('Topo Chico', 'Topo Chico', 45),
        ('Bottled water', 'Botella de agua', 30),
    ]),
    ('Shots', 'Shots', [
        ('Mezcal Montelobos', 'Mezcal Montelobos', 60),
        ('Tequila', 'Tequila', 60),
    ]),
]

# The stand-in menu seeded before the real sheets arrived. Removed on sight: leaving invented prices next to
# real ones is worse than having had no menu at all.
PLACEHOLDERS = ['Beer', 'Soft drinks', 'Snacks']


class Command(BaseCommand):
    help = "Seed the club's drinks menu, as printed."

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true',
                            help='Reset names and prices on rows that already exist. Discards admin edits.')

    def handle(self, *args, **opts):
        made = touched = 0
        wanted = {}
        for order, (name, name_es, items) in enumerate(MENU):
            category, created = MenuCategory.objects.get_or_create(
                name=name, defaults={'name_es': name_es, 'sort_order': order})
            if created or opts['overwrite']:
                category.name_es, category.sort_order, category.active = name_es, order, True
                category.save()
            wanted[category.pk] = {item for item, _, _ in items}

            for position, (item, item_es, pesos) in enumerate(items):
                row, is_new = MenuItem.objects.get_or_create(
                    category=category, name=item,
                    defaults={'name_es': item_es, 'price_cents': pesos * 100, 'currency': 'mxn',
                              'sort_order': position})
                if is_new:
                    made += 1
                elif opts['overwrite']:
                    row.name_es, row.price_cents, row.currency = item_es, pesos * 100, 'mxn'
                    row.sort_order, row.available = position, True
                    row.save()
                    touched += 1

        # Anything this command used to seed and no longer lists, category by category.
        removed = 0
        for category_pk, names in wanted.items():
            removed += MenuItem.objects.filter(category__pk=category_pk).exclude(name__in=names).delete()[0]
        stale = MenuCategory.objects.filter(name__in=PLACEHOLDERS).delete()

        self.stdout.write(f'{made} item(s) added, {touched} updated, '
                          f'{removed} stale item(s) and {stale[0]} placeholder row(s) removed')
        self.stdout.write(f'{MenuItem.objects.filter(available=True).count()} drinks on the menu now')
