from unfold.admin import ModelAdmin as UnfoldModelAdmin
from django.contrib import admin
from kkm.models import CashRegister, CashShift, FiscalReceipt, ReceiptOperation, CashSession, CashWorkstation

@admin.register(CashRegister)
class CashRegisterAdmin(UnfoldModelAdmin):
    list_display = ('name', 'company', 'firm', 'register_type', 'active')
    list_filter = ('company', 'firm', 'register_type', 'active')
    search_fields = ('name',)
    fieldsets = (((None, {'fields': (('company', 'firm'), 'name', 'register_type', 'active')}),))

@admin.register(CashShift)
class CashShiftAdmin(UnfoldModelAdmin):
    list_display = ('cash_register', 'opened_by', 'opened_at', 'closed_at', 'is_closed')
    list_filter = ('cash_register', 'is_closed')
    search_fields = ('cash_register__name', 'opened_by__username')

@admin.register(FiscalReceipt)
class FiscalReceiptAdmin(UnfoldModelAdmin):
    list_display = ('fiscal_number', 'shift', 'status', 'printed_at', 'sale_document')
    list_filter = ('status', 'shift__cash_register')
    search_fields = ('fiscal_number',)

@admin.register(ReceiptOperation)
class ReceiptOperationAdmin(UnfoldModelAdmin):
    list_display = ('receipt', 'product', 'quantity', 'price', 'warehouse', 'created_at')
    list_filter = ('product', 'warehouse')
    search_fields = ('receipt__fiscal_number', 'product__name')

@admin.register(CashSession)
class CashSessionAdmin(UnfoldModelAdmin):
    list_display = ('firm', 'trade_point', 'opened_by', 'opened_at', 'closed_at', 'is_closed')
    list_filter = ('firm', 'trade_point', 'is_closed')
    search_fields = ('firm__name', 'trade_point__name', 'opened_by__username')

@admin.register(CashWorkstation)
class CashWorkstationAdmin(UnfoldModelAdmin):
    list_display = ("name", "role", "cash_register", "active")
    list_filter = ("role", "active", "cash_register")
    search_fields = ("name", "app_key")
