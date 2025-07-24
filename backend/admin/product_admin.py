from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline, ModelAdmin
from django.contrib import admin
from backend.models import Unit, ProductGroup, Product, ProductCalculation, ProductCalculationItem, DiscountRule, \
    ProductUnitConversion, PaymentType


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    search_fields = ('name',)

@admin.register(ProductGroup)
class ProductGroupAdmin(ModelAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)

class ProductUnitConversionInline(TabularInline):
    model = ProductUnitConversion
    extra = 1
    autocomplete_fields = ['from_unit', 'to_unit']

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('id', 'name', 'type', 'firm', 'unit',  'group')
    list_filter = ('type', 'firm', 'group')
    search_fields = ('name',)
    inlines = [ProductUnitConversionInline]
    fieldsets = (
        (None, {
            'fields': (
                ('firm', 'name'),
                ('type', 'unit'),
            )
        }),
    )


class ProductCalculationItemInline(TabularInline):
    model = ProductCalculationItem
    extra = 1
    autocomplete_fields = ['component']
    fields = [
        'component', 'quantity', 'unit_conversion', 'loss_percent',
        'cooking_loss_percent', 'note'
    ]

    # ✅ ДОДАЄМО JAVASCRIPT ДЛЯ ФІЛЬТРАЦІЇ ФАСУВАНЬ
    class Media:
        js = ('admin/js/calculation_packaging.js',)


@admin.register(ProductCalculation)
class ProductCalculationAdmin(ModelAdmin):
    list_display = ['product', 'date', 'note', 'total_ingredients']
    list_filter = ['product__firm', 'product__type']
    search_fields = ['product__name', 'note']
    inlines = [ProductCalculationItemInline]

    def total_ingredients(self, obj):
        return obj.items.count()

    total_ingredients.short_description = 'Кількість інгредієнтів'

@admin.register(DiscountRule)
class DiscountRuleAdmin(ModelAdmin):
    list_display = ('name', 'percent', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    filter_horizontal = ('products', 'trade_points')
    search_fields = ('name',)



@admin.register(PaymentType)
class PaymentTypeAdmin(ModelAdmin):
    list_display = ['name']