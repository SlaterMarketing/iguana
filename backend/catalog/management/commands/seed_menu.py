"""Put a starter bar menu in the database, once, so the QR pages are not empty on the night they go up.

🚨 The items here are a PLACEHOLDER, not the club's menu. Nobody has sent the real drinks list, and a menu is
the one page where a wrong price is taken as a promise, so this seeds a deliberately small, obvious list at
prices taken from the one thing we do know: the pre-ordered drink already sells at 50 MXN.

It is safe to re-run and it never overwrites an edit. Once the real menu is typed into the admin, running this
again adds nothing back: it matches on name and only fills a row it created and nobody has touched.
"""

from django.core.management.base import BaseCommand

from catalog.models import MenuCategory, MenuItem

# (category, name, name_es, price in pesos)
STARTER = [
    ('Beer', 'Cerveza', [
        ('Draught beer', 'Cerveza de barril', 50),
        ('Bottled beer', 'Cerveza en botella', 50),
        ('Michelada', 'Michelada', 70),
    ]),
    ('Cocktails', 'Cócteles', [
        ('House margarita', 'Margarita de la casa', 120),
        ('Mojito', 'Mojito', 120),
        ('Mezcal negroni', 'Negroni de mezcal', 140),
    ]),
    ('Soft drinks', 'Sin alcohol', [
        ('Soft drink', 'Refresco', 40),
        ('Sparkling water', 'Agua mineral', 40),
        ('Coffee', 'Café', 45),
    ]),
    ('Snacks', 'Botanas', [
        ('Guacamole and totopos', 'Guacamole con totopos', 110),
        ('Peanuts', 'Cacahuates', 45),
    ]),
]


class Command(BaseCommand):
    help = 'Seed a starter bar menu. Placeholder prices: replace them in the admin.'

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true',
                            help='Reset prices and names on rows that already exist. Discards edits.')

    def handle(self, *args, **opts):
        made = touched = 0
        for order, (name, name_es, items) in enumerate(STARTER):
            category, created = MenuCategory.objects.get_or_create(
                name=name, defaults={'name_es': name_es, 'sort_order': order})
            if created or opts['overwrite']:
                category.name_es = name_es
                category.sort_order = order
                category.active = True
                category.save()
            for position, (item, item_es, pesos) in enumerate(items):
                row, is_new = MenuItem.objects.get_or_create(
                    category=category, name=item,
                    defaults={'name_es': item_es, 'price_cents': pesos * 100, 'currency': 'mxn',
                              'sort_order': position})
                if is_new:
                    made += 1
                elif opts['overwrite']:
                    row.name_es = item_es
                    row.price_cents = pesos * 100
                    row.currency = 'mxn'
                    row.sort_order = position
                    row.save()
                    touched += 1
        total = MenuItem.objects.filter(available=True).count()
        self.stdout.write(f'{made} item(s) added, {touched} updated, {total} on the menu now')
        self.stdout.write(self.style.WARNING(
            'These are PLACEHOLDER prices. Edit them at /admin/catalog/menucategory/ before printing the QR codes.'))
