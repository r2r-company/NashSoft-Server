# production/models.py - ЧАСТИНА 1: БАЗОВІ МОДЕЛІ
from django.db import models
from django.contrib.auth import get_user_model
from backend.models import Company, Firm, Warehouse, Product, Unit

User = get_user_model()


# ========== ВИРОБНИЧА ІНФРАСТРУКТУРА ==========

class ProductionLine(models.Model):
    """Виробнича лінія / цех"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")

    name = models.CharField("Назва лінії", max_length=255)
    code = models.CharField("Код", max_length=50, unique=True)
    description = models.TextField("Опис", blank=True, null=True)

    # Технічні характеристики
    capacity_per_hour = models.DecimalField(
        "Потужність (од/год)",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Скільки одиниць продукції може виробити за годину"
    )

    # Статус
    is_active = models.BooleanField("Активна", default=True)
    maintenance_mode = models.BooleanField("Технічне обслуговування", default=False)

    # Розташування
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        verbose_name="Склад",
        help_text="Склад де знаходиться лінія"
    )

    created_at = models.DateTimeField("Створено", auto_now_add=True)
    updated_at = models.DateTimeField("Оновлено", auto_now=True)

    class Meta:
        verbose_name = "Виробнича лінія"
        verbose_name_plural = "Виробничі лінії"
        unique_together = ('company', 'code')

    def __str__(self):
        return f"{self.name} [{self.code}]"

    def get_current_efficiency(self):
        """Поточна ефективність лінії (%)"""
        # TODO: розрахунок на основі факт/план
        return 85.0


class WorkCenter(models.Model):
    """Робочий центр / робоче місце"""
    production_line = models.ForeignKey(
        ProductionLine,
        on_delete=models.CASCADE,
        related_name='work_centers',
        verbose_name="Виробнича лінія"
    )

    name = models.CharField("Назва центру", max_length=255)
    code = models.CharField("Код", max_length=50)

    # Тип роботи
    WORK_TYPE_CHOICES = [
        ('preparation', 'Підготовка'),
        ('processing', 'Обробка'),
        ('assembly', 'Збірка'),
        ('packaging', 'Пакування'),
        ('quality_control', 'Контроль якості'),
        ('storage', 'Зберігання'),
    ]
    work_type = models.CharField(
        "Тип роботи",
        max_length=20,
        choices=WORK_TYPE_CHOICES
    )

    # Технічні параметри
    setup_time_minutes = models.IntegerField(
        "Час налаштування (хв)",
        default=0,
        help_text="Час підготовки робочого місця"
    )

    capacity_per_hour = models.DecimalField(
        "Потужність (од/год)",
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Вартість
    cost_per_hour = models.DecimalField(
        "Вартість роботи (грн/год)",
        max_digits=10,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField("Активний", default=True)

    class Meta:
        verbose_name = "Робочий центр"
        verbose_name_plural = "Робочі центри"
        unique_together = ('production_line', 'code')

    def __str__(self):
        return f"{self.production_line.name} → {self.name}"


class Equipment(models.Model):
    """Обладнання"""
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.CASCADE,
        related_name='equipment',
        verbose_name="Робочий центр"
    )

    name = models.CharField("Назва обладнання", max_length=255)
    model = models.CharField("Модель", max_length=100, blank=True)
    serial_number = models.CharField("Серійний номер", max_length=100, blank=True)

    # Статус
    STATUS_CHOICES = [
        ('operational', 'Працює'),
        ('maintenance', 'Обслуговування'),
        ('broken', 'Несправне'),
        ('idle', 'Простоює'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='operational')

    # Технічні характеристики
    power_consumption = models.DecimalField(
        "Споживання енергії (кВт/год)",
        max_digits=8,
        decimal_places=2,
        default=0
    )

    purchase_date = models.DateField("Дата придбання", null=True, blank=True)
    purchase_price = models.DecimalField(
        "Вартість придбання",
        max_digits=12,
        decimal_places=2,
        default=0
    )

    # Планове обслуговування
    maintenance_interval_hours = models.IntegerField(
        "Інтервал ТО (години)",
        default=0,
        help_text="Через скільки годин роботи потрібне технічне обслуговування"
    )

    last_maintenance = models.DateTimeField("Останнє ТО", null=True, blank=True)
    next_maintenance = models.DateTimeField("Наступне ТО", null=True, blank=True)

    class Meta:
        verbose_name = "Обладнання"
        verbose_name_plural = "Обладнання"

    def __str__(self):
        return f"{self.name} ({self.model})"

    def needs_maintenance(self):
        """Чи потрібне технічне обслуговування"""
        if not self.next_maintenance:
            return False
        from django.utils import timezone
        return timezone.now() >= self.next_maintenance


# ========== ПРАЦІВНИКИ ТА ЗМІНИ ==========

class WorkerPosition(models.Model):
    """Посада працівника"""
    name = models.CharField("Назва посади", max_length=100)
    description = models.TextField("Опис обов'язків", blank=True)
    hourly_rate = models.DecimalField(
        "Погодинна ставка (грн)",
        max_digits=8,
        decimal_places=2,
        default=0
    )

    class Meta:
        verbose_name = "Посада працівника"
        verbose_name_plural = "Посади працівників"

    def __str__(self):
        return self.name


class ProductionWorker(models.Model):
    """Виробничий працівник"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='production_worker',
        verbose_name="Користувач"
    )

    employee_id = models.CharField("Табельний номер", max_length=50, unique=True)
    position = models.ForeignKey(
        WorkerPosition,
        on_delete=models.CASCADE,
        verbose_name="Посада"
    )

    # Кваліфікація
    skill_level = models.IntegerField(
        "Рівень кваліфікації",
        choices=[(i, f"Рівень {i}") for i in range(1, 6)],
        default=1
    )

    # Робочі центри де може працювати
    work_centers = models.ManyToManyField(
        WorkCenter,
        verbose_name="Робочі центри",
        help_text="На яких робочих місцях може працювати"
    )

    hire_date = models.DateField("Дата прийняття на роботу")
    is_active = models.BooleanField("Активний", default=True)

    class Meta:
        verbose_name = "Виробничий працівник"
        verbose_name_plural = "Виробничі працівники"

    def __str__(self):
        return f"{self.user.get_full_name()} [{self.employee_id}]"


class WorkShift(models.Model):
    """Робоча зміна"""
    name = models.CharField("Назва зміни", max_length=100)
    start_time = models.TimeField("Час початку")
    end_time = models.TimeField("Час закінчення")

    # Дні тижня (1=Понеділок, 7=Неділя)
    work_days = models.JSONField(
        "Робочі дні",
        default=list,
        help_text="Список днів тижня: [1,2,3,4,5] для пн-пт"
    )

    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Робоча зміна"
        verbose_name_plural = "Робочі зміни"

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"

    def get_duration_hours(self):
        """Тривалість зміни в годинах"""
        from datetime import datetime, timedelta

        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)

        # Якщо зміна через опівночі
        if end < start:
            end += timedelta(days=1)

        return (end - start).total_seconds() / 3600


# production/models.py - ЧАСТИНА 2: ДОКУМЕНТИ ВИРОБНИЦТВА
# ДОДАЙТЕ ЦЕ В КІНЕЦЬ ФАЙЛУ models.py

from django.utils import timezone
from django.core.exceptions import ValidationError


# ========== ПЛАНУВАННЯ ВИРОБНИЦТВА ==========

class ProductionPlan(models.Model):
    """План виробництва на період"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")

    # Період планування
    plan_date_from = models.DateField("Дата початку")
    plan_date_to = models.DateField("Дата закінчення")

    # Метадані
    name = models.CharField("Назва плану", max_length=255)
    description = models.TextField("Опис", blank=True)

    # Статус
    STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('approved', 'Затверджено'),
        ('in_progress', 'Виконується'),
        ('completed', 'Завершено'),
        ('cancelled', 'Скасовано'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='draft')

    # Хто створив та затвердив
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_production_plans',
        verbose_name="Створив"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_production_plans',
        verbose_name="Затвердив"
    )
    approved_at = models.DateTimeField("Затверджено", null=True, blank=True)

    created_at = models.DateTimeField("Створено", auto_now_add=True)
    updated_at = models.DateTimeField("Оновлено", auto_now=True)

    class Meta:
        verbose_name = "План виробництва"
        verbose_name_plural = "Плани виробництва"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.plan_date_from} - {self.plan_date_to})"

    def approve(self, user):
        """Затвердити план"""
        if self.status != 'draft':
            raise ValidationError("Можна затверджувати тільки чернетки")

        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()

    def get_total_planned_quantity(self):
        """Загальна кількість до виробництва"""
        return self.items.aggregate(
            total=models.Sum('planned_quantity')
        )['total'] or 0


class ProductionPlanItem(models.Model):
    """Позиція плану виробництва"""
    production_plan = models.ForeignKey(
        ProductionPlan,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="План виробництва"
    )

    # ✅ ІНТЕГРАЦІЯ З ВАШИМИ КАЛЬКУЛЯЦІЯМИ:
    recipe = models.ForeignKey(
        'backend.ProductCalculation',  # ← Ваша технологічна карта!
        on_delete=models.CASCADE,
        verbose_name="Рецепт/технологічна карта"
    )

    # Планування
    planned_quantity = models.DecimalField(
        "Планована кількість",
        max_digits=10,
        decimal_places=3
    )
    planned_start_date = models.DateTimeField("Планований початок")
    planned_end_date = models.DateTimeField("Планове закінчення")

    # Призначення ресурсів
    production_line = models.ForeignKey(
        ProductionLine,
        on_delete=models.CASCADE,
        verbose_name="Виробнича лінія"
    )

    # Пріоритет
    priority = models.IntegerField(
        "Пріоритет",
        choices=[(i, f"Пріоритет {i}") for i in range(1, 6)],
        default=3,
        help_text="1 - найвищий, 5 - найнижчий"
    )

    # Розрахункові поля
    estimated_cost = models.DecimalField(
        "Планова собівартість",
        max_digits=12,
        decimal_places=2,
        default=0
    )
    estimated_duration_hours = models.DecimalField(
        "Планова тривалість (год)",
        max_digits=6,
        decimal_places=2,
        default=0
    )

    # Примітки
    notes = models.TextField("Примітки", blank=True)

    created_at = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        verbose_name = "Позиція плану виробництва"
        verbose_name_plural = "Позиції планів виробництва"
        unique_together = ('production_plan', 'recipe', 'production_line')

    def __str__(self):
        return f"{self.recipe.product.name} x {self.planned_quantity}"

    def calculate_estimated_cost(self):
        """Розрахунок планової собівартості через вашу калькуляцію"""
        from backend.services.tech_calc import TechCalculationService

        try:
            # ✅ ВИКОРИСТОВУЄМО ВАШ СЕРВІС!
            calc_service = TechCalculationService(
                product_id=self.recipe.product.id,
                mode='output',
                weight=self.planned_quantity
            )
            result = calc_service.calculate()

            self.estimated_cost = Decimal(str(result['total_cost']))
            self.save(update_fields=['estimated_cost'])

            return self.estimated_cost

        except Exception as e:
            print(f"Помилка розрахунку собівартості: {e}")
            return Decimal('0')


# ========== ВИРОБНИЧІ ЗАМОВЛЕННЯ ==========

class ProductionOrder(models.Model):
    """Виробниче замовлення"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")

    # Номер замовлення
    order_number = models.CharField("Номер замовлення", max_length=50, unique=True)

    # Звʼязок з планом (опціонально)
    production_plan = models.ForeignKey(
        ProductionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="План виробництва"
    )

    # ✅ ІНТЕГРАЦІЯ З ВАШИМИ КАЛЬКУЛЯЦІЯМИ:
    recipe = models.ForeignKey(
        'backend.ProductCalculation',
        on_delete=models.CASCADE,
        verbose_name="Рецепт/технологічна карта"
    )

    # Основні параметри
    quantity_ordered = models.DecimalField(
        "Замовлена кількість",
        max_digits=10,
        decimal_places=3
    )
    quantity_produced = models.DecimalField(
        "Вироблено",
        max_digits=10,
        decimal_places=3,
        default=0
    )

    # Терміни
    order_date = models.DateTimeField("Дата замовлення", default=timezone.now)
    due_date = models.DateTimeField("Термін виконання")
    started_at = models.DateTimeField("Початок виробництва", null=True, blank=True)
    completed_at = models.DateTimeField("Завершено", null=True, blank=True)

    # Ресурси
    production_line = models.ForeignKey(
        ProductionLine,
        on_delete=models.CASCADE,
        verbose_name="Виробнича лінія"
    )

    # Статус
    STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('planned', 'Заплановано'),
        ('released', 'Запущено'),
        ('in_progress', 'Виконується'),
        ('completed', 'Завершено'),
        ('cancelled', 'Скасовано'),
        ('on_hold', 'Призупинено'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='draft')

    # Пріоритет
    PRIORITY_CHOICES = [
        ('low', 'Низький'),
        ('normal', 'Звичайний'),
        ('high', 'Високий'),
        ('urgent', 'Терміновий'),
    ]
    priority = models.CharField("Пріоритет", max_length=10, choices=PRIORITY_CHOICES, default='normal')

    # Відповідальні
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_production_orders',
        verbose_name="Створив"
    )
    assigned_to = models.ForeignKey(
        ProductionWorker,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Призначено"
    )

    # Склад для сировини та готової продукції
    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='production_orders_source',
        verbose_name="Склад сировини"
    )
    target_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='production_orders_target',
        verbose_name="Склад готової продукції"
    )

    # Фінансова інформація
    planned_cost = models.DecimalField(
        "Планова собівартість",
        max_digits=12,
        decimal_places=2,
        default=0
    )
    actual_cost = models.DecimalField(
        "Фактична собівартість",
        max_digits=12,
        decimal_places=2,
        default=0
    )

    # Примітки
    notes = models.TextField("Примітки", blank=True)

    created_at = models.DateTimeField("Створено", auto_now_add=True)
    updated_at = models.DateTimeField("Оновлено", auto_now=True)

    class Meta:
        verbose_name = "Виробниче замовлення"
        verbose_name_plural = "Виробничі замовлення"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.recipe.product.name} x {self.quantity_ordered}"

    def save(self, *args, **kwargs):
        # Автогенерація номеру замовлення
        if not self.order_number:
            last_order = ProductionOrder.objects.filter(
                company=self.company
            ).order_by('-id').first()

            last_number = 0
            if last_order and last_order.order_number:
                try:
                    last_number = int(last_order.order_number.split('-')[-1])
                except:
                    pass

            self.order_number = f"PO-{str(last_number + 1).zfill(5)}"

        super().save(*args, **kwargs)

    def start_production(self, user):
        """Запустити виробництво"""
        if self.status not in ['planned', 'released']:
            raise ValidationError("Можна запускати тільки заплановані замовлення")

        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()

    def complete_production(self, actual_quantity=None):
        """Завершити виробництво"""
        if self.status != 'in_progress':
            raise ValidationError("Можна завершувати тільки виробництво що виконується")

        if actual_quantity:
            self.quantity_produced = actual_quantity

        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def get_completion_percentage(self):
        """Відсоток виконання"""
        if self.quantity_ordered == 0:
            return 0
        return min(100, (self.quantity_produced / self.quantity_ordered) * 100)

    def is_overdue(self):
        """Чи прострочено"""
        if self.status in ['completed', 'cancelled']:
            return False
        return timezone.now() > self.due_date


# production/models.py - ДОДАТКОВІ МОДЕЛІ ДЛЯ ПОВНОГО ФУНКЦІОНАЛУ

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

User = get_user_model()


# ========== ПЛАНУВАННЯ ТО ТА РЕМОНТІВ ==========

class MaintenanceType(models.Model):
    """Типи технічного обслуговування"""
    name = models.CharField("Назва ТО", max_length=100)
    description = models.TextField("Опис", blank=True)

    # Періодичність
    frequency_type = models.CharField(
        "Тип періодичності",
        max_length=20,
        choices=[
            ('hours', 'По мотогодинах'),
            ('days', 'По днях'),
            ('cycles', 'По циклах роботи'),
            ('manual', 'Ручне планування')
        ],
        default='days'
    )
    frequency_value = models.IntegerField("Значення періодичності", default=30)

    # Тривалість ТО
    duration_hours = models.DecimalField("Тривалість (год)", max_digits=6, decimal_places=2, default=2)

    # Вартість
    estimated_cost = models.DecimalField("Планова вартість", max_digits=10, decimal_places=2, default=0)

    is_active = models.BooleanField("Активний", default=True)

    class Meta:
        verbose_name = "Тип ТО"
        verbose_name_plural = "Типи ТО"

    def __str__(self):
        return self.name


class MaintenanceSchedule(models.Model):
    """Графік планового ТО"""
    production_line = models.ForeignKey(
        'ProductionLine',
        on_delete=models.CASCADE,
        related_name='maintenance_schedules',
        verbose_name="Виробнича лінія"
    )
    maintenance_type = models.ForeignKey(
        MaintenanceType,
        on_delete=models.CASCADE,
        verbose_name="Тип ТО"
    )

    # Планування
    scheduled_date = models.DateTimeField("Планова дата")
    estimated_duration = models.DecimalField("Планова тривалість (год)", max_digits=6, decimal_places=2)

    # Статус
    STATUS_CHOICES = [
        ('scheduled', 'Заплановано'),
        ('in_progress', 'Виконується'),
        ('completed', 'Завершено'),
        ('cancelled', 'Скасовано'),
        ('overdue', 'Прострочено'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Виконання
    actual_start = models.DateTimeField("Фактичний початок", null=True, blank=True)
    actual_end = models.DateTimeField("Фактичне завершення", null=True, blank=True)
    actual_cost = models.DecimalField("Фактична вартість", max_digits=10, decimal_places=2, default=0)

    # Відповідальні
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Відповідальний"
    )

    # Результат
    completion_notes = models.TextField("Примітки по виконанню", blank=True)
    next_maintenance_date = models.DateTimeField("Наступне ТО", null=True, blank=True)

    created_at = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        verbose_name = "График ТО"
        verbose_name_plural = "Графіки ТО"
        ordering = ['scheduled_date']

    def __str__(self):
        return f"{self.production_line.name} - {self.maintenance_type.name} ({self.scheduled_date.date()})"

    def is_overdue(self):
        """Перевірка чи прострочено ТО"""
        if self.status in ['completed', 'cancelled']:
            return False
        return timezone.now() > self.scheduled_date

    def get_actual_duration(self):
        """Фактична тривалість ТО"""
        if self.actual_start and self.actual_end:
            delta = self.actual_end - self.actual_start
            return round(delta.total_seconds() / 3600, 2)  # в годинах
        return None


# ========== КОНТРОЛЬ ЯКОСТІ ==========

class QualityCheckPoint(models.Model):
    """Контрольні точки якості"""
    name = models.CharField("Назва контрольної точки", max_length=200)
    production_line = models.ForeignKey(
        'ProductionLine',
        on_delete=models.CASCADE,
        related_name='quality_checkpoints',
        verbose_name="Виробнича лінія"
    )

    # Тип перевірки
    check_type = models.CharField(
        "Тип перевірки",
        max_length=20,
        choices=[
            ('visual', 'Візуальний контроль'),
            ('measurement', 'Вимірювання'),
            ('testing', 'Тестування'),
            ('sampling', 'Вибіркова перевірка'),
        ],
        default='visual'
    )

    # Параметри
    check_frequency = models.CharField(
        "Частота перевірки",
        max_length=20,
        choices=[
            ('each', 'Кожна одиниця'),
            ('batch', 'Кожна партія'),
            ('hour', 'Кожну годину'),
            ('shift', 'Кожну зміну'),
        ],
        default='batch'
    )

    # Критерії
    criteria = models.TextField("Критерії якості")
    acceptable_deviation = models.DecimalField(
        "Допустиме відхилення (%)",
        max_digits=5,
        decimal_places=2,
        default=5
    )

    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Контрольна точка"
        verbose_name_plural = "Контрольні точки"

    def __str__(self):
        return f"{self.name} ({self.production_line.name})"


class QualityCheck(models.Model):
    """Результати контролю якості"""
    production_order = models.ForeignKey(
        'ProductionOrder',
        on_delete=models.CASCADE,
        related_name='quality_checks',
        verbose_name="Виробниче замовлення"
    )
    checkpoint = models.ForeignKey(
        QualityCheckPoint,
        on_delete=models.CASCADE,
        verbose_name="Контрольна точка"
    )

    # Результати
    check_date = models.DateTimeField("Дата перевірки", default=timezone.now)
    checked_quantity = models.DecimalField("Перевірено (шт)", max_digits=10, decimal_places=3)
    passed_quantity = models.DecimalField("Пройшло контроль", max_digits=10, decimal_places=3)
    failed_quantity = models.DecimalField("Не пройшло контроль", max_digits=10, decimal_places=3, default=0)

    # Деталі
    measured_value = models.DecimalField("Виміряне значення", max_digits=10, decimal_places=3, null=True, blank=True)
    deviation_percent = models.DecimalField("Відхилення (%)", max_digits=5, decimal_places=2, default=0)

    # Статус
    STATUS_CHOICES = [
        ('pass', 'Пройшов'),
        ('fail', 'Не пройшов'),
        ('conditional', 'Умовно пройшов'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='pass')

    # Відповідальний та примітки
    inspector = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Контролер"
    )
    notes = models.TextField("Примітки", blank=True)

    class Meta:
        verbose_name = "Контроль якості"
        verbose_name_plural = "Контроль якості"
        ordering = ['-check_date']

    def __str__(self):
        return f"{self.checkpoint.name} - {self.check_date.date()} ({self.status})"

    def get_defect_rate(self):
        """Відсоток браку"""
        if self.checked_quantity > 0:
            return round((self.failed_quantity / self.checked_quantity) * 100, 2)
        return 0


# ========== ОБЛІК БРАКУ ТА ВІДХОДІВ ==========

class WasteType(models.Model):
    """Типи браку та відходів"""
    name = models.CharField("Назва типу", max_length=100)
    category = models.CharField(
        "Категорія",
        max_length=20,
        choices=[
            ('defect', 'Брак'),
            ('waste', 'Відходи'),
            ('rework', 'На доробку'),
        ],
        default='defect'
    )

    # Фінансові показники
    is_recoverable = models.BooleanField("Можна відновити", default=False)
    recovery_cost_per_unit = models.DecimalField(
        "Вартість відновлення за од.",
        max_digits=10,
        decimal_places=2,
        default=0
    )

    description = models.TextField("Опис", blank=True)

    class Meta:
        verbose_name = "Тип браку/відходів"
        verbose_name_plural = "Типи браку та відходів"

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class WasteRecord(models.Model):
    """Облік браку та відходів"""
    production_order = models.ForeignKey(
        'ProductionOrder',
        on_delete=models.CASCADE,
        related_name='waste_records',
        verbose_name="Виробниче замовлення"
    )
    waste_type = models.ForeignKey(
        WasteType,
        on_delete=models.CASCADE,
        verbose_name="Тип браку/відходів"
    )

    # Кількісні показники
    quantity = models.DecimalField("Кількість", max_digits=10, decimal_places=3)
    unit = models.ForeignKey(
        'backend.Unit',
        on_delete=models.CASCADE,
        verbose_name="Одиниця виміру"
    )

    # Фінансові показники
    unit_cost = models.DecimalField("Собівартість за од.", max_digits=10, decimal_places=2)
    total_loss = models.DecimalField("Загальні втрати", max_digits=12, decimal_places=2)

    # Деталі
    occurred_at = models.DateTimeField("Час виявлення", default=timezone.now)
    work_center = models.ForeignKey(
        'WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Робочий центр"
    )

    # Причини
    cause_category = models.CharField(
        "Категорія причини",
        max_length=20,
        choices=[
            ('material', 'Сировина'),
            ('equipment', 'Обладнання'),
            ('process', 'Технологічний процес'),
            ('human', 'Людський фактор'),
            ('environment', 'Зовнішні фактори'),
        ],
        default='process'
    )
    cause_description = models.TextField("Опис причини")

    # Дії
    action_taken = models.TextField("Вжиті заходи", blank=True)
    is_recovered = models.BooleanField("Відновлено", default=False)
    recovery_cost = models.DecimalField("Вартість відновлення", max_digits=10, decimal_places=2, default=0)

    # Відповідальний
    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Хто повідомив"
    )

    class Meta:
        verbose_name = "Запис про брак/відходи"
        verbose_name_plural = "Облік браку та відходів"
        ordering = ['-occurred_at']

    def __str__(self):
        return f"{self.waste_type.name} - {self.quantity} {self.unit.name} ({self.occurred_at.date()})"


# ========== НОРМУВАННЯ РОБОЧОГО ЧАСУ ==========

class WorkTimeNorm(models.Model):
    """Норми робочого часу"""
    production_line = models.ForeignKey(
        'ProductionLine',
        on_delete=models.CASCADE,
        related_name='time_norms',
        verbose_name="Виробнича лінія"
    )
    product = models.ForeignKey(
        'backend.Product',
        on_delete=models.CASCADE,
        verbose_name="Продукт"
    )

    # Норми часу
    setup_time_minutes = models.DecimalField(
        "Час налаштування (хв)",
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Час на підготовку лінії для виробництва"
    )
    cycle_time_seconds = models.DecimalField(
        "Час циклу (сек)",
        max_digits=8,
        decimal_places=2,
        help_text="Час виробництва однієї одиниці"
    )
    cleanup_time_minutes = models.DecimalField(
        "Час прибирання (хв)",
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Час на прибирання після завершення"
    )

    # Коефіцієнти
    efficiency_factor = models.DecimalField(
        "Коефіцієнт ефективності",
        max_digits=4,
        decimal_places=3,
        default=0.85,
        help_text="Врахування втрат часу (0.85 = 85% ефективність)"
    )
    quality_factor = models.DecimalField(
        "Коефіцієнт якості",
        max_digits=4,
        decimal_places=3,
        default=0.95,
        help_text="Врахування браку (0.95 = 5% брак)"
    )

    # Метадані
    valid_from = models.DateTimeField("Діє з", default=timezone.now)
    valid_to = models.DateTimeField("Діє до", null=True, blank=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Норма робочого часу"
        verbose_name_plural = "Норми робочого часу"
        unique_together = ('production_line', 'product', 'valid_from')

    def __str__(self):
        return f"{self.production_line.name} - {self.product.name}"

    def calculate_production_time(self, quantity):
        """Розрахунок часу виробництва для заданої кількості"""
        # Час налаштування (разово)
        setup = float(self.setup_time_minutes)

        # Час виробництва
        production = (float(quantity) * float(self.cycle_time_seconds)) / 60  # в хвилинах

        # Час прибирання (разово)
        cleanup = float(self.cleanup_time_minutes)

        # Загальний час з коефіцієнтами
        total_minutes = (setup + production + cleanup) / float(self.efficiency_factor)

        return {
            'setup_minutes': setup,
            'production_minutes': production,
            'cleanup_minutes': cleanup,
            'total_minutes': round(total_minutes, 2),
            'total_hours': round(total_minutes / 60, 2)
        }


# ========== РОЗШИРЕННЯ ІСНУЮЧИХ МОДЕЛЕЙ ==========

# Додаємо методи до ProductionLine
class ProductionLineExtended:
    """Розширення для ProductionLine"""

    def get_current_efficiency(self):
        """РЕАЛЬНИЙ розрахунок ефективності лінії"""
        from django.db.models import Avg, Sum
        from datetime import datetime, timedelta

        # Аналізуємо останні 30 днів
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        # Отримуємо завершені замовлення
        completed_orders = self.production_orders.filter(
            status='completed',
            completed_at__range=[start_date, end_date]
        )

        if not completed_orders.exists():
            return 0.0

        total_efficiency = 0
        count = 0

        for order in completed_orders:
            # Розрахунок ефективності для кожного замовлення
            planned_time = order.planned_duration_hours or 8
            actual_time = order.get_actual_duration_hours() or planned_time

            if actual_time > 0:
                efficiency = min(100, (planned_time / actual_time) * 100)
                total_efficiency += efficiency
                count += 1

        return round(total_efficiency / count, 1) if count > 0 else 0.0

    def get_quality_rate(self, days=30):
        """Показник якості за період"""
        from datetime import timedelta

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Збираємо дані по контролю якості
        quality_checks = QualityCheck.objects.filter(
            production_order__production_line=self,
            check_date__range=[start_date, end_date]
        )

        if not quality_checks.exists():
            return 100.0

        total_checked = sum(check.checked_quantity for check in quality_checks)
        total_passed = sum(check.passed_quantity for check in quality_checks)

        if total_checked > 0:
            return round((total_passed / total_checked) * 100, 2)
        return 100.0

    def get_availability_rate(self, days=30):
        """Коефіцієнт доступності (без ТО та простоїв)"""
        from datetime import timedelta

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Загальний час періоду
        total_hours = days * 24

        # Час простоїв через ТО
        maintenance_hours = MaintenanceSchedule.objects.filter(
            production_line=self,
            status='completed',
            actual_start__range=[start_date, end_date]
        ).aggregate(
            total=Sum('estimated_duration')
        )['total'] or 0

        # Час простоїв через поломки (можна додати окрему модель)
        breakdown_hours = 0  # TODO: додати модель Breakdown

        # Доступність
        downtime_hours = float(maintenance_hours) + breakdown_hours
        availability = max(0, (total_hours - downtime_hours) / total_hours * 100)

        return round(availability, 2)

    def get_oee(self, days=30):
        """Overall Equipment Effectiveness"""
        availability = self.get_availability_rate(days) / 100
        performance = self.get_current_efficiency() / 100
        quality = self.get_quality_rate(days) / 100

        oee = availability * performance * quality * 100
        return round(oee, 2)

    def schedule_next_maintenance(self):
        """Автоматичне планування наступного ТО"""
        # Знаходимо всі типи ТО для цієї лінії
        maintenance_types = MaintenanceType.objects.filter(is_active=True)

        for mt in maintenance_types:
            # Знаходимо останнє ТО цього типу
            last_maintenance = MaintenanceSchedule.objects.filter(
                production_line=self,
                maintenance_type=mt,
                status='completed'
            ).order_by('-actual_end').first()

            if last_maintenance:
                next_date = self._calculate_next_maintenance_date(last_maintenance, mt)
            else:
                # Перше ТО - через місяць
                next_date = timezone.now() + timedelta(days=30)

            # Створюємо запис якщо його ще немає
            existing = MaintenanceSchedule.objects.filter(
                production_line=self,
                maintenance_type=mt,
                status='scheduled'
            ).exists()

            if not existing:
                MaintenanceSchedule.objects.create(
                    production_line=self,
                    maintenance_type=mt,
                    scheduled_date=next_date,
                    estimated_duration=mt.duration_hours
                )

    def _calculate_next_maintenance_date(self, last_maintenance, maintenance_type):
        """Розрахунок дати наступного ТО"""
        if maintenance_type.frequency_type == 'days':
            return last_maintenance.actual_end + timedelta(days=maintenance_type.frequency_value)
        elif maintenance_type.frequency_type == 'hours':
            # TODO: облік мотогодин
            return last_maintenance.actual_end + timedelta(days=maintenance_type.frequency_value)
        else:
            return last_maintenance.actual_end + timedelta(days=30)


# Патчимо існуючу модель
def patch_production_line():
    """Додаємо нові методи до існуючої моделі ProductionLine"""
    from production.models import ProductionLine

    ProductionLine.get_current_efficiency = ProductionLineExtended.get_current_efficiency
    ProductionLine.get_quality_rate = ProductionLineExtended.get_quality_rate
    ProductionLine.get_availability_rate = ProductionLineExtended.get_availability_rate
    ProductionLine.get_oee = ProductionLineExtended.get_oee
    ProductionLine.schedule_next_maintenance = ProductionLineExtended.schedule_next_maintenance
    ProductionLine._calculate_next_maintenance_date = ProductionLineExtended._calculate_next_maintenance_date


# Додаємо методи до ProductionOrder
class ProductionOrderExtended:
    """Розширення для ProductionOrder"""

    def get_actual_duration_hours(self):
        """Фактична тривалість виробництва"""
        if self.actual_start and self.actual_end:
            delta = self.actual_end - self.actual_start
            return round(delta.total_seconds() / 3600, 2)
        elif self.actual_start:
            # Ще не завершено, рахуємо від початку
            delta = timezone.now() - self.actual_start
            return round(delta.total_seconds() / 3600, 2)
        return 0

    def calculate_planned_duration(self):
        """Розрахунок планової тривалості на основі норм"""
        try:
            # Знаходимо норму часу
            time_norm = WorkTimeNorm.objects.filter(
                production_line=self.production_line,
                product=self.recipe.product,
                is_active=True
            ).first()

            if time_norm:
                time_calc = time_norm.calculate_production_time(self.quantity_ordered)
                self.planned_duration_hours = time_calc['total_hours']
                self.save()
                return time_calc
            else:
                # Фолбек на базову формулу
                if self.production_line.capacity_per_hour > 0:
                    hours = float(self.quantity_ordered) / float(self.production_line.capacity_per_hour)
                    self.planned_duration_hours = round(hours, 2)
                    self.save()
                    return {'total_hours': hours}

        except Exception as e:
            print(f"Помилка розрахунку планової тривалості: {e}")
            return {'total_hours': 8}  # Фолбек на 8 годин

    def get_efficiency_percent(self):
        """Ефективність виконання замовлення"""
        if self.planned_duration_hours and self.get_actual_duration_hours():
            planned = float(self.planned_duration_hours)
            actual = self.get_actual_duration_hours()
            if actual > 0:
                return round((planned / actual) * 100, 1)
        return 0.0

    def get_quality_summary(self):
        """Зведення по якості"""
        checks = self.quality_checks.all()
        if not checks:
            return {'total_checked': 0, 'passed_rate': 100, 'defect_rate': 0}

        total_checked = sum(check.checked_quantity for check in checks)
        total_passed = sum(check.passed_quantity for check in checks)
        total_failed = sum(check.failed_quantity for check in checks)

        passed_rate = (total_passed / total_checked * 100) if total_checked > 0 else 100
        defect_rate = (total_failed / total_checked * 100) if total_checked > 0 else 0

        return {
            'total_checked': total_checked,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'passed_rate': round(passed_rate, 2),
            'defect_rate': round(defect_rate, 2)
        }

    def get_waste_summary(self):
        """Зведення по відходах та браку"""
        waste_records = self.waste_records.all()

        total_loss = sum(record.total_loss for record in waste_records)
        total_quantity = sum(record.quantity for record in waste_records)

        waste_by_type = {}
        for record in waste_records:
            category = record.waste_type.category
            if category not in waste_by_type:
                waste_by_type[category] = {'quantity': 0, 'loss': 0}
            waste_by_type[category]['quantity'] += record.quantity
            waste_by_type[category]['loss'] += record.total_loss

        return {
            'total_loss': total_loss,
            'total_quantity': total_quantity,
            'by_type': waste_by_type
        }


# Патчимо ProductionOrder
def patch_production_order():
    """Додаємо нові методи до ProductionOrder"""
    from production.models import ProductionOrder

    ProductionOrder.get_actual_duration_hours = ProductionOrderExtended.get_actual_duration_hours
    ProductionOrder.calculate_planned_duration = ProductionOrderExtended.calculate_planned_duration
    ProductionOrder.get_efficiency_percent = ProductionOrderExtended.get_efficiency_percent
    ProductionOrder.get_quality_summary = ProductionOrderExtended.get_quality_summary
    ProductionOrder.get_waste_summary = ProductionOrderExtended.get_waste_summary


# Ініціалізація всіх патчів
def initialize_production_extensions():
    """Ініціалізація всіх розширень"""
    patch_production_line()
    patch_production_order()


# Викликаємо при імпорті модуля
initialize_production_extensions()