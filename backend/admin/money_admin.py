from unfold.admin import ModelAdmin as UnfoldModelAdmin
from django.contrib import admin

from backend.models import Supplier, Customer
from settlements.models import Account, Contract, MoneyDocument, MoneyOperation, MoneyLedgerEntry


@admin.register(Account)
class AccountAdmin(UnfoldModelAdmin):
    list_display = ('name', 'company', 'type')
    list_filter = ('company', 'type')
    search_fields = ('name',)
    fieldsets = (((None, {'fields': (('company', 'name'), 'type')}),))

@admin.register(Contract)
class ContractAdmin(UnfoldModelAdmin):
    list_display = ('name', 'supplier', 'client', 'payment_type', 'account', 'contract_type', 'is_active')
    list_filter = ('is_active', 'contract_type', 'supplier', 'client')
    search_fields = ('name', 'supplier__name', 'client__name')

@admin.register(MoneyDocument)
class MoneyDocumentAdmin(UnfoldModelAdmin):
    list_display = ('doc_number', 'doc_type', 'company', 'firm', 'status', 'date')
    list_filter = ('doc_type', 'status', 'company', 'firm')
    search_fields = ('doc_number', 'comment')
    fieldsets = (((None, {'fields': (('company', 'firm'), 'doc_number', 'doc_type', 'status')}),))

@admin.register(MoneyOperation)
class MoneyOperationAdmin(UnfoldModelAdmin):
    list_display = ('document', 'account', 'amount', 'direction', 'visible', 'created_at')
    list_filter = ('direction', 'visible', 'account')
    search_fields = ('document__doc_number', 'account__name')


@admin.register(MoneyLedgerEntry)
class MoneyLedgerEntryAdmin(UnfoldModelAdmin):
    list_display = ('date', 'debit_account', 'credit_account', 'amount', 'document', 'supplier', 'customer')
    list_filter = ('debit_account', 'credit_account', 'supplier', 'customer')
    search_fields = ('document__doc_number', 'comment')
    readonly_fields = ('date',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name',)  # ← залиш тільки те, що точно є
    search_fields = ('name',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)