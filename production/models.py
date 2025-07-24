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