from django.contrib import admin
from django.conf import settings
from django.utils.html import format_html

from .models import CreditTransfer, LoginToken, Membership, MembershipPlan, Order, OrderItem, RedeemCode, Ticket


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('ticket_type', 'name', 'quantity', 'unit_price_cents')


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    fields = ('ticket_type_name', 'checkin_link', 'checked_in_at')
    readonly_fields = ('ticket_type_name', 'checkin_link')

    def checkin_link(self, obj):
        return format_html('<a href="/checkin/{}/">check in</a>', obj.checkin_token) if obj.pk else ''


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'customer_email', 'event_name', 'status', 'total', 'tickets_page')
    list_filter = ('status', 'event')
    search_fields = ('customer_email', 'customer_name', 'event_name', 'stripe_payment_intent_id')
    raw_id_fields = ('contact', 'event')
    readonly_fields = ('public_view_token', 'stripe_payment_intent_id', 'stripe_charge_id', 'completed_at', 'attribution')
    inlines = [OrderItemInline, TicketInline]

    def total(self, obj):
        return f'{obj.total_amount_cents / 100:,.2f} {obj.currency.upper()}'

    def tickets_page(self, obj):
        return format_html('<a href="{}/orders/{}/" target="_blank">view</a>', settings.BACKEND_URL, obj.public_view_token)


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'currency', 'monthly_cents', 'annual_cents', 'active')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('contact', 'plan', 'status', 'source', 'starts_at', 'ends_at', 'credit_balance_cents')
    list_filter = ('status', 'plan', 'source')
    search_fields = ('contact__email', 'stripe_subscription_id')
    raw_id_fields = ('contact',)


@admin.register(RedeemCode)
class RedeemCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'kind', 'plan', 'days', 'amount_cents', 'uses', 'max_uses', 'expires_at')


@admin.register(CreditTransfer)
class CreditTransferAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'sender', 'to_email', 'amount_cents', 'currency', 'status')
    raw_id_fields = ('sender', 'recipient', 'from_membership')


@admin.register(LoginToken)
class LoginTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at', 'expires_at', 'used_at', 'attempts')
    exclude = ('token', 'code')
