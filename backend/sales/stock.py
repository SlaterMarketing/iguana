"""Taking a delivered round out of the store room.

Applied when a round is DELIVERED, not when it is ordered. An order that is cancelled, or that a table changes
its mind about, never leaves the bar, and decrementing on the order would make the count sheet drift down by
every abandoned round. Delivery is the moment the thing physically goes.

🚨 It runs at most once per round, and that is enforced with a timestamp on the row rather than trusted to the
caller. Every realistic way this gets called twice is a normal event: a double tap on Delivered on a phone, a
page reload reposting the form, the board's own twenty-second refresh landing on a stale button, or Settle
marking an open round delivered after Delivered already did. Any of those emptying the fridge twice would make
the numbers lie in the direction nobody checks, because a count that is too LOW looks like theft rather than a
bug.
"""

import logging

from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)


def apply_stock(order, who=''):
    """Decrement every ingredient of every line on this delivered round. Returns rows written.

    Idempotent: a round that already carries `stock_applied_at` is left alone. Safe to call from anywhere that
    marks a round delivered, which is the point, because there are two such places and there will be a third.
    """
    from catalog.models import InventoryChange, InventoryItem

    if order.stock_applied_at:
        return 0

    written = 0
    with transaction.atomic():
        # Re-read under a lock: two people pressing Delivered on the same round at the same time is the normal
        # case behind a bar, not the edge one, and the check above would otherwise pass in both requests.
        locked = type(order).objects.select_for_update().get(pk=order.pk)
        if locked.stock_applied_at:
            return 0

        # Everything this round consumes, summed per inventory item first. A round with two gin and tonics and a
        # gin and soda touches the gin row once, so the history reads as one movement rather than three.
        needed = {}
        for line in locked.items.select_related('menu_item').all():
            if line.menu_item_id is None:
                continue   # a line whose menu item was deleted: nothing left to say what it consumed
            for ingredient in line.menu_item.ingredients.all():
                needed[ingredient.inventory_item_id] = (
                    needed.get(ingredient.inventory_item_id, 0) + ingredient.quantity * line.quantity)

        if needed:
            items = {i.id: i for i in InventoryItem.objects.select_for_update().filter(id__in=needed)}
            for item_id, amount in needed.items():
                item = items.get(item_id)
                if item is None:
                    continue
                before = item.quantity
                # Never below zero. A count that has drifted is already wrong; a NEGATIVE count is wrong and
                # also unreadable, and the person holding the phone cannot tell which of the two it is.
                item.quantity = max(before - amount, 0)
                item.save(update_fields=['quantity', 'updated_at'])
                InventoryChange.objects.create(
                    item=item, delta=item.quantity - before, quantity_after=item.quantity,
                    note=f'mesa {locked.table_number}', who=who or 'barra')
                written += 1

        locked.stock_applied_at = timezone.now()
        locked.save(update_fields=['stock_applied_at'])
        order.stock_applied_at = locked.stock_applied_at
    return written


def deliver(order, who=''):
    """Mark a round delivered and take it out of the store room, in that order and only once.

    Both things or neither: a round recorded as delivered whose stock never moved is the same silent drift this
    module exists to prevent, so they share the transaction.
    """
    from .models import TableOrder

    with transaction.atomic():
        if order.status == TableOrder.OPEN:
            order.status = TableOrder.DELIVERED
            order.delivered_at = timezone.now()
            order.save(update_fields=['status', 'delivered_at'])
        apply_stock(order, who=who)
    return order
