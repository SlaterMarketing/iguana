"""El inventario, para la gente que está en la barra.

Spanish only, and that is a decision rather than an omission: the floor console has one audience and it works
in Spanish. Everything customer-facing in this project is bilingual because a customer reads it; nobody
outside the building ever sees this page.

Three things it has to do at one in the morning on a phone, in order of how often: take one off, put one
back, and add something nobody thought of when the list was written. Everything else is secondary to those.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from catalog.models import InventoryChange, InventoryItem

from .floor import floor_required

AREA_LABELS = dict(InventoryItem.AREAS)


def _who(request):
    return (request.user.get_full_name() or request.user.get_username())[:80]


def _decimal(raw, default=None):
    """A number typed by somebody in a hurry: commas for decimals, spaces, or nothing at all."""
    if raw is None:
        return default
    text = str(raw).strip().replace(',', '.')
    if not text:
        return default
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return default
    # Guard rails rather than validation: a slipped finger should not write 10000 bottles of gin.
    if value.is_nan() or value.is_infinite() or abs(value) > Decimal('100000'):
        return default
    return value.quantize(Decimal('0.01'))


@floor_required
def inventory(request):
    items = list(InventoryItem.objects.filter(active=True))
    # Anything at or below its reorder level first, because the page exists to answer what to buy. Within
    # that, the order the staff themselves set.
    items.sort(key=lambda i: (not i.low, i.area, i.sort_order, i.name.lower()))
    groups = {}
    for item in items:
        groups.setdefault(item.area, []).append(item)
    return render(request, 'floor/inventario.html', {
        'grupos': [(AREA_LABELS.get(area, area), rows) for area, rows in groups.items()],
        'bajos': [i for i in items if i.low],
        'areas': InventoryItem.AREAS,
        'total': len(items),
        'movimientos': InventoryChange.objects.select_related('item')[:25],
    })


@floor_required
@require_POST
def adjust(request, item_id):
    """Take one off, put one back, or set the count to what is actually on the shelf."""
    item = InventoryItem.objects.filter(id=item_id, active=True).first()
    if item is None:
        return redirect('floor-inventory')

    with transaction.atomic():
        # Locked because two people counting the same fridge at once is the normal case, not the edge one.
        item = InventoryItem.objects.select_for_update().get(pk=item.pk)
        exact = _decimal(request.POST.get('set'))
        if exact is not None:
            delta = exact - item.quantity
            item.quantity = exact
        else:
            delta = _decimal(request.POST.get('delta'), Decimal('0'))
            item.quantity = item.quantity + delta
        # A count cannot be negative. Somebody who takes the last one twice means zero, not minus one.
        if item.quantity < 0:
            delta -= item.quantity
            item.quantity = Decimal('0')
        item.save(update_fields=['quantity', 'updated_at'])
        if delta:
            InventoryChange.objects.create(item=item, delta=delta, quantity_after=item.quantity,
                                           note=(request.POST.get('note') or '')[:200], who=_who(request))
    return redirect(f"/mesas/inventario/#i{item.pk}")


@floor_required
@require_POST
def add_item(request):
    """Add whatever the list was missing, with as few required fields as possible.

    A name is the only thing insisted on. Anything the person does not know yet can be filled in later, and a
    half-written row that exists beats a complete one that nobody stopped to type during service.
    """
    name = (request.POST.get('name') or '').strip()[:120]
    if not name:
        return redirect('floor-inventory')
    area = request.POST.get('area')
    item = InventoryItem.objects.create(
        name=name,
        area=area if area in dict(InventoryItem.AREAS) else InventoryItem.BAR,
        unit=(request.POST.get('unit') or '').strip()[:30],
        quantity=_decimal(request.POST.get('quantity'), Decimal('0')),
        par=_decimal(request.POST.get('par'), Decimal('0')),
        note=(request.POST.get('note') or '').strip()[:300],
    )
    if item.quantity:
        InventoryChange.objects.create(item=item, delta=item.quantity, quantity_after=item.quantity,
                                       note='alta', who=_who(request))
    return redirect(f"/mesas/inventario/#i{item.pk}")


@floor_required
@require_POST
def edit_item(request, item_id):
    """Rename, re-unit, change the reorder level, or archive it."""
    item = InventoryItem.objects.filter(id=item_id).first()
    if item is None:
        return redirect('floor-inventory')
    if request.POST.get('archive'):
        item.active = False
        item.save(update_fields=['active', 'updated_at'])
        return redirect('floor-inventory')
    name = (request.POST.get('name') or '').strip()[:120]
    if name:
        item.name = name
    area = request.POST.get('area')
    if area in dict(InventoryItem.AREAS):
        item.area = area
    item.unit = (request.POST.get('unit') or '').strip()[:30]
    item.par = _decimal(request.POST.get('par'), item.par)
    item.note = (request.POST.get('note') or '').strip()[:300]
    item.save(update_fields=['name', 'area', 'unit', 'par', 'note', 'updated_at'])
    return redirect(f"/mesas/inventario/#i{item.pk}")
