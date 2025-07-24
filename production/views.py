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