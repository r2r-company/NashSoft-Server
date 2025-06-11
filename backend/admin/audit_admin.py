from unfold.admin import ModelAdmin as UnfoldModelAdmin
from django.contrib import admin
from backend.models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(UnfoldModelAdmin):
    search_fields = ('name',)