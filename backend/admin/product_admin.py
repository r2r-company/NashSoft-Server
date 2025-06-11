from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline
from django.contrib import admin
from backend.models import Unit, ProductGroup, Product, ProductCalculation, ProductCalculationItem, DiscountRule, \
    ProductUnitConversion, PaymentType


@admin.register(Unit)
class UnitAdmin(UnfoldModelAdmin):
    search_fields = ('name',)

@admin.register(ProductGroup)
class ProductGroupAdmin(UnfoldModelAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)

class ProductUnitConversionInline(TabularInline):
    model = ProductUnitConversion
    extra = 1
    autocomplete_fields = ['from_unit', 'to_unit']

@admin.register(Product)
class ProductAdmin(UnfoldModelAdmin):
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
    fields = ['component', 'quantity', 'loss_percent', 'cooking_loss_percent', 'note']

@admin.register(ProductCalculation)
class ProductCalculationAdmin(UnfoldModelAdmin):
    list_display = ['product', 'date', 'note']
    list_filter = ['product__firm', 'product__type']
    search_fields = ['product__name', 'note']
    inlines = [ProductCalculationItemInline]

@admin.register(DiscountRule)
class DiscountRuleAdmin(UnfoldModelAdmin):
    list_display = ('name', 'percent', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    filter_horizontal = ('products', 'trade_points')
    search_fields = ('name',)



@admin.register(PaymentType)
class PaymentTypeAdmin(UnfoldModelAdmin):
    list_display = ['name']