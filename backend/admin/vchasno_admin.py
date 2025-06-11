from unfold.admin import ModelAdmin as UnfoldModelAdmin
from django.contrib import admin
from vchasno_kasa.models import VchasnoDevice, VchasnoCashier, VchasnoShift

@admin.register(VchasnoDevice)
class VchasnoDeviceAdmin(UnfoldModelAdmin):
    list_display = ('name', 'device_id', 'company', 'is_active', 'created_at')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'device_id')
    fieldsets = (((None, {'fields': (('company', 'name'), 'device_id', 'is_active')}),))

@admin.register(VchasnoCashier)
class VchasnoCashierAdmin(UnfoldModelAdmin):
    list_display = ('name', 'inn', 'user', 'cashier_id', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'inn', 'user__username')

@admin.register(VchasnoShift)
class VchasnoShiftAdmin(UnfoldModelAdmin):
    list_display = ('device', 'cashier', 'shift_number', 'status', 'opened_at', 'closed_at')
    list_filter = ('status', 'device')
    search_fields = ('device__name', 'cashier__name')