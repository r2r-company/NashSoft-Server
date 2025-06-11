from rest_framework.exceptions import ValidationError
from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline
from django.contrib import admin
from django.utils.html import format_html
from backend.models import Document, DocumentItem, Operation
from backend.services.document_admin_service import try_post_document_if_needed



class DocumentItemInline(TabularInline):
    model = DocumentItem
    extra = 1
    autocomplete_fields = ['product']


@admin.register(Document)
class DocumentAdmin(UnfoldModelAdmin):
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
class DocumentItemAdmin(UnfoldModelAdmin):
    list_display = ('document', 'product', 'quantity', 'price')
    list_filter = ('product',)




@admin.register(Operation)
class OperationAdmin(UnfoldModelAdmin):
    list_display = ('document', 'product', 'quantity', 'direction', 'visible', 'warehouse', 'created_at')
    list_filter = ('direction', 'visible', 'warehouse', 'product')
    search_fields = ('document__doc_number',)



