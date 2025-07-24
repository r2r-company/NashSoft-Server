# production/services.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, Q

from backend.models import Operation, Document, DocumentItem
from backend.operations.stock import FIFOStockManager
from backend.services.logger import AuditLoggerService
from backend.services.tech_calc import TechCalculationService

from .models import (
    ProductionOrder, ProductionPlan, ProductionPlanItem,
    ProductionLine, WorkCenter, ProductionWorker
)


class ProductionPlanService:
    """Сервіс для роботи з планами виробництва"""

    def __init__(self, production_plan):
        self.plan = production_plan
        self.logger = AuditLoggerService(document=None)

    def approve_plan(self, user):
        """Затвердити план виробництва"""
        try:
            with transaction.atomic():
                if self.plan.status != 'draft':
                    raise ValidationError("Можна затверджувати тільки чернетки")

                # Перевірка чи всі позиції мають призначені лінії
                items_without_lines = self.plan.items.filter(production_line__isnull=True)
                if items_without_lines.exists():
                    raise ValidationError("Всі позиції плану повинні мати призначені виробничі лінії")

                # Перевірка на конфлікти ресурсів
                self._validate_resource_conflicts()

                # Розрахунок планової собівартості для всіх позицій
                for item in self.plan.items.all():
                    item.calculate_estimated_cost()

                # Затвердження
                self.plan.approve(user)

                self.logger.log_event(
                    "production_plan_approved",
                    f"План виробництва {self.plan.name} затверджено"
                )

                return True

        except Exception as e:
            self.logger.log_error("production_plan_approval_failed", e)
            raise

    def _validate_resource_conflicts(self):
        """Перевірка конфліктів ресурсів"""
        # Групуємо позиції по лініях та часу
        conflicts = []

        for item in self.plan.items.all():
            overlapping_items = self.plan.items.filter(
                production_line=item.production_line
            ).exclude(id=item.id).filter(
                Q(planned_start_date__lte=item.planned_end_date) &
                Q(planned_end_date__gte=item.planned_start_date)
            )

            if overlapping_items.exists():
                conflicts.append(f"Конфлікт ресурсів на лінії {item.production_line.name}")

        if conflicts:
            raise ValidationError("; ".join(conflicts))

    def create_production_orders(self):
        """Створити виробничі замовлення на основі плану"""
        if self.plan.status != 'approved':
            raise ValidationError("План повинен бути затверджений")

        orders = []

        with transaction.atomic():
            for item in self.plan.items.all():
                order = ProductionOrder.objects.create(
                    company=self.plan.company,
                    firm=self.plan.firm,
                    production_plan=self.plan,
                    recipe=item.recipe,
                    quantity_ordered=item.planned_quantity,
                    due_date=item.planned_end_date,
                    production_line=item.production_line,
                    source_warehouse=self.plan.firm.warehouse_set.first(),
                    target_warehouse=self.plan.firm.warehouse_set.first(),
                    planned_cost=item.estimated_cost,
                    status='planned'
                )
                orders.append(order)

                self.logger.log_event(
                    "production_order_created_from_plan",
                    f"Створено замовлення {order.order_number} з плану {self.plan.name}"
                )

        return orders


class ProductionOrderService:
    """Сервіс для роботи з виробничими замовленнями"""

    def __init__(self, production_order, request=None):
        self.order = production_order
        if request:
            self.logger = AuditLoggerService.create_from_request(request)
        else:
            self.logger = AuditLoggerService()

    def validate_materials_availability(self):
        """Перевірка наявності сировини"""
        # ✅ ІНТЕГРАЦІЯ З ВАШОЮ КАЛЬКУЛЯЦІЄЮ
        try:
            calc_service = TechCalculationService(
                product_id=self.order.recipe.product.id,
                mode='output',
                weight=self.order.quantity_ordered,
                warehouse=self.order.source_warehouse,
                firm=self.order.firm
            )

            result = calc_service.calculate()
            missing_materials = []

            # Перевіряємо кожен інгредієнт
            for ingredient in result['total_per_ingredient']:
                product_id = ingredient['product_id']
                required_qty = Decimal(str(ingredient['total_required_quantity']))

                from backend.models import Product
                product = Product.objects.get(id=product_id)

                available_stock = FIFOStockManager.get_available_stock(
                    product, self.order.source_warehouse, self.order.firm
                )

                if available_stock < required_qty:
                    missing_materials.append({
                        'product': product.name,
                        'required': float(required_qty),
                        'available': float(available_stock),
                        'shortage': float(required_qty - available_stock)
                    })

            return {
                'materials_available': len(missing_materials) == 0,
                'missing_materials': missing_materials,
                'total_cost': result['total_cost']
            }

        except Exception as e:
            self.logger.log_error("materials_validation_failed", e)
            return {
                'materials_available': False,
                'error': str(e)
            }

    def start_production(self, user):
        """Запустити виробництво"""
        try:
            with transaction.atomic():
                # Перевірка статусу
                if self.order.status not in ['planned', 'released']:
                    raise ValidationError("Неможливо запустити виробництво з поточним статусом")

                # Перевірка наявності матеріалів
                validation_result = self.validate_materials_availability()
                if not validation_result['materials_available']:
                    missing = validation_result.get('missing_materials', [])
                    missing_names = [m['product'] for m in missing]
                    raise ValidationError(f"Недостатньо сировини: {', '.join(missing_names)}")

                # Резервування матеріалів (створення документа списання)
                materials_document = self._reserve_materials()

                # Запуск виробництва
                self.order.start_production(user)

                self.logger.log_event(
                    "production_started",
                    f"Запущено виробництво {self.order.order_number}"
                )

                return {
                    'success': True,
                    'materials_document': materials_document.doc_number if materials_document else None
                }

        except Exception as e:
            self.logger.log_error("production_start_failed", e)
            raise

    def _reserve_materials(self):
        """Резервування матеріалів (списання сировини)"""
        try:
            # Створюємо документ списання сировини
            from backend.models import Document, DocumentItem
            from backend.utils.doc_number import generate_document_number

            document = Document.objects.create(
                doc_type='production_order',  # Новий тип документа
                company=self.order.company,
                firm=self.order.firm,
                warehouse=self.order.source_warehouse,
                doc_number=generate_document_number('production_order', self.order.company),
                status='draft'
            )

            # ✅ ВИКОРИСТОВУЄМО ВАШУ КАЛЬКУЛЯЦІЮ ДЛЯ СТВОРЕННЯ ПОЗИЦІЙ
            calc_service = TechCalculationService(
                product_id=self.order.recipe.product.id,
                mode='output',
                weight=self.order.quantity_ordered,
                warehouse=self.order.source_warehouse,
                firm=self.order.firm
            )

            result = calc_service.calculate()

            # Створюємо позиції документа
            for ingredient in result['total_per_ingredient']:
                from backend.models import Product
                product = Product.objects.get(id=ingredient['product_id'])

                DocumentItem.objects.create(
                    document=document,
                    product=product,
                    quantity=Decimal(str(ingredient['total_required_quantity'])),
                    unit=product.unit,
                    price=Decimal(str(ingredient['avg_price'])),
                    vat_percent=0  # Внутрішнє списання без ПДВ
                )

            # Проводимо документ через існуючий сервіс
            from backend.services.factory import get_document_service
            service = get_document_service(document)
            service.post()

            self.logger.log_event(
                "materials_reserved",
                f"Списано сировину документом {document.doc_number}"
            )

            return document

        except Exception as e:
            self.logger.log_error("materials_reservation_failed", e)
            raise

    def complete_production(self, actual_quantity, quality_grade='A'):
        """Завершити виробництво"""
        try:
            with transaction.atomic():
                if self.order.status != 'in_progress':
                    raise ValidationError("Неможливо завершити виробництво з поточним статусом")

                # Оприбуткування готової продукції
                finished_goods_document = self._receive_finished_goods(actual_quantity, quality_grade)

                # Розрахунок фактичної собівартості
                self._calculate_actual_cost(actual_quantity)

                # Завершення замовлення
                self.order.complete_production(actual_quantity)

                self.logger.log_event(
                    "production_completed",
                    f"Завершено виробництво {self.order.order_number}, "
                    f"вироблено {actual_quantity} од."
                )

                return {
                    'success': True,
                    'finished_goods_document': finished_goods_document.doc_number,
                    'actual_cost': float(self.order.actual_cost),
                    'efficiency': self._calculate_efficiency()
                }

        except Exception as e:
            self.logger.log_error("production_completion_failed", e)
            raise

    def _receive_finished_goods(self, quantity, quality_grade):
        """Оприбуткування готової продукції"""
        from backend.models import Document, DocumentItem
        from backend.utils.doc_number import generate_document_number

        document = Document.objects.create(
            doc_type='production',  # Тип документа виробництва
            company=self.order.company,
            firm=self.order.firm,
            warehouse=self.order.target_warehouse,
            doc_number=generate_document_number('production', self.order.company),
            status='draft'
        )

        # Створюємо позицію готової продукції
        DocumentItem.objects.create(
            document=document,
            product=self.order.recipe.product,
            quantity=quantity,
            unit=self.order.recipe.product.unit,
            price=self.order.planned_cost / self.order.quantity_ordered,  # Собівартість
            vat_percent=0  # Внутрішнє оприбуткування
        )

        # Проводимо документ
        from backend.services.factory import get_document_service
        service = get_document_service(document)
        service.post()

        return document

    def _calculate_actual_cost(self, actual_quantity):
        """Розрахунок фактичної собівартості"""
        # Тут можна додати логіку розрахунку фактичних витрат
        # Поки що використовуємо планову собівартість пропорційно
        if self.order.quantity_ordered > 0:
            cost_per_unit = self.order.planned_cost / self.order.quantity_ordered
            self.order.actual_cost = cost_per_unit * actual_quantity
            self.order.save(update_fields=['actual_cost'])

    def _calculate_efficiency(self):
        """Розрахунок ефективності виробництва"""
        if self.order.quantity_ordered == 0:
            return 0

        return (self.order.quantity_produced / self.order.quantity_ordered) * 100


class ProductionLineService:
    """Сервіс для роботи з виробничими лініями"""

    def __init__(self, production_line):
        self.line = production_line
        self.logger = AuditLoggerService()

    def get_current_workload(self, date_from=None, date_to=None):
        """Поточне завантаження лінії"""
        if not date_from:
            date_from = timezone.now().date()
        if not date_to:
            date_to = date_from

        orders = ProductionOrder.objects.filter(
            production_line=self.line,
            status__in=['planned', 'released', 'in_progress'],
            due_date__date__range=[date_from, date_to]
        )

        total_planned_hours = 0
        for order in orders:
            # Розрахунок планової тривалості на основі кількості та потужності лінії
            if self.line.capacity_per_hour > 0:
                hours_needed = float(order.quantity_ordered) / float(self.line.capacity_per_hour)
                total_planned_hours += hours_needed

        # Припускаємо 8-годинний робочий день
        available_hours = 8.0
        workload_percentage = min(100, (total_planned_hours / available_hours) * 100)

        return {
            'planned_hours': total_planned_hours,
            'available_hours': available_hours,
            'workload_percentage': workload_percentage,
            'orders_count': orders.count(),
            'is_overloaded': total_planned_hours > available_hours
        }

    def schedule_maintenance(self, start_time, duration_hours, description):
        """Планування технічного обслуговування"""
        # TODO: Реалізувати систему планування ТО
        self.line.maintenance_mode = True
        self.line.save()

        self.logger.log_event(
            "maintenance_scheduled",
            f"Заплановано ТО для лінії {self.line.name}"
        )


class ProductionReportService:
    """Сервіс звітності по виробництву"""

    @staticmethod
    def get_production_efficiency_report(company, date_from, date_to):
        """Звіт ефективності виробництва"""
        orders = ProductionOrder.objects.filter(
            company=company,
            status='completed',
            completed_at__date__range=[date_from, date_to]
        )

        total_orders = orders.count()
        total_planned = orders.aggregate(Sum('quantity_ordered'))['quantity_ordered__sum'] or 0
        total_produced = orders.aggregate(Sum('quantity_produced'))['quantity_produced__sum'] or 0

        efficiency = (total_produced / total_planned * 100) if total_planned > 0 else 0

        # Групування по лініях
        lines_data = {}
        for order in orders:
            line_name = order.production_line.name
            if line_name not in lines_data:
                lines_data[line_name] = {
                    'orders_count': 0,
                    'planned_quantity': 0,
                    'produced_quantity': 0,
                    'efficiency': 0
                }

            lines_data[line_name]['orders_count'] += 1
            lines_data[line_name]['planned_quantity'] += float(order.quantity_ordered)
            lines_data[line_name]['produced_quantity'] += float(order.quantity_produced)

        # Розрахунок ефективності по лініях
        for line_name, data in lines_data.items():
            if data['planned_quantity'] > 0:
                data['efficiency'] = (data['produced_quantity'] / data['planned_quantity']) * 100

        return {
            'period': {'from': date_from, 'to': date_to},
            'summary': {
                'total_orders': total_orders,
                'total_planned': float(total_planned),
                'total_produced': float(total_produced),
                'overall_efficiency': float(efficiency)
            },
            'by_production_lines': lines_data
        }