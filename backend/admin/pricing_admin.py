from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction

from backend.forms import PriceSettingItemForm
from backend.models import (
    PriceType, PriceSettingDocument, PriceSettingItem,
    TradePoint, ProductUnitConversion, Unit
)
from unfold.admin import  ModelAdmin, TabularInline


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
        'unit', 'unit_conversion', 'firm'
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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "unit":
            product_id = None
            if request.method == "POST":
                try:
                    post_data = request.POST
                    for key in post_data:
                        if key.endswith("-product"):
                            product_id = post_data[key]
                            break
                except:
                    pass

            if product_id:
                unit_ids = ProductUnitConversion.objects.filter(
                    product_id=product_id
                ).values_list('to_unit_id', flat=True)
                kwargs["queryset"] = Unit.objects.filter(id__in=unit_ids)
            else:
                kwargs["queryset"] = Unit.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PriceSettingDocument)
class PriceSettingDocumentAdmin(ModelAdmin):
    list_display = ('doc_number', 'company', 'valid_from', 'status')
    list_filter = ('company', 'status')
    search_fields = ('doc_number',)
    exclude = ['doc_number']
    inlines = [PriceSettingItemInline]

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form.save_m2m()

        if obj.firm and not obj.trade_points.exists():
            obj.trade_points.set(TradePoint.objects.filter(firm=obj.firm))

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        obj = form.instance
        trade_points = list(obj.trade_points.all())
        if not trade_points:
            raise ValidationError("Виберіть хоча б одну торгову точку.")

        # ❌ Видаляємо попередні елементи
        PriceSettingItem.objects.filter(price_setting_document=obj).delete()

        for formset in formsets:
            for form in formset.forms:
                if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                    item = form.save(commit=False)

                    if not item.unit_conversion:
                        raise ValidationError("Оберіть фасування (конверсію одиниці) для товару.")

                    for tp in trade_points:
                        PriceSettingItem.objects.create(
                            price_setting_document=obj,
                            product=item.product,
                            price_type=item.price_type,
                            price=item.price,
                            vat_percent=item.vat_percent,
                            vat_included=item.vat_included,
                            markup_percent=item.markup_percent,
                            trade_point=tp,
                            unit=item.unit,
                            unit_conversion=item.unit_conversion,
                            firm=obj.firm
                        )
