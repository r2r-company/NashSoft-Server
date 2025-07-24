# production/admin.py - ВИПРАВЛЕННЯ format_html ПОМИЛКИ
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    ProductionLine, WorkCenter, Equipment, WorkerPosition,
    ProductionWorker, WorkShift, ProductionPlan, ProductionPlanItem,
    ProductionOrder
)


# ========== ВИРОБНИЧА ІНФРАСТРУКТУРА ==========

@admin.register(ProductionLine)
class ProductionLineAdmin(ModelAdmin):
    list_display = [
        'name', 'code', 'company', 'firm', 'capacity_per_hour',
        'is_active', 'maintenance_mode', 'efficiency_display'
    ]
    list_filter = ['company', 'firm', 'is_active', 'maintenance_mode']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']

    def efficiency_display(self, obj):
        efficiency = obj.get_current_efficiency()
        color = 'green' if efficiency >= 80 else 'orange' if efficiency >= 60 else 'red'
        # ✅ ВИПРАВЛЕННЯ: використовуємо % замість f
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, efficiency / 100  # Ділимо на 100 для % форматування
        )

    efficiency_display.short_description = 'Ефективність'


@admin.register(WorkCenter)
class WorkCenterAdmin(ModelAdmin):
    list_display = [
        'name', 'code', 'production_line', 'work_type',
        'capacity_per_hour', 'cost_per_hour', 'is_active'
    ]
    list_filter = ['production_line', 'work_type', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Equipment)
class EquipmentAdmin(ModelAdmin):
    list_display = [
        'name', 'model', 'work_center', 'status',
        'maintenance_status', 'purchase_date'
    ]
    list_filter = ['status', 'work_center__production_line']
    search_fields = ['name', 'model', 'serial_number']

    def maintenance_status(self, obj):
        if obj.needs_maintenance():
            return format_html('<span style="color: red;">⚠️ Потрібне ТО</span>')
        elif obj.next_maintenance:
            days_left = (obj.next_maintenance.date() - timezone.now().date()).days
            if days_left <= 7:
                return format_html('<span style="color: orange;">📅 ТО через {} днів</span>', days_left)
            else:
                return format_html('<span style="color: green;">✅ OK</span>')
        return '❓ Не встановлено'

    maintenance_status.short_description = 'Статус ТО'


# ========== ВИРОБНИЧІ ПРАЦІВНИКИ ==========

@admin.register(WorkerPosition)
class WorkerPositionAdmin(ModelAdmin):
    list_display = ['name', 'hourly_rate']
    search_fields = ['name']


@admin.register(ProductionWorker)
class ProductionWorkerAdmin(ModelAdmin):
    list_display = [
        'employee_id', 'user', 'position', 'skill_level',
        'hire_date', 'is_active'
    ]
    list_filter = ['position', 'skill_level', 'is_active']
    search_fields = ['employee_id', 'user__username', 'user__first_name', 'user__last_name']
    filter_horizontal = ['work_centers']


@admin.register(WorkShift)
class WorkShiftAdmin(ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'duration_display', 'is_active']
    list_filter = ['is_active']

    def duration_display(self, obj):
        hours = obj.get_duration_hours()
        return "{} год".format(round(hours, 1))

    duration_display.short_description = 'Тривалість'


# ========== ПЛАНУВАННЯ ВИРОБНИЦТВА ==========

class ProductionPlanItemInline(TabularInline):
    model = ProductionPlanItem
    extra = 1
    fields = [
        'recipe', 'planned_quantity', 'planned_start_date',
        'planned_end_date', 'production_line', 'priority'
    ]


@admin.register(ProductionPlan)
class ProductionPlanAdmin(ModelAdmin):
    list_display = [
        'name', 'company', 'firm', 'plan_date_from', 'plan_date_to',
        'status_display', 'total_items', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'company', 'firm', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'approved_by', 'approved_at']
    inlines = [ProductionPlanItemInline]

    def total_items(self, obj):
        return obj.items.count()

    total_items.short_description = 'Кількість позицій'

    def status_display(self, obj):
        colors = {
            'draft': 'gray',
            'approved': 'green',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )

    status_display.short_description = 'Статус'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ProductionPlanItem)
class ProductionPlanItemAdmin(ModelAdmin):
    list_display = [
        'production_plan', 'recipe_product', 'planned_quantity',
        'planned_start_date', 'production_line', 'priority'
    ]
    list_filter = ['production_plan', 'production_line', 'priority']
    search_fields = ['recipe__product__name']

    def recipe_product(self, obj):
        return obj.recipe.product.name

    recipe_product.short_description = 'Продукт'


# ========== ВИРОБНИЧІ ЗАМОВЛЕННЯ ==========

@admin.register(ProductionOrder)
class ProductionOrderAdmin(ModelAdmin):
    list_display = [
        'order_number', 'recipe_product', 'quantity_ordered',
        'quantity_produced', 'status_display', 'priority_display',
        'due_date', 'completion_percentage_display', 'production_line'
    ]
    list_filter = [
        'status', 'priority', 'production_line', 'company', 'firm',
        'due_date', 'created_at'
    ]
    search_fields = ['order_number', 'recipe__product__name']
    readonly_fields = [
        'order_number', 'created_at', 'updated_at', 'started_at', 'completed_at'
    ]

    def recipe_product(self, obj):
        return obj.recipe.product.name

    recipe_product.short_description = 'Продукт'

    def status_display(self, obj):
        colors = {
            'draft': 'gray',
            'planned': 'blue',
            'released': 'orange',
            'in_progress': 'green',
            'completed': 'darkgreen',
            'cancelled': 'red',
            'on_hold': 'purple'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )

    status_display.short_description = 'Статус'

    def priority_display(self, obj):
        colors = {
            'low': 'gray',
            'normal': 'blue',
            'high': 'orange',
            'urgent': 'red'
        }
        color = colors.get(obj.priority, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_priority_display()
        )

    priority_display.short_description = 'Пріоритет'

    def completion_percentage_display(self, obj):
        percentage = obj.get_completion_percentage()
        if percentage == 100:
            color = 'green'
        elif percentage >= 50:
            color = 'orange'
        else:
            color = 'red'

        # ✅ ВИПРАВЛЕННЯ: спочатку форматуємо число, потім передаємо в format_html
        percentage_text = "{:.1f}%".format(percentage)
        return format_html(
            '<span style="color: {};">{}</span>',
            color, percentage_text
        )

    completion_percentage_display.short_description = '% виконання'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # Дії з замовленнями
    actions = ['mark_as_urgent', 'mark_as_completed', 'cancel_orders']

    def mark_as_urgent(self, request, queryset):
        updated = queryset.update(priority='urgent')
        self.message_user(
            request,
            '{} замовлень позначено як термінові.'.format(updated)
        )

    mark_as_urgent.short_description = 'Позначити як термінові'

    def mark_as_completed(self, request, queryset):
        updated = 0
        for order in queryset:
            if order.status == 'in_progress':
                order.status = 'completed'
                order.completed_at = timezone.now()
                order.quantity_produced = order.quantity_ordered
                order.save()
                updated += 1

        self.message_user(
            request,
            '{} замовлень завершено.'.format(updated)
        )

    mark_as_completed.short_description = 'Завершити виробництво'

    def cancel_orders(self, request, queryset):
        updated = queryset.exclude(status='completed').update(status='cancelled')
        self.message_user(
            request,
            '{} замовлень скасовано.'.format(updated)
        )

    cancel_orders.short_description = 'Скасувати замовлення'