# production/views.py
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.db.models import Q, Count, Sum
from datetime import datetime, timedelta

from backend.utils.responses import StandardResponse, DocumentActionResponse
from .models import (
    ProductionLine, WorkCenter, Equipment, WorkerPosition,
    ProductionWorker, WorkShift, ProductionPlan, ProductionPlanItem,
    ProductionOrder
)
from .serializers import (
    ProductionLineSerializer, WorkCenterSerializer, EquipmentSerializer,
    WorkerPositionSerializer, ProductionWorkerSerializer, WorkShiftSerializer,
    ProductionPlanSerializer, ProductionPlanCreateSerializer, ProductionPlanItemSerializer,
    ProductionOrderSerializer, ProductionOrderCreateSerializer,
    ProductionOrderActionSerializer, ProductionPlanActionSerializer,
    ProductionDashboardSerializer, MaterialsRequirementSerializer
)
from .services import (
    ProductionPlanService, ProductionOrderService, ProductionLineService,
    ProductionReportService
)


# ========== ІНФРАСТРУКТУРА ==========

class ProductionLineViewSet(ModelViewSet):
    queryset = ProductionLine.objects.all()
    serializer_class = ProductionLineSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.request.query_params.get('company')
        firm_id = self.request.query_params.get('firm')

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if firm_id:
            queryset = queryset.filter(firm_id=firm_id)

        return queryset.order_by('name')

    @action(detail=True, methods=['get'])
    def workload(self, request, pk=None):
        """Завантаження виробничої лінії"""
        line = self.get_object()
        service = ProductionLineService(line)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

        workload = service.get_current_workload(date_from, date_to)
        return StandardResponse.success(workload, "Завантаження лінії отримано")

    @action(detail=True, methods=['post'])
    def maintenance(self, request, pk=None):
        """Планування технічного обслуговування"""
        line = self.get_object()
        service = ProductionLineService(line)

        start_time = request.data.get('start_time')
        duration_hours = request.data.get('duration_hours', 4)
        description = request.data.get('description', '')

        if not start_time:
            return StandardResponse.error("Потрібно вказати start_time")

        try:
            start_time = datetime.fromisoformat(start_time)
            service.schedule_maintenance(start_time, duration_hours, description)
            return StandardResponse.success(None, "Технічне обслуговування заплановано")
        except Exception as e:
            return StandardResponse.error(str(e))


class WorkCenterViewSet(ModelViewSet):
    queryset = WorkCenter.objects.all()
    serializer_class = WorkCenterSerializer
    permission_classes = [AllowAny]


class EquipmentViewSet(ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [AllowAny]


# ========== ПРАЦІВНИКИ ==========

class WorkerPositionViewSet(ModelViewSet):
    queryset = WorkerPosition.objects.all()
    serializer_class = WorkerPositionSerializer
    permission_classes = [AllowAny]


class ProductionWorkerViewSet(ModelViewSet):
    queryset = ProductionWorker.objects.all()
    serializer_class = ProductionWorkerSerializer
    permission_classes = [AllowAny]


class WorkShiftViewSet(ModelViewSet):
    queryset = WorkShift.objects.all()
    serializer_class = WorkShiftSerializer
    permission_classes = [AllowAny]


# ========== ПЛАНУВАННЯ ==========

class ProductionPlanViewSet(ModelViewSet):
    queryset = ProductionPlan.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'create':
            return ProductionPlanCreateSerializer
        return ProductionPlanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.request.query_params.get('company')
        firm_id = self.request.query_params.get('firm')
        status = self.request.query_params.get('status')

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if firm_id:
            queryset = queryset.filter(firm_id=firm_id)
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def actions(self, request, pk=None):
        """Дії з планом виробництва"""
        plan = self.get_object()
        serializer = ProductionPlanActionSerializer(data=request.data)

        if not serializer.is_valid():
            return StandardResponse.error("Помилка валідації", details=serializer.errors)

        action_type = serializer.validated_data['action']
        service = ProductionPlanService(plan)

        try:
            if action_type == 'approve':
                service.approve_plan(request.user)
                return StandardResponse.success(None, f"План {plan.name} затверджено")

            elif action_type == 'create_orders':
                if plan.status != 'approved':
                    return StandardResponse.error("План повинен бути затверджений")

                orders = service.create_production_orders()
                return StandardResponse.success({
                    'orders_created': len(orders),
                    'order_numbers': [o.order_number for o in orders]
                }, f"Створено {len(orders)} виробничих замовлень")

            elif action_type == 'cancel':
                plan.status = 'cancelled'
                plan.save()
                return StandardResponse.success(None, f"План {plan.name} скасовано")

            else:
                return StandardResponse.error("Невідома дія")

        except Exception as e:
            return StandardResponse.error(str(e))


class ProductionPlanItemViewSet(ModelViewSet):
    queryset = ProductionPlanItem.objects.all()
    serializer_class = ProductionPlanItemSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'])
    def calculate_cost(self, request, pk=None):
        """Розрахунок планової собівартості"""
        item = self.get_object()
        try:
            cost = item.calculate_estimated_cost()
            return StandardResponse.success({
                'estimated_cost': float(cost)
            }, "Собівартість розрахована")
        except Exception as e:
            return StandardResponse.error(str(e))


# ========== ВИРОБНИЧІ ЗАМОВЛЕННЯ ==========

class ProductionOrderViewSet(ModelViewSet):
    queryset = ProductionOrder.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'create':
            return ProductionOrderCreateSerializer
        return ProductionOrderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.request.query_params.get('company')
        firm_id = self.request.query_params.get('firm')
        status = self.request.query_params.get('status')
        production_line_id = self.request.query_params.get('production_line')

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if firm_id:
            queryset = queryset.filter(firm_id=firm_id)
        if status:
            queryset = queryset.filter(status=status)
        if production_line_id:
            queryset = queryset.filter(production_line_id=production_line_id)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def actions(self, request, pk=None):
        """Дії з виробничим замовленням"""
        order = self.get_object()
        serializer = ProductionOrderActionSerializer(data=request.data)

        if not serializer.is_valid():
            return StandardResponse.error("Помилка валідації", details=serializer.errors)

        action_type = serializer.validated_data['action']
        service = ProductionOrderService(order, request)

        try:
            if action_type == 'start':
                result = service.start_production(request.user)
                return StandardResponse.success(result, f"Виробництво {order.order_number} запущено")

            elif action_type == 'complete':
                actual_quantity = serializer.validated_data.get('actual_quantity', order.quantity_ordered)
                quality_grade = serializer.validated_data.get('quality_grade', 'A')

                result = service.complete_production(actual_quantity, quality_grade)
                return StandardResponse.success(result, f"Виробництво {order.order_number} завершено")

            elif action_type == 'cancel':
                order.status = 'cancelled'
                order.save()
                return StandardResponse.success(None, f"Замовлення {order.order_number} скасовано")

            elif action_type == 'pause':
                order.status = 'on_hold'
                order.save()
                return StandardResponse.success(None, f"Замовлення {order.order_number} призупинено")

            else:
                return StandardResponse.error("Невідома дія")

        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=True, methods=['get'])
    def materials(self, request, pk=None):
        """Перевірка наявності матеріалів"""
        order = self.get_object()
        service = ProductionOrderService(order)

        validation_result = service.validate_materials_availability()
        return StandardResponse.success(validation_result, "Перевірка матеріалів виконана")


# ========== ЗВІТНІСТЬ ТА АНАЛІТИКА ==========

class ProductionDashboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Дешборд виробництва"""
        company_id = request.query_params.get('company')
        firm_id = request.query_params.get('firm')

        if not company_id:
            return StandardResponse.error("Потрібно вказати company")

        # Базовий фільтр
        orders_filter = {'company_id': company_id}
        if firm_id:
            orders_filter['firm_id'] = firm_id

        today = timezone.now().date()

        # Загальна статистика
        total_orders = ProductionOrder.objects.filter(**orders_filter).count()
        orders_in_progress = ProductionOrder.objects.filter(
            **orders_filter, status='in_progress'
        ).count()
        orders_completed_today = ProductionOrder.objects.filter(
            **orders_filter, status='completed', completed_at__date=today
        ).count()
        orders_overdue = ProductionOrder.objects.filter(
            **orders_filter,
            status__in=['planned', 'released', 'in_progress'],
            due_date__lt=timezone.now()
        ).count()

        # Ефективність
        completed_orders = ProductionOrder.objects.filter(
            **orders_filter, status='completed'
        )

        if completed_orders.exists():
            total_planned = completed_orders.aggregate(Sum('quantity_ordered'))['quantity_ordered__sum'] or 0
            total_produced = completed_orders.aggregate(Sum('quantity_produced'))['quantity_produced__sum'] or 0
            overall_efficiency = (total_produced / total_planned * 100) if total_planned > 0 else 0
        else:
            overall_efficiency = 0
            total_planned = 0
            total_produced = 0

        # Статус виробничих ліній
        lines_filter = {'company_id': company_id}
        if firm_id:
            lines_filter['firm_id'] = firm_id

        production_lines = ProductionLine.objects.filter(**lines_filter)
        lines_status = []

        for line in production_lines:
            service = ProductionLineService(line)
            workload = service.get_current_workload()

            lines_status.append({
                'id': line.id,
                'name': line.name,
                'is_active': line.is_active,
                'maintenance_mode': line.maintenance_mode,
                'workload_percentage': workload['workload_percentage'],
                'orders_count': workload['orders_count']
            })

        # Топ продукції
        top_products = []
        product_stats = ProductionOrder.objects.filter(
            **orders_filter, status='completed'
        ).values(
            'recipe__product__name'
        ).annotate(
            total_produced=Sum('quantity_produced'),
            orders_count=Count('id')
        ).order_by('-total_produced')[:5]

        for stat in product_stats:
            top_products.append({
                'product_name': stat['recipe__product__name'],
                'total_produced': float(stat['total_produced']),
                'orders_count': stat['orders_count']
            })

        dashboard_data = {
            'total_orders': total_orders,
            'orders_in_progress': orders_in_progress,
            'orders_completed_today': orders_completed_today,
            'orders_overdue': orders_overdue,
            'overall_efficiency': round(overall_efficiency, 2),
            'planned_vs_actual': {
                'planned': float(total_planned),
                'actual': float(total_produced)
            },
            'production_lines_status': lines_status,
            'top_products': top_products
        }

        return StandardResponse.success(dashboard_data, "Дешборд виробництва")


class ProductionReportsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Звіти виробництва"""
        report_type = request.query_params.get('type', 'efficiency')
        company_id = request.query_params.get('company')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if not company_id:
            return StandardResponse.error("Потрібно вказати company")

        if not date_from or not date_to:
            # За замовчуванням - поточний місяць
            today = timezone.now().date()
            date_from = today.replace(day=1)
            date_to = today
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

        try:
            if report_type == 'efficiency':
                from backend.models import Company
                company = Company.objects.get(id=company_id)
                report_data = ProductionReportService.get_production_efficiency_report(
                    company, date_from, date_to
                )
                return StandardResponse.success(report_data, "Звіт ефективності")

            else:
                return StandardResponse.error("Невідомий тип звіту")

        except Exception as e:
            return StandardResponse.error(str(e))



class MaterialsRequirementView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Потреби у матеріалах для запланованого виробництва"""
        company_id = request.query_params.get('company')
        firm_id = request.query_params.get('firm')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if not company_id:
            return StandardResponse.error("Потрібно вказати company")

        # Фільтр замовлень
        orders_filter = {
            'company_id': company_id,
            'status__in': ['planned', 'released']
        }

        if firm_id:
            orders_filter['firm_id'] = firm_id

        if date_from and date_to:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                orders_filter['due_date__date__range'] = [date_from, date_to]
            except ValueError:
                return StandardResponse.error("Невірний формат дати (YYYY-MM-DD)")

        # Отримуємо замовлення
        orders = ProductionOrder.objects.filter(**orders_filter)

        if not orders.exists():
            return StandardResponse.success([], "Немає запланованих замовлень")

        # Агрегуємо потреби у матеріалах
        materials_requirements = {}

        for order in orders:
            try:
                # ✅ ВИКОРИСТОВУЄМО ВАШУ КАЛЬКУЛЯЦІЮ
                from backend.services.tech_calc import TechCalculationService

                calc_service = TechCalculationService(
                    product_id=order.recipe.product.id,
                    mode='output',
                    weight=order.quantity_ordered,
                    warehouse=order.source_warehouse,
                    firm=order.firm
                )

                result = calc_service.calculate()

                # Додаємо до загальних потреб
                for ingredient in result['total_per_ingredient']:
                    product_id = ingredient['product_id']
                    required_qty = float(ingredient['total_required_quantity'])

                    if product_id not in materials_requirements:
                        from backend.models import Product
                        product = Product.objects.get(id=product_id)

                        # Отримуємо поточний залишок
                        from backend.operations.stock import FIFOStockManager
                        available_stock = FIFOStockManager.get_available_stock(
                            product, order.source_warehouse, order.firm
                        )

                        materials_requirements[product_id] = {
                            'product_id': product_id,
                            'product_name': product.name,
                            'unit': product.unit.symbol or product.unit.name,
                            'required_quantity': 0,
                            'available_quantity': float(available_stock),
                            'shortage': 0
                        }

                    materials_requirements[product_id]['required_quantity'] += required_qty

            except Exception as e:
                # Логуємо помилку але продовжуємо
                print(f"Помилка розрахунку для замовлення {order.order_number}: {e}")
                continue

        # Розраховуємо нестачу
        requirements_list = []
        for req in materials_requirements.values():
            shortage = max(0, req['required_quantity'] - req['available_quantity'])
            req['shortage'] = shortage
            requirements_list.append(req)

        # Сортуємо по нестачі (спочатку найбільша нестача)
        requirements_list.sort(key=lambda x: x['shortage'], reverse=True)

        return StandardResponse.success({
            'orders_count': orders.count(),
            'materials_requirements': requirements_list,
            'total_materials': len(requirements_list),
            'materials_with_shortage': len([r for r in requirements_list if r['shortage'] > 0])
        }, "Потреби у матеріалах розраховані")


class ProductionCalendarView(APIView):
    """Календар виробництва"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        firm_id = request.query_params.get('firm')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if not company_id:
            return StandardResponse.error("Потрібно вказати company")

        # За замовчуванням - поточний тиждень
        if not date_from or not date_to:
            today = timezone.now().date()
            date_from = today - timedelta(days=today.weekday())  # Понеділок
            date_to = date_from + timedelta(days=6)  # Неділя
        else:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                return StandardResponse.error("Невірний формат дати")

        # Фільтр замовлень
        orders_filter = {
            'company_id': company_id,
            'due_date__date__range': [date_from, date_to]
        }

        if firm_id:
            orders_filter['firm_id'] = firm_id

        orders = ProductionOrder.objects.filter(**orders_filter).select_related(
            'recipe__product', 'production_line'
        ).order_by('due_date')

        # Групуємо по датах
        calendar_data = {}
        current_date = date_from

        while current_date <= date_to:
            calendar_data[current_date.isoformat()] = {
                'date': current_date.isoformat(),
                'weekday': current_date.strftime('%A'),
                'orders': []
            }
            current_date += timedelta(days=1)

        # Розподіляємо замовлення по датах
        for order in orders:
            date_key = order.due_date.date().isoformat()
            if date_key in calendar_data:
                calendar_data[date_key]['orders'].append({
                    'id': order.id,
                    'order_number': order.order_number,
                    'product_name': order.recipe.product.name,
                    'quantity_ordered': float(order.quantity_ordered),
                    'quantity_produced': float(order.quantity_produced),
                    'status': order.status,
                    'priority': order.priority,
                    'production_line': order.production_line.name,
                    'completion_percentage': order.get_completion_percentage(),
                    'is_overdue': order.is_overdue()
                })

        return StandardResponse.success({
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'calendar': list(calendar_data.values())
        }, "Календар виробництва")


# ========== ШВИДКІ ДІЇ ==========

class QuickActionsView(APIView):
    """Швидкі дії для виробництва"""
    permission_classes = [AllowAny]

    def post(self, request):
        action_type = request.data.get('action')

        if action_type == 'create_urgent_order':
            return self._create_urgent_order(request)
        elif action_type == 'emergency_stop':
            return self._emergency_stop(request)
        elif action_type == 'quick_material_check':
            return self._quick_material_check(request)
        else:
            return StandardResponse.error("Невідома швидка дія")

    def _create_urgent_order(self, request):
        """Створення термінового замовлення"""
        try:
            data = request.data

            # Автоматично встановлюємо терміновий пріоритет
            data['priority'] = 'urgent'
            data['status'] = 'released'

            # Термін виконання - сьогодні + 2 години
            if not data.get('due_date'):
                data['due_date'] = timezone.now() + timedelta(hours=2)

            serializer = ProductionOrderCreateSerializer(
                data=data,
                context={'request': request}
            )

            if serializer.is_valid():
                order = serializer.save()
                return StandardResponse.created({
                    'order_number': order.order_number,
                    'id': order.id
                }, "Термінове замовлення створено")
            else:
                return StandardResponse.error("Помилка валідації", details=serializer.errors)

        except Exception as e:
            return StandardResponse.error(str(e))

    def _emergency_stop(self, request):
        """Екстрене зупинення виробництва"""
        production_line_id = request.data.get('production_line_id')
        reason = request.data.get('reason', 'Екстрене зупинення')

        if not production_line_id:
            return StandardResponse.error("Потрібно вказати production_line_id")

        try:
            # Зупиняємо всі активні замовлення на лінії
            orders = ProductionOrder.objects.filter(
                production_line_id=production_line_id,
                status='in_progress'
            )

            stopped_orders = []
            for order in orders:
                order.status = 'on_hold'
                order.notes = f"{order.notes}\n\nЕКСТРЕНЕ ЗУПИНЕННЯ: {reason}"
                order.save()
                stopped_orders.append(order.order_number)

            # Переводимо лінію в режим обслуговування
            line = ProductionLine.objects.get(id=production_line_id)
            line.maintenance_mode = True
            line.save()

            return StandardResponse.success({
                'stopped_orders': stopped_orders,
                'orders_count': len(stopped_orders)
            }, f"Екстрене зупинення лінії {line.name}")

        except Exception as e:
            return StandardResponse.error(str(e))

    def _quick_material_check(self, request):
        """Швидка перевірка матеріалів"""
        product_ids = request.data.get('product_ids', [])
        warehouse_id = request.data.get('warehouse_id')
        firm_id = request.data.get('firm_id')

        if not product_ids or not warehouse_id or not firm_id:
            return StandardResponse.error("Потрібно вказати product_ids, warehouse_id, firm_id")

        try:
            from backend.models import Product, Warehouse, Firm
            from backend.operations.stock import FIFOStockManager

            warehouse = Warehouse.objects.get(id=warehouse_id)
            firm = Firm.objects.get(id=firm_id)

            results = []
            for product_id in product_ids:
                product = Product.objects.get(id=product_id)
                stock = FIFOStockManager.get_available_stock(product, warehouse, firm)

                results.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'available_stock': float(stock),
                    'unit': product.unit.symbol or product.unit.name,
                    'status': 'available' if stock > 0 else 'out_of_stock'
                })

            return StandardResponse.success({
                'materials': results,
                'check_time': timezone.now().isoformat()
            }, "Швидка перевірка матеріалів")

        except Exception as e:
            return StandardResponse.error(str(e))


# production/views_extended.py - НОВІ API ДЛЯ РОЗШИРЕНОГО ФУНКЦІОНАЛУ

from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from .models import (
    MaintenanceSchedule, MaintenanceType, QualityCheck, QualityCheckPoint,
    WasteRecord, WasteType, WorkTimeNorm
)
from .services_extended import (
    MaintenanceService, QualityControlService, WasteManagementService,
    WorkTimeNormService, ProductionAnalyticsService
)
from backend.utils.responses import StandardResponse


class MaintenanceViewSet(ModelViewSet):
    """API для управління технічним обслуговуванням"""
    queryset = MaintenanceSchedule.objects.all()
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Фільтри
        company_id = self.request.query_params.get('company')
        production_line_id = self.request.query_params.get('production_line')
        status_filter = self.request.query_params.get('status')

        if company_id:
            queryset = queryset.filter(production_line__company_id=company_id)

        if production_line_id:
            queryset = queryset.filter(production_line_id=production_line_id)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('scheduled_date')

    def list(self, request):
        """Список планових ТО"""
        queryset = self.get_queryset()

        # Додаткові фільтри
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if date_from and date_to:
            queryset = queryset.filter(scheduled_date__range=[date_from, date_to])

        data = []
        for schedule in queryset:
            data.append({
                'id': schedule.id,
                'production_line': {
                    'id': schedule.production_line.id,
                    'name': schedule.production_line.name
                },
                'maintenance_type': {
                    'id': schedule.maintenance_type.id,
                    'name': schedule.maintenance_type.name
                },
                'scheduled_date': schedule.scheduled_date,
                'estimated_duration': schedule.estimated_duration,
                'status': schedule.status,
                'is_overdue': schedule.is_overdue(),
                'assigned_to': schedule.assigned_to.username if schedule.assigned_to else None,
                'actual_duration': schedule.get_actual_duration(),
                'actual_cost': schedule.actual_cost
            })

        return StandardResponse.success(data, "Список планового ТО")

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Прострочені ТО"""
        company_id = request.query_params.get('company')

        service = MaintenanceService()
        overdue_maintenance = service.get_overdue_maintenance(company_id)

        data = [{
            'id': item.id,
            'production_line': item.production_line.name,
            'maintenance_type': item.maintenance_type.name,
            'scheduled_date': item.scheduled_date,
            'days_overdue': (timezone.now() - item.scheduled_date).days
        } for item in overdue_maintenance]

        return StandardResponse.success(data, f"Знайдено {len(data)} прострочених ТО")

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Найближчі ТО"""
        company_id = request.query_params.get('company')
        days_ahead = int(request.query_params.get('days', 7))

        service = MaintenanceService()
        upcoming_maintenance = service.get_upcoming_maintenance(days_ahead, company_id)

        data = [{
            'id': item.id,
            'production_line': item.production_line.name,
            'maintenance_type': item.maintenance_type.name,
            'scheduled_date': item.scheduled_date,
            'days_until': (item.scheduled_date - timezone.now()).days,
            'assigned_to': item.assigned_to.username if item.assigned_to else None
        } for item in upcoming_maintenance]

        return StandardResponse.success(data, f"Найближчі ТО ({days_ahead} днів)")

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Початок виконання ТО"""
        service = MaintenanceService()

        try:
            schedule = service.start_maintenance(pk, request.user)
            return StandardResponse.success({
                'id': schedule.id,
                'status': schedule.status,
                'actual_start': schedule.actual_start
            }, "ТО розпочато")
        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Завершення ТО"""
        service = MaintenanceService()

        data = request.data
        actual_cost = data.get('actual_cost', 0)
        completion_notes = data.get('completion_notes', '')

        try:
            schedule = service.complete_maintenance(
                pk, actual_cost, completion_notes, request.user
            )
            return StandardResponse.success({
                'id': schedule.id,
                'status': schedule.status,
                'actual_end': schedule.actual_end,
                'next_maintenance_date': schedule.next_maintenance_date,
                'actual_duration': schedule.get_actual_duration()
            }, "ТО завершено")
        except Exception as e:
            return StandardResponse.error(str(e))


class QualityControlViewSet(ModelViewSet):
    """API для контролю якості"""
    queryset = QualityCheck.objects.all()
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        production_order_id = self.request.query_params.get('production_order')
        production_line_id = self.request.query_params.get('production_line')
        status_filter = self.request.query_params.get('status')

        if production_order_id:
            queryset = queryset.filter(production_order_id=production_order_id)

        if production_line_id:
            queryset = queryset.filter(production_order__production_line_id=production_line_id)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-check_date')

    def list(self, request):
        """Список контролів якості"""
        queryset = self.get_queryset()

        data = []
        for check in queryset:
            data.append({
                'id': check.id,
                'production_order': {
                    'id': check.production_order.id,
                    'order_number': check.production_order.order_number,
                    'product': check.production_order.recipe.product.name
                },
                'checkpoint': {
                    'id': check.checkpoint.id,
                    'name': check.checkpoint.name,
                    'check_type': check.checkpoint.check_type
                },
                'check_date': check.check_date,
                'checked_quantity': check.checked_quantity,
                'passed_quantity': check.passed_quantity,
                'failed_quantity': check.failed_quantity,
                'defect_rate': check.get_defect_rate(),
                'status': check.status,
                'inspector': check.inspector.username if check.inspector else None,
                'measured_value': check.measured_value,
                'deviation_percent': check.deviation_percent
            })

        return StandardResponse.success(data, "Список контролів якості")

    @action(detail=False, methods=['post'])
    def perform_check(self, request):
        """Виконання контролю якості"""
        data = request.data

        service = QualityControlService()
        service.production_order_id = data.get('production_order')

        try:
            quality_check = service.perform_quality_check(
                checkpoint_id=data.get('checkpoint'),
                checked_quantity=data.get('checked_quantity'),
                passed_quantity=data.get('passed_quantity'),
                measured_value=data.get('measured_value'),
                inspector=request.user,
                notes=data.get('notes', '')
            )

            return StandardResponse.success({
                'id': quality_check.id,
                'status': quality_check.status,
                'defect_rate': quality_check.get_defect_rate(),
                'deviation_percent': quality_check.deviation_percent
            }, "Контроль якості виконано")

        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Зведення по якості"""
        production_line_id = request.query_params.get('production_line')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        service = QualityControlService()

        # Конвертуємо дати
        if date_from:
            date_from = timezone.datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        if date_to:
            date_to = timezone.datetime.fromisoformat(date_to.replace('Z', '+00:00'))

        production_line = None
        if production_line_id:
            from .models import ProductionLine
            production_line = ProductionLine.objects.get(id=production_line_id)

        summary = service.get_quality_summary(production_line, date_from, date_to)

        return StandardResponse.success(summary, "Зведення по якості")


class WasteManagementViewSet(ModelViewSet):
    """API для управління браком та відходами"""
    queryset = WasteRecord.objects.all()
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        production_order_id = self.request.query_params.get('production_order')
        production_line_id = self.request.query_params.get('production_line')
        waste_type = self.request.query_params.get('waste_type')
        cause_category = self.request.query_params.get('cause_category')

        if production_order_id:
            queryset = queryset.filter(production_order_id=production_order_id)

        if production_line_id:
            queryset = queryset.filter(production_order__production_line_id=production_line_id)

        if waste_type:
            queryset = queryset.filter(waste_type__category=waste_type)

        if cause_category:
            queryset = queryset.filter(cause_category=cause_category)

        return queryset.order_by('-occurred_at')

    def list(self, request):
        """Список записів про брак/відходи"""
        queryset = self.get_queryset()

        data = []
        for record in queryset:
            data.append({
                'id': record.id,
                'production_order': {
                    'id': record.production_order.id,
                    'order_number': record.production_order.order_number,
                    'product': record.production_order.recipe.product.name
                },
                'waste_type': {
                    'id': record.waste_type.id,
                    'name': record.waste_type.name,
                    'category': record.waste_type.category
                },
                'quantity': record.quantity,
                'unit': record.unit.name,
                'unit_cost': record.unit_cost,
                'total_loss': record.total_loss,
                'occurred_at': record.occurred_at,
                'cause_category': record.cause_category,
                'cause_description': record.cause_description,
                'is_recovered': record.is_recovered,
                'recovery_cost': record.recovery_cost,
                'reported_by': record.reported_by.username if record.reported_by else None
            })

        return StandardResponse.success(data, "Список браку та відходів")

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Реєстрація браку/відходів"""
        data = request.data

        service = WasteManagementService()

        try:
            from .models import ProductionOrder, WasteType, WorkCenter

            production_order = ProductionOrder.objects.get(id=data.get('production_order'))
            waste_type = WasteType.objects.get(id=data.get('waste_type'))
            work_center = None

            if data.get('work_center'):
                work_center = WorkCenter.objects.get(id=data.get('work_center'))

            waste_record = service.register_waste(
                production_order=production_order,
                waste_type=waste_type,
                quantity=data.get('quantity'),
                unit_cost=data.get('unit_cost'),
                cause_category=data.get('cause_category'),
                cause_description=data.get('cause_description'),
                work_center=work_center,
                reported_by=request.user
            )

            return StandardResponse.success({
                'id': waste_record.id,
                'total_loss': waste_record.total_loss
            }, "Брак/відходи зареєстровано")

        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=True, methods=['post'])
    def attempt_recovery(self, request, pk=None):
        """Спроба відновлення браку"""
        data = request.data
        service = WasteManagementService()

        try:
            result = service.attempt_recovery(
                waste_record_id=pk,
                recovery_cost=data.get('recovery_cost'),
                action_taken=data.get('action_taken'),
                user=request.user
            )

            return StandardResponse.success(result, "Спроба відновлення зареєстрована")

        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Аналітика по браку та відходам"""
        company_id = request.query_params.get('company')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        service = WasteManagementService()

        # Конвертуємо дати
        if date_from:
            date_from = timezone.datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        if date_to:
            date_to = timezone.datetime.fromisoformat(date_to.replace('Z', '+00:00'))

        company = None
        if company_id:
            from backend.models import Company
            company = Company.objects.get(id=company_id)

        analytics = service.get_waste_analytics(company, date_from, date_to)

        return StandardResponse.success(analytics, "Аналітика браку та відходів")


class WorkTimeNormViewSet(ModelViewSet):
    """API для управління нормами робочого часу"""
    queryset = WorkTimeNorm.objects.all()
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        production_line_id = self.request.query_params.get('production_line')
        product_id = self.request.query_params.get('product')
        is_active = self.request.query_params.get('is_active')

        if production_line_id:
            queryset = queryset.filter(production_line_id=production_line_id)

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-valid_from')

    def list(self, request):
        """Список норм робочого часу"""
        queryset = self.get_queryset()

        data = []
        for norm in queryset:
            # Розрахунок для прикладу (100 одиниць)
            sample_calc = norm.calculate_production_time(100)

            data.append({
                'id': norm.id,
                'production_line': {
                    'id': norm.production_line.id,
                    'name': norm.production_line.name
                },
                'product': {
                    'id': norm.product.id,
                    'name': norm.product.name
                },
                'setup_time_minutes': norm.setup_time_minutes,
                'cycle_time_seconds': norm.cycle_time_seconds,
                'cleanup_time_minutes': norm.cleanup_time_minutes,
                'efficiency_factor': norm.efficiency_factor,
                'quality_factor': norm.quality_factor,
                'is_active': norm.is_active,
                'valid_from': norm.valid_from,
                'valid_to': norm.valid_to,
                'sample_calculation': sample_calc
            })

        return StandardResponse.success(data, "Список норм робочого часу")

    @action(detail=False, methods=['post'])
    def create_norm(self, request):
        """Створення норми робочого часу"""
        data = request.data
        service = WorkTimeNormService()

        try:
            from .models import ProductionLine
            from backend.models import Product

            production_line = ProductionLine.objects.get(id=data.get('production_line'))
            product = Product.objects.get(id=data.get('product'))

            time_norm = service.create_time_norm(
                production_line=production_line,
                product=product,
                setup_time=data.get('setup_time_minutes'),
                cycle_time=data.get('cycle_time_seconds'),
                cleanup_time=data.get('cleanup_time_minutes'),
                efficiency_factor=data.get('efficiency_factor', 0.85),
                quality_factor=data.get('quality_factor', 0.95)
            )

            return StandardResponse.success({
                'id': time_norm.id,
                'production_line': time_norm.production_line.name,
                'product': time_norm.product.name
            }, "Норма робочого часу створена")

        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=False, methods=['post'])
    def calculate_schedule(self, request):
        """Розрахунок графіку виробництва"""
        data = request.data
        order_ids = data.get('order_ids', [])

        service = WorkTimeNormService()

        try:
            from .models import ProductionOrder
            orders = ProductionOrder.objects.filter(id__in=order_ids)

            schedule = service.calculate_production_schedule(orders)

            return StandardResponse.success(schedule, "Графік виробництва розраховано")

        except Exception as e:
            return StandardResponse.error(str(e))


class ProductionAnalyticsViewSet:
    """API для аналітики виробництва"""

    @action(detail=False, methods=['get'])
    def comprehensive_report(self, request):
        """Комплексний звіт по виробництву"""
        company_id = request.query_params.get('company')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if not all([company_id, date_from, date_to]):
            return StandardResponse.error("Потрібно вказати company, date_from та date_to")

        try:
            from backend.models import Company
            company = Company.objects.get(id=company_id)

            # Конвертуємо дати
            date_from = timezone.datetime.fromisoformat(date_from.replace('Z', '+00:00')).date()
            date_to = timezone.datetime.fromisoformat(date_to.replace('Z', '+00:00')).date()

            report = ProductionAnalyticsService.get_comprehensive_report(
                company, date_from, date_to
            )

            return StandardResponse.success(report, "Комплексний звіт сформовано")

        except Exception as e:
            return StandardResponse.error(str(e))

    @action(detail=False, methods=['get'])
    def line_efficiency(self, request):
        """Ефективність виробничих ліній"""
        company_id = request.query_params.get('company')
        days = int(request.query_params.get('days', 30))

        try:
            from .models import ProductionLine

            queryset = ProductionLine.objects.filter(company_id=company_id, is_active=True)

            data = []
            for line in queryset:
                data.append({
                    'id': line.id,
                    'name': line.name,
                    'current_efficiency': line.get_current_efficiency(),
                    'quality_rate': line.get_quality_rate(days),
                    'availability_rate': line.get_availability_rate(days),
                    'oee': line.get_oee(days),
                    'capacity_per_hour': line.capacity_per_hour,
                    'maintenance_mode': line.maintenance_mode
                })

            return StandardResponse.success(data, "Ефективність виробничих ліній")

        except Exception as e:
            return StandardResponse.error(str(e))


