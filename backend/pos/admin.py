from django.contrib import admin

from .models import CashMove, Check, CheckLine, Comanda, Payment, Printer, PrintJob, Shift, Staff, Table, Zone


class LineInline(admin.TabularInline):
    model = CheckLine
    extra = 0
    fields = ('name', 'quantity', 'unit_price_cents', 'sent_at', 'voided_at', 'void_reason', 'voided_by')
    readonly_fields = fields


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('method', 'status', 'amount_cents', 'tip_cents', 'reference', 'created_by', 'created_at')
    readonly_fields = fields


@admin.register(Check)
class CheckAdmin(admin.ModelAdmin):
    list_display = ('folio', 'where', 'status', 'waiter', 'opened_at', 'closed_at')
    list_filter = ('status',)
    search_fields = ('folio', 'label')
    inlines = [LineInline, PaymentInline]


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'active')
    exclude = ('pin_hash',)


admin.site.register([Zone, Table, Shift, CashMove, Comanda, Printer, PrintJob])
