# pricing_admin.py - ВИПРАВЛЕНИЙ

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction

from backend.forms import PriceSettingItemForm
from backend.models import (
    PriceType, PriceSettingDocument, PriceSettingItem,
    TradePoint, ProductUnitConversion, Unit
)
from unfold.admin import ModelAdmin, TabularInline


@admin.register(PriceType)
class PriceTypeAdmin(ModelAdmin):
    list_display = ('name', 'is_default')
    list_filter = ('is_default',)
    search_fields = ('name',)


class PriceSettingItemInline(TabularInline):
    model = PriceSettingItem
    form = PriceSettingItemForm
    extra = 0
    fields = (
        'product', 'price_type', 'price',
        'vat_percent', 'vat_included', 'markup_percent',
        'unit_conversion', 'firm'  # ✅ ПРИБРАВ 'unit' - воно автоматичне
    )
    autocomplete_fields = ("product",)
    can_delete = True

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        class CustomFormSet(formset):
            def save_new(self, form, commit=True):
                # ❌ Не зберігаємо тут — збереження вручну в save_related
                return None

        return CustomFormSet


@admin.register(PriceSettingDocument)
class PriceSettingDocumentAdmin(ModelAdmin):
    list_display = ('doc_number', 'company', 'firm', 'valid_from', 'status')  # ✅ ДОДАВ firm
    list_filter = ('company', 'firm', 'status')  # ✅ ДОДАВ firm
    search_fields = ('doc_number',)
    exclude = ['doc_number']
    inlines = [PriceSettingItemInline]

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form.save_m2m()

        # ✅ АВТОМАТИЧНО ДОДАЄМО ТОРГОВІ ТОЧКИ ФІРМИ
        if obj.firm and not obj.trade_points.exists():
            trade_points = TradePoint.objects.filter(firm=obj.firm)
            if trade_points.exists():
                obj.trade_points.set(trade_points)

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        obj = form.instance
        trade_points = list(obj.trade_points.all())

        if not trade_points:
            raise ValidationError("Виберіть хоча б одну торгову точку або додайте торгову точку до фірми.")

        # ❌ Видаляємо попередні елементи
        PriceSettingItem.objects.filter(price_setting_document=obj).delete()

        for formset in formsets:
            for form_item in formset.forms:
                if form_item.cleaned_data and not form_item.cleaned_data.get("DELETE", False):
                    item_data = form_item.cleaned_data

                    # ✅ ДОЗВОЛЯЄМО БЕЗ unit_conversion (базова одиниця)
                    for tp in trade_points:
                        PriceSettingItem.objects.create(
                            price_setting_document=obj,
                            product=item_data['product'],
                            price_type=item_data['price_type'],
                            price=item_data['price'],
                            vat_percent=item_data.get('vat_percent', 20),
                            vat_included=item_data.get('vat_included', True),
                            markup_percent=item_data.get('markup_percent', 0),
                            trade_point=tp,
                            unit_conversion=item_data.get('unit_conversion'),  # ✅ Може бути None
                            firm=obj.firm
                        )