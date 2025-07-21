from rest_framework.exceptions import ValidationError
from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline, ModelAdmin
from django.contrib import admin
from django.utils.html import format_html
from backend.models import Document, DocumentItem, Operation, AccountingSettings, DocumentSettings
from backend.services.document_admin_service import try_post_document_if_needed



class DocumentItemInline(TabularInline):
    model = DocumentItem
    extra = 1
    autocomplete_fields = ['product']


@admin.register(Document)
class DocumentAdmin(ModelAdmin):
    list_display = ('doc_number', 'doc_type', 'company', 'firm', 'warehouse', 'colored_status', 'status', 'date')
    list_filter = ('doc_type', 'status', 'company', 'firm', 'warehouse')
    search_fields = ('doc_number',)
    exclude = ('doc_number',)
    inlines = [DocumentItemInline]

    def colored_status(self, obj):
        color = {
            'draft': '#ffc107',
            'posted': '#28a745',
            'cancelled': '#dc3545'
        }.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color:white; background-color:{}; padding:2px 6px; border-radius:4px;">{}</span>',
            color, obj.get_status_display()
        )
    colored_status.short_description = "Статус"

    def save_model(self, request, obj, form, change):
        old_status = None
        if obj.pk:
            old_status = Document.objects.filter(pk=obj.pk).values_list("status", flat=True).first()

        if form.cleaned_data.get("status") == "posted" and old_status != "posted":
            obj.status = "draft"  # ⛔ запобігаємо помилці при save()

        super().save_model(request, obj, form, change)

        try_post_document_if_needed(request, obj, form, old_status)


@admin.register(DocumentItem)
class DocumentItemAdmin(ModelAdmin):
    list_display = ('document', 'product', 'quantity', 'price')
    list_filter = ('product',)




@admin.register(Operation)
class OperationAdmin(ModelAdmin):
    list_display = ('document', 'product', 'quantity', 'direction', 'visible', 'warehouse', 'created_at')
    list_filter = ('direction', 'visible', 'warehouse', 'product')
    search_fields = ('document__doc_number',)


@admin.register(AccountingSettings)
class AccountingSettingsAdmin(ModelAdmin):
    list_display = ('company', 'stock_account', 'supplier_account', 'default_vat_rate', 'default_price_type')
    list_filter = ('company',)

    fieldsets = (
        ('Компанія', {
            'fields': ('company',)
        }),
        ('Рахунки товарів', {
            'fields': ('stock_account', 'supplier_account', 'vat_input_account')
        }),
        ('Рахунки продажів', {
            'fields': ('client_account', 'revenue_account', 'vat_output_account')
        }),
        ('Ставки ПДВ', {
            'fields': ('default_vat_rate', 'reduced_vat_rate', 'zero_vat_rate')
        }),
        ('Ціноутворення', {  # ⬅️ НОВА СЕКЦІЯ
            'fields': ('default_price_type',)
        }),
    )


@admin.register(DocumentSettings)
class DocumentSettingsAdmin(ModelAdmin):
    list_display = ('company', 'receipt_prefix', 'sale_prefix', 'transfer_prefix')
    list_filter = ('company',)

    fieldsets = (
        ('Компанія', {
            'fields': ('company',)
        }),
        ('Основні документи', {
            'fields': ('receipt_prefix', 'sale_prefix', 'transfer_prefix', 'inventory_prefix')
        }),
        ('Повернення', {
            'fields': ('return_to_supplier_prefix', 'return_from_client_prefix')
        }),
        ('Інше', {
            'fields': ('stock_in_prefix', 'conversion_prefix')
        }),
    )