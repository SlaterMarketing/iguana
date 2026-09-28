"""The bar's point of sale, modelled on Soft Restaurant (owner, 2026-09-28: "make it a clone of soft restaurant").

The shape is the one every Mexican bar already knows from that product:

  a MAP of tables  ->  a CUENTA (check) per table  ->  LINES added from a grid of products
  ->  ENVIAR sends the new lines to the bar as a COMANDA (and prints it)
  ->  PRECUENTA prints the bill  ->  COBRAR takes one or more PAGOS  ->  the check closes
  ->  every pago lands in the open TURNO, which is closed with a CORTE (counted cash against expected).

Who did what is a STAFF member with a PIN, not the shared floor login: the tablet is signed in as the floor
account (that is what keeps the admin shut, see api/floor.py), and the person tapping is whoever last typed a
PIN. Every void, discount and payment records that person.

Stock: the menu (catalog.MenuItem), recipes (catalog.MenuItemIngredient) and the count sheet
(catalog.InventoryItem / InventoryChange) are reused, not copied. A line takes its ingredients out when it is
SENT, because that is when the bar makes it; voiding a sent line as "no se preparó" puts them back, "se tiró"
does not.

Money is integer centavos everywhere, MXN. The English open mic sells tickets in dollars but the bar is pesos.
"""

from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from catalog.models import Event, InventoryItem, MenuItem
from iguana.ids import new_id, new_token


class Staff(models.Model):
    MESERO, CAJERO, GERENTE = 'MESERO', 'CAJERO', 'GERENTE'
    ROLES = [(MESERO, 'Mesero'), (CAJERO, 'Cajero'), (GERENTE, 'Gerente')]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    name = models.CharField(max_length=80)
    role = models.CharField(max_length=10, choices=ROLES, default=MESERO)
    pin_hash = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'staff'

    def __str__(self):
        return f'{self.name} ({self.get_role_display()})'

    def set_pin(self, pin):
        self.pin_hash = make_password(str(pin))

    def check_pin(self, pin):
        return bool(pin) and check_password(str(pin), self.pin_hash)

    @property
    def is_manager(self):
        return self.role == self.GERENTE

    @property
    def can_charge(self):
        return self.role in (self.CAJERO, self.GERENTE)

    @classmethod
    def by_pin(cls, pin):
        """The active staff member with this PIN, or None. A handful of rows, so checking each hash is fine."""
        pin = str(pin or '').strip()
        if not pin.isdigit() or not 4 <= len(pin) <= 6:
            return None
        return next((s for s in cls.objects.filter(active=True) if s.check_pin(pin)), None)


class Zone(models.Model):
    name = models.CharField(max_length=60)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Table(models.Model):
    """A table on the map. `number` is what the customer QR stickers carry (/menu/7/), so it must stay put."""

    SQUARE, ROUND, BAR = 'SQUARE', 'ROUND', 'BAR'
    SHAPES = [(SQUARE, 'Cuadrada'), (ROUND, 'Redonda'), (BAR, 'Barra')]

    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name='tables')
    number = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=40, blank=True, help_text='Blank shows the number.')
    shape = models.CharField(max_length=10, choices=SHAPES, default=SQUARE)
    seats = models.PositiveIntegerField(default=4)
    # Position and size on the map, in percent of the map's width and height, so it fits any tablet.
    x = models.FloatField(default=5)
    y = models.FloatField(default=5)
    w = models.FloatField(default=12)
    h = models.FloatField(default=12)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['zone__sort_order', 'number']

    def __str__(self):
        return self.label

    @property
    def label(self):
        return self.name or f'Mesa {self.number}'


class ModifierGroup(models.Model):
    """A choice asked when a product is added: "¿Cómo lo quieres?" with options, some costing extra."""

    name = models.CharField(max_length=60)
    min_select = models.PositiveIntegerField(default=0)
    max_select = models.PositiveIntegerField(default=1)
    items = models.ManyToManyField(MenuItem, blank=True, related_name='modifier_groups')
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Modifier(models.Model):
    group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, related_name='options')
    name = models.CharField(max_length=60)
    price_cents = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Shift(models.Model):
    """A turno de caja. Every payment belongs to the shift open when it was taken; the corte closes it."""

    OPEN, CLOSED = 'OPEN', 'CLOSED'

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    status = models.CharField(max_length=10, default=OPEN)
    opened_by = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='shifts_opened')
    opened_at = models.DateTimeField(default=timezone.now)
    opening_cash_cents = models.PositiveIntegerField(default=0)
    closed_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.PROTECT, related_name='shifts_closed')
    closed_at = models.DateTimeField(null=True, blank=True)
    counted_cash_cents = models.PositiveIntegerField(null=True, blank=True)
    counted_card_cents = models.PositiveIntegerField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f'Turno {timezone.localtime(self.opened_at):%d/%m %H:%M}'

    @classmethod
    def current(cls):
        return cls.objects.filter(status=cls.OPEN).order_by('-opened_at').first()


class CashMove(models.Model):
    """Money into or out of the drawer that is not a sale: a retiro to the safe, change brought in."""

    IN, OUT = 'IN', 'OUT'

    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='moves')
    kind = models.CharField(max_length=3, choices=[(IN, 'Entrada'), (OUT, 'Retiro')])
    amount_cents = models.PositiveIntegerField()
    reason = models.CharField(max_length=200)
    by = models.ForeignKey(Staff, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)


class Check(models.Model):
    """La cuenta. One open per table at a time; a bar or takeaway check has no table."""

    OPEN, PAID, CANCELLED = 'OPEN', 'PAID', 'CANCELLED'
    STATUSES = [(OPEN, 'Abierta'), (PAID, 'Pagada'), (CANCELLED, 'Cancelada')]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    folio = models.PositiveIntegerField(db_index=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=OPEN, db_index=True)
    table = models.ForeignKey(Table, null=True, blank=True, on_delete=models.SET_NULL, related_name='checks')
    label = models.CharField(max_length=60, blank=True, help_text='For a check with no table: "Barra", a name.')
    guests = models.PositiveIntegerField(default=1)
    waiter = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='checks')
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name='pos_checks')
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    # When the precuenta (the bill) was last printed. The map colours the table so the floor knows it is asked for.
    bill_printed_at = models.DateTimeField(null=True, blank=True)
    discount_cents = models.PositiveIntegerField(default=0)
    discount_reason = models.CharField(max_length=120, blank=True)
    discount_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    cancel_reason = models.CharField(max_length=200, blank=True)
    cancelled_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    note = models.CharField(max_length=200, blank=True)
    # What the customer's phone carries to pay this check by card (the QR on the precuenta).
    pay_token = models.CharField(max_length=60, default=new_token, unique=True)

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f'Cuenta {self.folio} {self.where}'

    @property
    def where(self):
        return self.table.label if self.table else (self.label or 'Barra')

    def live_lines(self):
        return [line for line in self.lines.all() if not line.voided_at]

    @property
    def subtotal_cents(self):
        return sum(line.total_cents for line in self.live_lines())

    @property
    def total_cents(self):
        return max(self.subtotal_cents - self.discount_cents, 0)

    @property
    def paid_cents(self):
        return sum(p.amount_cents for p in self.payments.all() if p.status == Payment.PAID)

    @property
    def tips_cents(self):
        return sum(p.tip_cents for p in self.payments.all() if p.status == Payment.PAID)

    @property
    def due_cents(self):
        return max(self.total_cents - self.paid_cents, 0)

    @property
    def unsent(self):
        return [line for line in self.live_lines() if not line.sent_at]


class CheckLine(models.Model):
    NOT_MADE, WASTED, MISTAKE = 'NOT_MADE', 'WASTED', 'MISTAKE'
    VOID_REASONS = [(NOT_MADE, 'No se preparó'), (WASTED, 'Se preparó y se tiró'), (MISTAKE, 'Error de captura')]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    cuenta = models.ForeignKey(Check, on_delete=models.CASCADE, related_name='lines')
    menu_item = models.ForeignKey(MenuItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # Snapshotted: tonight's price change cannot restate what a table already ordered.
    name = models.CharField(max_length=120)
    unit_price_cents = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    modifiers = models.JSONField(default=list, blank=True, help_text='[{"name": "", "priceCents": 0}]')
    note = models.CharField(max_length=200, blank=True)
    seat = models.PositiveIntegerField(null=True, blank=True)
    # Blank for a line the customer ordered from the table QR.
    created_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    from_customer = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    comanda = models.ForeignKey('Comanda', null=True, blank=True, on_delete=models.SET_NULL, related_name='lines')
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=10, choices=VOID_REASONS, blank=True)
    void_note = models.CharField(max_length=200, blank=True)
    voided_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    stock_applied_at = models.DateTimeField(null=True, blank=True)
    stock_returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.quantity} x {self.name}'

    @property
    def each_cents(self):
        return self.unit_price_cents + sum(int(m.get('priceCents') or 0) for m in (self.modifiers or []))

    @property
    def total_cents(self):
        return 0 if self.voided_at else self.each_cents * self.quantity


class Comanda(models.Model):
    """One send to the bar: the lines that were new when ENVIAR was pressed, numbered for the night."""

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    cuenta = models.ForeignKey(Check, on_delete=models.CASCADE, related_name='comandas')
    number = models.PositiveIntegerField()
    created_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    done_at = models.DateTimeField(null=True, blank=True, help_text='Marked served on the bar screen.')

    class Meta:
        ordering = ['-created_at']


class Payment(models.Model):
    CASH, CARD, TRANSFER, PHONE, COURTESY = 'CASH', 'CARD', 'TRANSFER', 'PHONE', 'COURTESY'
    METHODS = [(CASH, 'Efectivo'), (CARD, 'Tarjeta (terminal)'), (TRANSFER, 'Transferencia'),
               (PHONE, 'Tarjeta (celular)'), (COURTESY, 'Cortesía')]
    PENDING, PAID, REFUNDED = 'PENDING', 'PAID', 'REFUNDED'

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    cuenta = models.ForeignKey(Check, on_delete=models.CASCADE, related_name='payments')
    method = models.CharField(max_length=10, choices=METHODS)
    status = models.CharField(max_length=10, default=PAID)
    # What goes against the bill. The tip is on top and is the staff's, so it never counts as a sale.
    amount_cents = models.PositiveIntegerField()
    tip_cents = models.PositiveIntegerField(default=0)
    # Cash only: what the customer handed over, and what went back.
    received_cents = models.PositiveIntegerField(default=0)
    change_cents = models.PositiveIntegerField(default=0)
    reference = models.CharField(max_length=80, blank=True, help_text='Terminal voucher or transfer reference.')
    shift = models.ForeignKey(Shift, null=True, blank=True, on_delete=models.PROTECT, related_name='payments')
    created_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    stripe_payment_intent_id = models.CharField(max_length=80, blank=True, db_index=True)
    stripe_charge_id = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['created_at']


class Printer(models.Model):
    """A cloud printer that fetches its own jobs, so nothing has to run at the club.

    Epson TM (m30 and newer) with Server Direct Print, or Star with CloudPRNT, pointed at /pos/print/<token>/.
    """

    COMANDA, TICKET = 'COMANDA', 'TICKET'
    EPSON, STAR = 'EPSON', 'STAR'

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    name = models.CharField(max_length=60)
    role = models.CharField(max_length=10, choices=[(COMANDA, 'Comandas (barra)'), (TICKET, 'Tickets (caja)')])
    protocol = models.CharField(max_length=10, choices=[(EPSON, 'Epson Server Direct Print'), (STAR, 'Star CloudPRNT')],
                                default=EPSON)
    token = models.CharField(max_length=60, default=new_token, unique=True)
    active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class PrintJob(models.Model):
    QUEUED, SENT, DONE, FAILED = 'QUEUED', 'SENT', 'DONE', 'FAILED'

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    role = models.CharField(max_length=10)
    printer = models.ForeignKey(Printer, null=True, blank=True, on_delete=models.SET_NULL, related_name='jobs')
    title = models.CharField(max_length=80)
    # Plain lines, 42 characters wide (80mm paper at the printers' default font). Rendered as ePOS XML, Star
    # text or an HTML page for the browser fallback, from the same lines.
    lines = models.JSONField(default=list)
    status = models.CharField(max_length=10, default=QUEUED, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']


class Supplier(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
    note = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Purchase(models.Model):
    """Una compra: what came in, from whom, at what cost. Saving it adds the quantities to the count sheet."""

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name='purchases')
    reference = models.CharField(max_length=80, blank=True, help_text='Invoice or ticket number.')
    by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def total_cents(self):
        return sum(line.cost_cents for line in self.lines.all())


class PurchaseLine(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='+')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    cost_cents = models.PositiveIntegerField(default=0, help_text='Total paid for this line.')

    @property
    def unit_cost_cents(self):
        return int(Decimal(self.cost_cents) / self.quantity) if self.quantity else 0


class ItemCost(models.Model):
    """Last known unit cost of a count-sheet item, from the latest purchase. What costs a drink in the reports."""

    item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name='pos_cost')
    unit_cost_cents = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class StockCount(models.Model):
    """Un inventario físico: a count of everything, compared with what the sheet expected."""

    OPEN, APPLIED = 'OPEN', 'APPLIED'

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    status = models.CharField(max_length=10, default=OPEN)
    by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class StockCountLine(models.Model):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='+')
    expected = models.DecimalField(max_digits=10, decimal_places=2)
    counted = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    @property
    def variance(self):
        return None if self.counted is None else self.counted - self.expected
