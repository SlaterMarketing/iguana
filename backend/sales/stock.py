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


def return_stock(item, who=''):
    """Put one voided line's ingredients back on the shelf. Returns rows written.

    Only ever called for a line voided as NOT_MADE, and only when the round had already been delivered, because
    a round that never left the bar never took anything out to give back. Both conditions are checked here
    rather than at the call site: this is the arithmetic that decides whether the count sheet is true, and it
    should not depend on every future caller remembering the rule.
    """
    from catalog.models import InventoryChange, InventoryItem

    if item.stock_returned_at or not item.order.stock_applied_at:
        return 0
    if item.menu_item_id is None:
        return 0   # the menu item is gone, so nothing records what this line consumed

    written = 0
    with transaction.atomic():
        locked = type(item).objects.select_for_update().get(pk=item.pk)
        if locked.stock_returned_at or not locked.order.stock_applied_at:
            return 0

        back = {}
        if locked.menu_item_id is not None:
            for ingredient in locked.menu_item.ingredients.all():
                back[ingredient.inventory_item_id] = (
                    back.get(ingredient.inventory_item_id, 0) + ingredient.quantity * locked.quantity)

        if back:
            rows = {i.id: i for i in InventoryItem.objects.select_for_update().filter(id__in=back)}
            for item_id, amount in back.items():
                stock = rows.get(item_id)
                if stock is None:
                    continue
                before = stock.quantity
                stock.quantity = before + amount
                stock.save(update_fields=['quantity', 'updated_at'])
                InventoryChange.objects.create(
                    item=stock, delta=amount, quantity_after=stock.quantity,
                    note=f'devuelto, mesa {locked.order.table_number}', who=who or 'barra')
                written += 1

        locked.stock_returned_at = timezone.now()
        locked.save(update_fields=['stock_returned_at'])
        item.stock_returned_at = locked.stock_returned_at
    return written


def void_line(item, reason, note='', who=''):
    """Take a line off the bill, and settle what that means for the store room.

    The two reasons are different facts, and conflating them is how a count sheet starts lying:

    NOT_MADE  the drink was never poured, so the ingredients are still in the bottle and the count comes back
              up. This is the "they didn't order it" case, a line added to the wrong table's ticket.
    WASTED    the drink was made and thrown away, so it is gone. The money comes off the bill and the count
              does NOT move: the stock is in a bin, and a sheet that claimed it was on the shelf would send
              somebody looking for it. This is the "it wasn't any good" case.

    Either way the line stays on the round, struck through, with who did it. Both things in one transaction,
    because a line off the bill whose stock never settled is the silent drift the rest of this module exists to
    prevent.
    """
    from .models import TableOrderItem

    with transaction.atomic():
        locked = TableOrderItem.objects.select_for_update().get(pk=item.pk)
        if locked.voided_at:
            return locked   # already off the bill; voiding twice must not refund twice
        locked.voided_at = timezone.now()
        locked.void_reason = reason if reason in dict(TableOrderItem.VOID_REASONS) else TableOrderItem.WASTED
        locked.void_note = (note or '')[:200]
        locked.voided_by = who
        locked.save(update_fields=['voided_at', 'void_reason', 'void_note', 'voided_by'])
        if locked.void_reason == TableOrderItem.NOT_MADE:
            return_stock(locked, who=who)
        locked.order.recount()
    item.refresh_from_db()
    return item
