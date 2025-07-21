from unfold.admin import ModelAdmin as UnfoldModelAdmin, ModelAdmin
from django.contrib import admin
from backend.models import Interface, AppUser

@admin.register(Interface)
class InterfaceAdmin(ModelAdmin):
    list_display = ('code', 'name', 'access_group')
    list_filter = ('access_group',)

@admin.register(AppUser)
class AppUserAdmin(ModelAdmin):
    list_display = ('user', 'company', 'is_active')
    list_filter = ('is_active', 'company')
    search_fields = ('user__username',)
    filter_horizontal = ('interfaces',)
    fieldsets = (((None, {'fields': (('company', 'user'), 'is_active', 'interfaces')}),))