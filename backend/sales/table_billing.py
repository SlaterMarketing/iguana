"""The bill a table pays from its own phone, and the token the QR carries.

Two rules hold this together and both are about not trusting the browser.

🚨 **The amount is summed here, from the rounds, every time.** The page posts a tip CHOICE out of a fixed list
of percentages; it never posts an amount. A hidden field carrying a total is a field somebody can edit, and a
bar bill is precisely the thing worth editing.

🚨 **The QR is signed and scoped to one service.** A photograph of last night's QR must not open tonight's
bill, and a digit changed in the URL must not open the next table's. `django.core.signing` gives both: the
payload carries the table number and the service date, and a token that does not verify is simply not a table.
"""

from django.core import signing

from api.tables_views import CANCUN, current_show, service_start, table_labels
from .models import TableOrder

# The salt is its own, so a token minted here can never be read as anything else the project signs.
SALT = 'iguana.table.pay'

# What the customer may choose, and the ONLY values accepted. Fifteen is the default because it is what the
# house suggests (owner, 2026-09-25); zero is on the list deliberately, since a tip prompt with no way out is
# a demand rather than an offer and people resent being cornered by a screen.
TIP_CHOICES = (0, 10, 15, 20)
DEFAULT_TIP = 15


def token_for(table_number, day=None):
    """The string the QR encodes. Scoped to the service that is running now."""
    day = day or service_start().date()
    return signing.dumps({'t': int(table_number), 'd': day.isoformat()}, salt=SALT, compress=True)


def table_from_token(token):
    """The table this token opens, or None. Returns None for a token from another service."""
    try:
        data = signing.loads(token, salt=SALT, max_age=60 * 60 * 24 * 2)
    except signing.BadSignature:
        return None
    if data.get('d') != service_start().date().isoformat():
        return None  # last night's QR, photographed or left on a table
    return data.get('t')


def unpaid_rounds(table_number):
    """Every round this table still owes for, in the current service.

    The same window and the same exclusions as the board, so the two can never disagree about what is owed.
    """
    return (TableOrder.objects.filter(table_number=table_number, created_at__gte=service_start(),
                                      closed_at__isnull=True)
            .exclude(status__in=(TableOrder.PAID, TableOrder.CANCELLED))
            .prefetch_related('items').order_by('created_at'))


def tip_cents(bill_cents, percent):
    """The tip, rounded to the cent, on a percentage that must already be on the list."""
    if percent not in TIP_CHOICES:
        percent = DEFAULT_TIP
    return round(bill_cents * percent / 100)


def bill_for(table_number):
    """What this table owes right now: the lines, the total, the currency and whose night it is.

    Voided lines are left out by construction, because `TableOrder.total_cents` is recounted when a line comes
    off. Summing the items again here would put a drink somebody sent back straight back onto the bill.
    """
    rounds = list(unpaid_rounds(table_number))
    lines, currency = [], 'mxn'
    for order in rounds:
        currency = order.currency or currency
        for item in order.items.all():
            if item.voided:
                continue
            lines.append({'quantity': item.quantity, 'name': item.name,
                          'cents': item.unit_price_cents * item.quantity})
    show = current_show()
    return {
        'table': table_number,
        'label': table_labels().get(str(table_number), ''),
        'rounds': rounds,
        'lines': lines,
        'cents': sum(o.total_cents for o in rounds),
        'currency': currency,
        'show': show,
        'when': service_start().astimezone(CANCUN),
    }
