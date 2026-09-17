from datetime import timedelta

from django.db import models
from django.utils import timezone

from catalog.models import Event, TicketType
from crm.models import Contact
from iguana.ids import new_id, new_token


class Order(models.Model):
    PENDING, COMPLETED, REFUNDED, CANCELLED = 'PENDING', 'COMPLETED', 'REFUNDED', 'CANCELLED'
    STATUS_CHOICES = [(s, s.title()) for s in (PENDING, COMPLETED, REFUNDED, CANCELLED)]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    currency = models.CharField(max_length=3, default='usd')
    total_amount_cents = models.PositiveIntegerField(default=0)
    discount_amount_cents = models.PositiveIntegerField(default=0)
    credits_applied_cents = models.PositiveIntegerField(default=0)
    # Reservations of pay-at-the-door ticket types: nothing is charged online and the door collects this amount,
    # so revenue actually received online is total_amount_cents - pay_at_door_cents.
    pay_at_door_cents = models.PositiveIntegerField(default=0)
    # The language the customer booked in; the order page and confirmation email follow it.
    locale = models.CharField(max_length=5, default='en')
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40, blank=True)
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    event_name = models.CharField(max_length=200, blank=True, help_text='Snapshot, kept when the event row is missing.')
    stripe_payment_intent_id = models.CharField(max_length=80, blank=True, db_index=True)
    stripe_charge_id = models.CharField(max_length=80, blank=True)
    public_view_token = models.CharField(max_length=60, default=new_token, unique=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    attribution = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer_email} {self.event_name} ({self.status})'


class OrderItem(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    ticket_type = models.ForeignKey(TicketType, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField()
    unit_price_cents = models.PositiveIntegerField()


class Ticket(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tickets')
    ticket_type_name = models.CharField(max_length=120)
    checkin_token = models.CharField(max_length=80, default=new_token, unique=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    @property
    def door_price_cents(self):
        """What the door collects for this seat: 0 unless the order was reserved to pay at the door."""
        if not self.order.pay_at_door_cents:
            return 0
        item = next((i for i in self.order.items.all() if i.name == self.ticket_type_name), None)
        return item.unit_price_cents if item else 0


class MembershipPlan(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    benefits = models.JSONField(default=list, blank=True, help_text='["Two free tickets", ...]')
    currency = models.CharField(max_length=3, default='mxn')
    monthly_cents = models.PositiveIntegerField(null=True, blank=True)
    annual_cents = models.PositiveIntegerField(null=True, blank=True)
    lifetime_cents = models.PositiveIntegerField(null=True, blank=True)
    pass_cents = models.PositiveIntegerField(null=True, blank=True)
    pass_days = models.PositiveIntegerField(null=True, blank=True)
    free_tickets_per_order = models.PositiveIntegerField(default=2)
    guest_discount_percent = models.PositiveIntegerField(default=10)
    stripe_product_id = models.CharField(max_length=60, blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Membership(models.Model):
    ACTIVE, PENDING, CANCELED, EXPIRED, PAST_DUE = 'ACTIVE', 'PENDING', 'CANCELED', 'EXPIRED', 'PAST_DUE'
    STATUS_CHOICES = [(s, s.replace('_', ' ').title()) for s in (ACTIVE, PENDING, CANCELED, EXPIRED, PAST_DUE)]

    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='memberships')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='memberships')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    source = models.CharField(max_length=20, blank=True, help_text='RECURRING, LIFETIME, PASS, CODE, MANUAL')
    billing_interval = models.CharField(max_length=10, blank=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    credit_balance_cents = models.IntegerField(default=0)
    stripe_subscription_id = models.CharField(max_length=80, blank=True, db_index=True)
    stripe_customer_id = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contact.email}: {self.plan.name} ({self.status})'

    @property
    def is_current(self):
        return self.status == self.ACTIVE and (self.ends_at is None or self.ends_at > timezone.now())


class RedeemCode(models.Model):
    MEMBERSHIP, CREDITS = 'membership', 'credits'

    code = models.CharField(max_length=40, unique=True)
    kind = models.CharField(max_length=12, choices=[(MEMBERSHIP, 'Membership'), (CREDITS, 'Credits')])
    plan = models.ForeignKey(MembershipPlan, null=True, blank=True, on_delete=models.PROTECT)
    days = models.PositiveIntegerField(null=True, blank=True, help_text='Membership length granted')
    amount_cents = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='mxn')
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.code


class CreditTransfer(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=new_id, editable=False)
    sender = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='credit_transfers_sent')
    from_membership = models.ForeignKey(Membership, null=True, blank=True, on_delete=models.SET_NULL)
    to_email = models.EmailField()
    recipient = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='credit_transfers_received')
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default='mxn')
    status = models.CharField(max_length=10, default='PENDING')
    created_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


def _login_expiry():
    return timezone.now() + timedelta(minutes=30)


class LoginToken(models.Model):
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=60, default=new_token, unique=True)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField(default=_login_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
