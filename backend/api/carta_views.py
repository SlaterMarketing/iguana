"""La carta: precios, disponibilidad y qué descuenta cada cosa del inventario.

Spanish only, like the rest of the floor console.

Why the bar is trusted with prices at all: the menu already lives in the database rather than in the site's
code precisely so a price can change the night it changes, without a deploy and without asking anybody. Until
now "anybody" meant somebody with the admin, which is the one thing these accounts must not have. A price the
bar cannot fix is a price that stays wrong all night.

🚨 Changing a price never rewrites an order. `TableOrderItem` snapshots the name and the unit price when the
round is ordered, so tonight's correction cannot restate what a table already agreed to pay. That is what makes
handing this to the floor safe rather than reckless.
"""

from decimal import Decimal, InvalidOperation

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from catalog.models import InventoryItem, MenuCategory, MenuItem, MenuItemIngredient

from .floor import floor_required

# A cap, not a validation rule: nobody sells a drink for more than this, and a slipped finger that turns 60
# into 60000 would otherwise sit on the menu until a customer queried it.
MAX_PRICE = Decimal('100000')


def _money_cents(raw, default=None):
    """"60" or "60,50" from somebody in a hurry, into cents."""
    if raw is None:
        return default
    text = str(raw).strip().replace(',', '.').replace('$', '')
    if not text:
        return default
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return default
    if value.is_nan() or value.is_infinite() or value < 0 or value > MAX_PRICE:
        return default
    return int((value * 100).to_integral_value())


def _quantity(raw, default=None):
    if raw is None:
        return default
    text = str(raw).strip().replace(',', '.')
    if not text:
        return default
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return default
    if value.is_nan() or value.is_infinite() or value <= 0 or value > Decimal('1000'):
        return default
    return value.quantize(Decimal('0.001'))


@floor_required
def carta(request):
    categories = (MenuCategory.objects.filter(active=True)
                  .prefetch_related('items__ingredients__inventory_item'))
    grupos = []
    sin_receta = 0
    for category in categories:
        rows = []
        for item in category.items.all():
            ingredients = list(item.ingredients.all())
            if not ingredients:
                sin_receta += 1
            rows.append({'item': item, 'ingredientes': ingredients,
                         'precio': f'{item.price_cents / 100:g}'})
        grupos.append((category, rows))
    return render(request, 'floor/carta.html', {
        'grupos': grupos,
        'inventario': InventoryItem.objects.filter(active=True),
        'sin_receta': sin_receta,
        'categorias': categories,
    })


@floor_required
@require_POST
def save_item(request, item_id):
    """Price, name, description and whether it is on tonight."""
    item = MenuItem.objects.filter(id=item_id).first()
    if item is None:
        return redirect('floor-carta')
    name = (request.POST.get('name') or '').strip()[:120]
    if name:
        item.name = name
        # The floor console is Spanish, so what they type IS the Spanish name. Keeping them in step means the
        # customer menu does not end up showing an old name in one language and the new one in the other.
        item.name_es = name
    item.price_cents = _money_cents(request.POST.get('price'), item.price_cents)
    item.description = (request.POST.get('description') or '').strip()[:300]
    item.description_es = item.description
    item.available = bool(request.POST.get('available'))
    item.save(update_fields=['name', 'name_es', 'price_cents', 'description', 'description_es', 'available'])
    return redirect(f'/mesas/carta/#m{item.pk}')


@floor_required
@require_POST
def toggle_item(request, item_id):
    """On or off for tonight, in one tap, without opening the row.

    Turned off rather than deleted: it comes back tomorrow without being retyped, and an old order still names
    what it was.
    """
    item = MenuItem.objects.filter(id=item_id).first()
    if item is not None:
        item.available = not item.available
        item.save(update_fields=['available'])
    return redirect(f'/mesas/carta/#m{item_id}')


@floor_required
@require_POST
def add_menu_item(request):
    name = (request.POST.get('name') or '').strip()[:120]
    price = _money_cents(request.POST.get('price'))
    category = MenuCategory.objects.filter(id=request.POST.get('category'), active=True).first()
    if not name or price is None or category is None:
        return redirect('floor-carta')
    item = MenuItem.objects.create(category=category, name=name, name_es=name, price_cents=price,
                                   currency='mxn', available=True)
    return redirect(f'/mesas/carta/#m{item.pk}')


@floor_required
@require_POST
def link_ingredient(request, item_id):
    """Say what one of these takes out of the store room."""
    item = MenuItem.objects.filter(id=item_id).first()
    stock = InventoryItem.objects.filter(id=request.POST.get('inventory_item'), active=True).first()
    amount = _quantity(request.POST.get('quantity'), Decimal('1'))
    if item is None or stock is None or amount is None:
        return redirect('floor-carta')
    MenuItemIngredient.objects.update_or_create(menu_item=item, inventory_item=stock,
                                                defaults={'quantity': amount})
    return redirect(f'/mesas/carta/#m{item.pk}')


@floor_required
@require_POST
def unlink_ingredient(request, pk):
    row = MenuItemIngredient.objects.filter(pk=pk).first()
    item_id = row.menu_item_id if row else ''
    if row:
        row.delete()
    return redirect(f'/mesas/carta/#m{item_id}')
