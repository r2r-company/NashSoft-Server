# production/serializers.py
from rest_framework import serializers
from django.utils import timezone
from backend.models import ProductCalculation, Product, Warehouse
from .models import (
    ProductionLine, WorkCenter, Equipment, WorkerPosition,
    ProductionWorker, WorkShift, ProductionPlan, ProductionPlanItem,
    ProductionOrder
)


# ========== ІНФРАСТРУКТУРА ==========

class ProductionLineSerializer(serializers.ModelSerializer):
    efficiency = serializers.SerializerMethodField()
    current_workload = serializers.SerializerMethodField()

    class Meta:
        model = ProductionLine
        fields = [
            'id', 'company', 'firm', 'name', 'code', 'description',
            'capacity_per_hour', 'is_active', 'maintenance_mode',
            'warehouse', 'efficiency', 'current_workload',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_efficiency(self, obj):
        return obj.get_current_efficiency()

    def get_current_workload(self, obj):
        from .services import ProductionLineService
        service = ProductionLineService(obj)
        return service.get_current_workload()


class WorkCenterSerializer(serializers.ModelSerializer):
    production_line_name = serializers.CharField(source='production_line.name', read_only=True)

    class Meta:
        model = WorkCenter
        fields = [
            'id', 'production_line', 'production_line_name', 'name', 'code',
            'work_type', 'setup_time_minutes', 'capacity_per_hour',
            'cost_per_hour', 'is_active'
        ]


class EquipmentSerializer(serializers.ModelSerializer):
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    needs_maintenance = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = [
            'id', 'work_center', 'work_center_name', 'name', 'model',
            'serial_number', 'status', 'power_consumption',
            'purchase_date', 'purchase_price', 'maintenance_interval_hours',
            'last_maintenance', 'next_maintenance', 'needs_maintenance'
        ]

    def get_needs_maintenance(self, obj):
        return obj.needs_maintenance()


# ========== ПРАЦІВНИКИ ==========

class WorkerPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerPosition
        fields = ['id', 'name', 'description', 'hourly_rate']


class ProductionWorkerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    position_name = serializers.CharField(source='position.name', read_only=True)
    work_center_names = serializers.SerializerMethodField()

    class Meta:
        model = ProductionWorker
        fields = [
            'id', 'user', 'username', 'full_name', 'employee_id',
            'position', 'position_name', 'skill_level', 'work_centers',
            'work_center_names', 'hire_date', 'is_active'
        ]

    def get_work_center_names(self, obj):
        return [wc.name for wc in obj.work_centers.all()]


class WorkShiftSerializer(serializers.ModelSerializer):
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = WorkShift
        fields = [
            'id', 'name', 'start_time', 'end_time', 'work_days',
            'duration_hours', 'is_active'
        ]

    def get_duration_hours(self, obj):
        return obj.get_duration_hours()


# ========== ПЛАНУВАННЯ ==========

class ProductionPlanItemSerializer(serializers.ModelSerializer):
    recipe_name = serializers.CharField(source='recipe.product.name', read_only=True)
    production_line_name = serializers.CharField(source='production_line.name', read_only=True)
    estimated_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ProductionPlanItem
        fields = [
            'id', 'recipe', 'recipe_name', 'planned_quantity',
            'planned_start_date', 'planned_end_date', 'production_line',
            'production_line_name', 'priority', 'estimated_cost',
            'estimated_duration_hours', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at', 'estimated_cost']


class ProductionPlanSerializer(serializers.ModelSerializer):
    items = ProductionPlanItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    total_planned_quantity = serializers.SerializerMethodField()

    class Meta:
        model = ProductionPlan
        fields = [
            'id', 'company', 'firm', 'plan_date_from', 'plan_date_to',
            'name', 'description', 'status', 'created_by', 'created_by_name',
            'approved_by', 'approved_by_name', 'approved_at',
            'total_planned_quantity', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'approved_by', 'approved_at'
        ]

    def get_total_planned_quantity(self, obj):
        return obj.get_total_planned_quantity()


class ProductionPlanCreateSerializer(serializers.ModelSerializer):
    """Окремий серіалізатор для створення планів з позиціями"""
    items = ProductionPlanItemSerializer(many=True)

    class Meta:
        model = ProductionPlan
        fields = [
            'company', 'firm', 'plan_date_from', 'plan_date_to',
            'name', 'description', 'items'
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items')

        # Додаємо created_by з контексту
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user

        plan = ProductionPlan.objects.create(**validated_data)

        # Створюємо позиції
        for item_data in items_data:
            ProductionPlanItem.objects.create(
                production_plan=plan,
                **item_data
            )

        return plan


# ========== ВИРОБНИЧІ ЗАМОВЛЕННЯ ==========

class ProductionOrderSerializer(serializers.ModelSerializer):
    recipe_name = serializers.CharField(source='recipe.product.name', read_only=True)
    production_line_name = serializers.CharField(source='production_line.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.user.get_full_name', read_only=True)
    source_warehouse_name = serializers.CharField(source='source_warehouse.name', read_only=True)
    target_warehouse_name = serializers.CharField(source='target_warehouse.name', read_only=True)

    # Розрахункові поля
    completion_percentage = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    materials_validation = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrder
        fields = [
            'id', 'order_number', 'company', 'firm', 'production_plan',
            'recipe', 'recipe_name', 'quantity_ordered', 'quantity_produced',
            'order_date', 'due_date', 'started_at', 'completed_at',
            'production_line', 'production_line_name', 'status', 'priority',
            'created_by', 'created_by_name', 'assigned_to', 'assigned_to_name',
            'source_warehouse', 'source_warehouse_name',
            'target_warehouse', 'target_warehouse_name',
            'planned_cost', 'actual_cost', 'notes',
            'completion_percentage', 'is_overdue', 'materials_validation',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'order_number', 'created_at', 'updated_at', 'started_at', 'completed_at'
        ]

    def get_completion_percentage(self, obj):
        return obj.get_completion_percentage()

    def get_is_overdue(self, obj):
        return obj.is_overdue()

    def get_materials_validation(self, obj):
        """Перевірка наявності матеріалів"""
        if obj.status in ['draft', 'planned']:
            from .services import ProductionOrderService
            service = ProductionOrderService(obj)
            return service.validate_materials_availability()
        return None


class ProductionOrderCreateSerializer(serializers.ModelSerializer):
    """Спрощений серіалізатор для створення замовлень"""

    class Meta:
        model = ProductionOrder
        fields = [
            'company', 'firm', 'recipe', 'quantity_ordered', 'due_date',
            'production_line', 'source_warehouse', 'target_warehouse',
            'priority', 'notes'
        ]

    def create(self, validated_data):
        # Додаємо created_by з контексту
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user

        return ProductionOrder.objects.create(**validated_data)


# ========== ДЕШБОРД СЕРІАЛІЗАТОРИ ==========

class ProductionDashboardSerializer(serializers.Serializer):
    """Серіалізатор для дешборду виробництва"""

    # Загальна статистика
    total_orders = serializers.IntegerField()
    orders_in_progress = serializers.IntegerField()
    orders_completed_today = serializers.IntegerField()
    orders_overdue = serializers.IntegerField()

    # Ефективність
    overall_efficiency = serializers.FloatField()
    planned_vs_actual = serializers.DictField()

    # По виробничих лініях
    production_lines_status = serializers.ListField()

    # Топ продукції
    top_products = serializers.ListField()


class MaterialsRequirementSerializer(serializers.Serializer):
    """Серіалізатор для потреб у матеріалах"""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    required_quantity = serializers.FloatField()
    available_quantity = serializers.FloatField()
    shortage = serializers.FloatField()
    unit = serializers.CharField()


# ========== ACTION СЕРІАЛІЗАТОРИ ==========

class ProductionOrderActionSerializer(serializers.Serializer):
    """Серіалізатор для дій з виробничими замовленнями"""

    action = serializers.ChoiceField(choices=[
        ('start', 'Запустити'),
        ('complete', 'Завершити'),
        ('cancel', 'Скасувати'),
        ('pause', 'Призупинити')
    ])

    # Для завершення виробництва
    actual_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False
    )
    quality_grade = serializers.ChoiceField(
        choices=[('A', 'Відмінно'), ('B', 'Добре'), ('C', 'Задовільно')],
        required=False, default='A'
    )

    # Коментар
    comment = serializers.CharField(required=False, allow_blank=True)


class ProductionPlanActionSerializer(serializers.Serializer):
    """Серіалізатор для дій з планами виробництва"""

    action = serializers.ChoiceField(choices=[
        ('approve', 'Затвердити'),
        ('create_orders', 'Створити замовлення'),
        ('cancel', 'Скасувати')
    ])

    comment = serializers.CharField(required=False, allow_blank=True)