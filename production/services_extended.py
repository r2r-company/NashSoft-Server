# production/services_extended.py - НОВІ СЕРВІСИ ДЛЯ ПОВНОГО ФУНКЦІОНАЛУ

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from datetime import datetime, timedelta
from django.core.mail import send_mail

from .models import (
    MaintenanceSchedule, MaintenanceType, QualityCheck, QualityCheckPoint,
    WasteRecord, WasteType, WorkTimeNorm, ProductionLine, ProductionOrder
)
from backend.services.logger import AuditLoggerService


class MaintenanceService:
    """Сервіс управління технічним обслуговуванням"""

    def __init__(self, production_line=None):
        self.production_line = production_line
        self.logger = AuditLoggerService()

    def create_maintenance_schedule(self, maintenance_type, scheduled_date, assigned_to=None):
        """Створення планового ТО"""
        try:
            with transaction.atomic():
                schedule = MaintenanceSchedule.objects.create(
                    production_line=self.production_line,
                    maintenance_type=maintenance_type,
                    scheduled_date=scheduled_date,
                    estimated_duration=maintenance_type.duration_hours,
                    assigned_to=assigned_to
                )

                # Блокуємо лінію на час ТО
                if scheduled_date <= timezone.now() + timedelta(hours=24):
                    self.production_line.maintenance_mode = True
                    self.production_line.save()

                self.logger.log_event(
                    "maintenance_scheduled",
                    f"Заплановано {maintenance_type.name} для {self.production_line.name} на {scheduled_date}"
                )

                # Відправляємо нагадування
                self._send_maintenance_notification(schedule)

                return schedule

        except Exception as e:
            self.logger.log_error("maintenance_schedule_creation_failed", e)
            raise

    def start_maintenance(self, schedule_id, user):
        """Початок виконання ТО"""
        try:
            schedule = MaintenanceSchedule.objects.get(id=schedule_id)

            if schedule.status != 'scheduled':
                raise ValidationError("ТО має статус відмінний від 'заплановано'")

            with transaction.atomic():
                schedule.status = 'in_progress'
                schedule.actual_start = timezone.now()
                schedule.save()

                # Блокуємо лінію
                schedule.production_line.maintenance_mode = True
                schedule.production_line.save()

                self.logger.log_event(
                    "maintenance_started",
                    f"Розпочато ТО {schedule.maintenance_type.name} на лінії {schedule.production_line.name}",
                    user=user
                )

                return schedule

        except Exception as e:
            self.logger.log_error("maintenance_start_failed", e)
            raise

    def complete_maintenance(self, schedule_id, actual_cost, completion_notes, user):
        """Завершення ТО"""
        try:
            schedule = MaintenanceSchedule.objects.get(id=schedule_id)

            if schedule.status != 'in_progress':
                raise ValidationError("ТО не знаходиться в процесі виконання")

            with transaction.atomic():
                schedule.status = 'completed'
                schedule.actual_end = timezone.now()
                schedule.actual_cost = actual_cost
                schedule.completion_notes = completion_notes

                # Розраховуємо наступне ТО
                schedule.next_maintenance_date = self._calculate_next_maintenance(
                    schedule.maintenance_type, schedule.actual_end
                )
                schedule.save()

                # Розблокуємо лінію
                schedule.production_line.maintenance_mode = False
                schedule.production_line.save()

                # Автоматично плануємо наступне ТО
                self._auto_schedule_next_maintenance(schedule)

                self.logger.log_event(
                    "maintenance_completed",
                    f"Завершено ТО {schedule.maintenance_type.name} на лінії {schedule.production_line.name}",
                    user=user
                )

                return schedule

        except Exception as e:
            self.logger.log_error("maintenance_completion_failed", e)
            raise

    def get_overdue_maintenance(self, company=None):
        """Отримання прострочених ТО"""
        queryset = MaintenanceSchedule.objects.filter(
            status='scheduled',
            scheduled_date__lt=timezone.now()
        )

        if company:
            queryset = queryset.filter(production_line__company=company)

        # Позначаємо як прострочені
        queryset.update(status='overdue')

        return queryset

    def get_upcoming_maintenance(self, days_ahead=7, company=None):
        """ТО найближчими днями"""
        end_date = timezone.now() + timedelta(days=days_ahead)

        queryset = MaintenanceSchedule.objects.filter(
            status='scheduled',
            scheduled_date__range=[timezone.now(), end_date]
        )

        if company:
            queryset = queryset.filter(production_line__company=company)

        return queryset.order_by('scheduled_date')

    def _calculate_next_maintenance(self, maintenance_type, last_date):
        """Розрахунок дати наступного ТО"""
        if maintenance_type.frequency_type == 'days':
            return last_date + timedelta(days=maintenance_type.frequency_value)
        elif maintenance_type.frequency_type == 'hours':
            # Припускаємо 8 годин роботи на день
            days = maintenance_type.frequency_value / 8
            return last_date + timedelta(days=days)
        elif maintenance_type.frequency_type == 'cycles':
            # TODO: реалізувати облік циклів роботи
            return last_date + timedelta(days=30)
        else:
            return last_date + timedelta(days=30)

    def _auto_schedule_next_maintenance(self, completed_schedule):
        """Автоматичне планування наступного ТО"""
        if completed_schedule.next_maintenance_date:
            MaintenanceSchedule.objects.create(
                production_line=completed_schedule.production_line,
                maintenance_type=completed_schedule.maintenance_type,
                scheduled_date=completed_schedule.next_maintenance_date,
                estimated_duration=completed_schedule.maintenance_type.duration_hours
            )

    def _send_maintenance_notification(self, schedule):
        """Відправка нагадування про ТО"""
        if schedule.assigned_to and schedule.assigned_to.email:
            try:
                send_mail(
                    subject=f"Планове ТО: {schedule.maintenance_type.name}",
                    message=f"""
                    Заплановано технічне обслуговування:

                    Лінія: {schedule.production_line.name}
                    Тип ТО: {schedule.maintenance_type.name}
                    Дата: {schedule.scheduled_date.strftime('%d.%m.%Y %H:%M')}
                    Тривалість: {schedule.estimated_duration} год

                    Підготуйтеся до виконання робіт.
                    """,
                    from_email='noreply@nashsoft.com',
                    recipient_list=[schedule.assigned_to.email]
                )
            except Exception as e:
                self.logger.log_error("maintenance_notification_failed", e)


class QualityControlService:
    """Сервіс контролю якості"""

    def __init__(self, production_order=None):
        self.production_order = production_order
        self.logger = AuditLoggerService()

    def perform_quality_check(self, checkpoint_id, checked_quantity, passed_quantity,
                              measured_value=None, inspector=None, notes=""):
        """Виконання контролю якості"""
        try:
            checkpoint = QualityCheckPoint.objects.get(id=checkpoint_id)
            failed_quantity = checked_quantity - passed_quantity

            # Розрахунок відхилення
            deviation = 0
            if measured_value and checkpoint.check_type == 'measurement':
                # TODO: додати еталонне значення для порівняння
                deviation = abs(float(measured_value) - 100) / 100 * 100  # заглушка

            # Визначення статусу
            defect_rate = (failed_quantity / checked_quantity * 100) if checked_quantity > 0 else 0

            if defect_rate == 0:
                status = 'pass'
            elif defect_rate <= checkpoint.acceptable_deviation:
                status = 'conditional'
            else:
                status = 'fail'

            with transaction.atomic():
                quality_check = QualityCheck.objects.create(
                    production_order=self.production_order,
                    checkpoint=checkpoint,
                    checked_quantity=checked_quantity,
                    passed_quantity=passed_quantity,
                    failed_quantity=failed_quantity,
                    measured_value=measured_value,
                    deviation_percent=deviation,
                    status=status,
                    inspector=inspector,
                    notes=notes
                )

                # Якщо брак перевищує норму - створюємо запис про брак
                if status == 'fail' and failed_quantity > 0:
                    self._create_waste_record(failed_quantity, checkpoint, quality_check)

                self.logger.log_event(
                    "quality_check_performed",
                    f"Контроль якості: {checkpoint.name}, статус: {status}",
                    user=inspector
                )

                return quality_check

        except Exception as e:
            self.logger.log_error("quality_check_failed", e)
            raise

    def get_quality_summary(self, production_line=None, date_from=None, date_to=None):
        """Зведення по якості"""
        queryset = QualityCheck.objects.all()

        if production_line:
            queryset = queryset.filter(production_order__production_line=production_line)

        if date_from and date_to:
            queryset = queryset.filter(check_date__range=[date_from, date_to])

        summary = queryset.aggregate(
            total_checks=Count('id'),
            total_checked=Sum('checked_quantity'),
            total_passed=Sum('passed_quantity'),
            total_failed=Sum('failed_quantity'),
            avg_deviation=Avg('deviation_percent')
        )

        # Расчеты показателей
        total_checked = summary['total_checked'] or 0
        total_passed = summary['total_passed'] or 0
        total_failed = summary['total_failed'] or 0

        pass_rate = (total_passed / total_checked * 100) if total_checked > 0 else 100
        defect_rate = (total_failed / total_checked * 100) if total_checked > 0 else 0

        return {
            **summary,
            'pass_rate': round(pass_rate, 2),
            'defect_rate': round(defect_rate, 2)
        }

    def _create_waste_record(self, failed_quantity, checkpoint, quality_check):
        """Створення запису про брак"""
        try:
            # Знаходимо або створюємо тип браку
            waste_type, created = WasteType.objects.get_or_create(
                name=f"Брак по {checkpoint.name}",
                defaults={
                    'category': 'defect',
                    'description': f"Автоматично створено при контролі {checkpoint.name}"
                }
            )

            # Розрахунок вартості браку
            unit_cost = self.production_order.planned_cost / self.production_order.quantity_ordered
            total_loss = unit_cost * failed_quantity

            WasteRecord.objects.create(
                production_order=self.production_order,
                waste_type=waste_type,
                quantity=failed_quantity,
                unit=self.production_order.recipe.product.unit,
                unit_cost=unit_cost,
                total_loss=total_loss,
                work_center=checkpoint.production_line.work_centers.first(),
                cause_category='process',
                cause_description=f"Не пройшов контроль якості: {checkpoint.name}",
                reported_by=quality_check.inspector
            )

        except Exception as e:
            self.logger.log_error("waste_record_creation_failed", e)


class WasteManagementService:
    """Сервіс управління браком та відходами"""

    def __init__(self):
        self.logger = AuditLoggerService()

    def register_waste(self, production_order, waste_type, quantity, unit_cost,
                       cause_category, cause_description, work_center=None, reported_by=None):
        """Реєстрація браку/відходів"""
        try:
            total_loss = quantity * unit_cost

            with transaction.atomic():
                waste_record = WasteRecord.objects.create(
                    production_order=production_order,
                    waste_type=waste_type,
                    quantity=quantity,
                    unit=production_order.recipe.product.unit,
                    unit_cost=unit_cost,
                    total_loss=total_loss,
                    work_center=work_center,
                    cause_category=cause_category,
                    cause_description=cause_description,
                    reported_by=reported_by
                )

                self.logger.log_event(
                    "waste_registered",
                    f"Зареєстровано {waste_type.category}: {quantity} {production_order.recipe.product.unit.name}",
                    user=reported_by
                )

                return waste_record

        except Exception as e:
            self.logger.log_error("waste_registration_failed", e)
            raise

    def attempt_recovery(self, waste_record_id, recovery_cost, action_taken, user):
        """Спроба відновлення браку"""
        try:
            waste_record = WasteRecord.objects.get(id=waste_record_id)

            if not waste_record.waste_type.is_recoverable:
                raise ValidationError("Цей тип браку не підлягає відновленню")

            with transaction.atomic():
                waste_record.is_recovered = True
                waste_record.recovery_cost = recovery_cost
                waste_record.action_taken = action_taken
                waste_record.save()

                # Розрахунок економії
                potential_loss = waste_record.total_loss
                actual_loss = recovery_cost
                savings = potential_loss - actual_loss

                self.logger.log_event(
                    "waste_recovered",
                    f"Відновлено брак: економія {savings:.2f} грн",
                    user=user
                )

                return {
                    'success': True,
                    'potential_loss': potential_loss,
                    'actual_loss': actual_loss,
                    'savings': savings
                }

        except Exception as e:
            self.logger.log_error("waste_recovery_failed", e)
            raise

    def get_waste_analytics(self, company=None, date_from=None, date_to=None):
        """Аналітика по браку та відходам"""
        queryset = WasteRecord.objects.all()

        if company:
            queryset = queryset.filter(production_order__company=company)

        if date_from and date_to:
            queryset = queryset.filter(occurred_at__range=[date_from, date_to])

        # Загальна статистика
        total_stats = queryset.aggregate(
            total_records=Count('id'),
            total_quantity=Sum('quantity'),
            total_loss=Sum('total_loss'),
            total_recovery_cost=Sum('recovery_cost'),
            recovered_count=Count('id', filter=Q(is_recovered=True))
        )

        # По типах браку
        by_type = queryset.values(
            'waste_type__name', 'waste_type__category'
        ).annotate(
            count=Count('id'),
            total_quantity=Sum('quantity'),
            total_loss=Sum('total_loss')
        ).order_by('-total_loss')

        # По причинах
        by_cause = queryset.values(
            'cause_category'
        ).annotate(
            count=Count('id'),
            total_loss=Sum('total_loss')
        ).order_by('-total_loss')

        # По лініях
        by_line = queryset.values(
            'production_order__production_line__name'
        ).annotate(
            count=Count('id'),
            total_loss=Sum('total_loss')
        ).order_by('-total_loss')

        return {
            'total_stats': total_stats,
            'by_type': list(by_type),
            'by_cause': list(by_cause),
            'by_line': list(by_line)
        }


class WorkTimeNormService:
    """Сервіс управління нормами робочого часу"""

    def __init__(self):
        self.logger = AuditLoggerService()

    def create_time_norm(self, production_line, product, setup_time, cycle_time,
                         cleanup_time, efficiency_factor=0.85, quality_factor=0.95):
        """Створення норми робочого часу"""
        try:
            # Деактивуємо старі норми
            WorkTimeNorm.objects.filter(
                production_line=production_line,
                product=product,
                is_active=True
            ).update(is_active=False, valid_to=timezone.now())

            # Створюємо нову норму
            time_norm = WorkTimeNorm.objects.create(
                production_line=production_line,
                product=product,
                setup_time_minutes=setup_time,
                cycle_time_seconds=cycle_time,
                cleanup_time_minutes=cleanup_time,
                efficiency_factor=efficiency_factor,
                quality_factor=quality_factor
            )

            self.logger.log_event(
                "time_norm_created",
                f"Створено норму часу: {production_line.name} - {product.name}"
            )

            return time_norm

        except Exception as e:
            self.logger.log_error("time_norm_creation_failed", e)
            raise

    def calculate_production_schedule(self, production_orders):
        """Розрахунок графіку виробництва на основі норм"""
        schedule = []

        for order in production_orders:
            try:
                # Знаходимо норму часу
                time_norm = WorkTimeNorm.objects.filter(
                    production_line=order.production_line,
                    product=order.recipe.product,
                    is_active=True
                ).first()

                if time_norm:
                    time_calc = time_norm.calculate_production_time(order.quantity_ordered)

                    schedule.append({
                        'order': order,
                        'time_calculation': time_calc,
                        'can_schedule': True
                    })
                else:
                    # Фолбек розрахунок
                    hours = 8  # Стандартна зміна
                    if order.production_line.capacity_per_hour > 0:
                        hours = float(order.quantity_ordered) / float(order.production_line.capacity_per_hour)

                    schedule.append({
                        'order': order,
                        'time_calculation': {'total_hours': hours},
                        'can_schedule': False,
                        'warning': 'Норма часу не встановлена'
                    })

            except Exception as e:
                schedule.append({
                    'order': order,
                    'error': str(e),
                    'can_schedule': False
                })

        return schedule

    def optimize_production_sequence(self, orders, production_line):
        """Оптимізація послідовності виробництва"""
        # Групуємо замовлення по продуктах для мінімізації переналагоджень
        grouped_orders = {}

        for order in orders:
            product_id = order.recipe.product.id
            if product_id not in grouped_orders:
                grouped_orders[product_id] = []
            grouped_orders[product_id].append(order)

        # Сортуємо групи по загальному часу налаштування
        optimized_sequence = []

        for product_id, product_orders in grouped_orders.items():
            # Сортуємо замовлення в групі по об'єму (великі спочатку)
            product_orders.sort(key=lambda x: x.quantity_ordered, reverse=True)
            optimized_sequence.extend(product_orders)

        return optimized_sequence


class ProductionAnalyticsService:
    """Сервіс аналітики виробництва"""

    @staticmethod
    def get_comprehensive_report(company, date_from, date_to):
        """Комплексний звіт по виробництву"""

        # Базові дані
        production_lines = ProductionLine.objects.filter(company=company)
        completed_orders = ProductionOrder.objects.filter(
            company=company,
            status='completed',
            completed_at__range=[date_from, date_to]
        )

        report = {
            'period': {'from': date_from, 'to': date_to},
            'summary': {},
            'lines': [],
            'quality': {},
            'waste': {},
            'maintenance': {}
        }

        # Загальна статистика
        total_orders = completed_orders.count()
        total_quantity = completed_orders.aggregate(Sum('quantity_produced'))['quantity_produced__sum'] or 0
        total_planned_hours = completed_orders.aggregate(Sum('planned_duration_hours'))[
                                  'planned_duration_hours__sum'] or 0

        report['summary'] = {
            'total_orders': total_orders,
            'total_quantity': total_quantity,
            'total_planned_hours': total_planned_hours,
            'avg_efficiency': 0
        }

        # По лініях
        total_efficiency = 0
        active_lines = 0

        for line in production_lines:
            line_orders = completed_orders.filter(production_line=line)

            if line_orders.exists():
                line_efficiency = line.get_current_efficiency()
                line_quality = line.get_quality_rate((date_to - date_from).days)
                line_oee = line.get_oee((date_to - date_from).days)

                total_efficiency += line_efficiency
                active_lines += 1

                report['lines'].append({
                    'name': line.name,
                    'orders_count': line_orders.count(),
                    'total_quantity': line_orders.aggregate(Sum('quantity_produced'))['quantity_produced__sum'] or 0,
                    'efficiency': line_efficiency,
                    'quality_rate': line_quality,
                    'oee': line_oee
                })

        if active_lines > 0:
            report['summary']['avg_efficiency'] = round(total_efficiency / active_lines, 1)

        # Контроль якості
        quality_service = QualityControlService()
        report['quality'] = quality_service.get_quality_summary(
            date_from=date_from,
            date_to=date_to
        )

        # Брак и відходи
        waste_service = WasteManagementService()
        report['waste'] = waste_service.get_waste_analytics(
            company=company,
            date_from=date_from,
            date_to=date_to
        )

        # ТО
        maintenance_stats = MaintenanceSchedule.objects.filter(
            production_line__company=company,
            scheduled_date__range=[date_from, date_to]
        ).aggregate(
            total_scheduled=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            overdue=Count('id', filter=Q(status='overdue')),
            total_cost=Sum('actual_cost')
        )

        report['maintenance'] = maintenance_stats

        return report