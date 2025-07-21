from unfold.admin import ModelAdmin as UnfoldModelAdmin, ModelAdmin
from django.contrib import admin
from backend.models import Company, Firm, Warehouse, Department, TradePoint, DepartmentWarehouseAccess, CustomerType


@admin.register(Company)
class CompanyAdmin(ModelAdmin):
    search_fields = ('name',)

@admin.register(Warehouse)
class WarehouseAdmin(ModelAdmin):
    search_fields = ('name',)

@admin.register(Firm)
class FirmAdmin(ModelAdmin):
    list_display = ('name', 'company', 'vat_type')
    list_filter = ('company', 'vat_type')
    search_fields = ('name',)

@admin.register(TradePoint)
class TradePointAdmin(ModelAdmin):
    list_display = ('name', 'firm')
    list_filter = ('firm',)
    search_fields = ('name',)

@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ('name', 'firm')
    search_fields = ('name',)
    fieldsets = (((None, {'fields': (('firm', 'name'),)}),))

@admin.register(DepartmentWarehouseAccess)
class DepartmentWarehouseAccessAdmin(ModelAdmin):
    list_display = ('department', 'warehouse')
    list_filter = ('department', 'warehouse')


@admin.register(CustomerType)
class CustomerTypeAdmin(ModelAdmin):
    list_display = ["id", "name"]