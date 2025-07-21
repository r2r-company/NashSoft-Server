from unfold.admin import ModelAdmin as UnfoldModelAdmin, ModelAdmin
from django.contrib import admin
from backend.models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    search_fields = ('name',)