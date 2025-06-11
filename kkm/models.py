from django.contrib.auth import get_user_model
from django.db import models
from backend.models import Product, Warehouse, Company, Firm, Document, TradePoint

User = get_user_model()

class CashSession(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")
    trade_point = models.ForeignKey(TradePoint, on_delete=models.CASCADE, verbose_name="Торгова точка")

    opened_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='opened_sessions', verbose_name="Відкрив")
    opened_at = models.DateTimeField("Час відкриття", auto_now_add=True)

    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_sessions', verbose_name="Закрив")
    closed_at = models.DateTimeField("Час закриття", null=True, blank=True)

    is_closed = models.BooleanField("Закрита", default=False)
    comment = models.TextField("Коментар", blank=True, null=True)

    class Meta:
        verbose_name = "Сесія фірми"
        verbose_name_plural = "Сесії фірми"

    def __str__(self):
        return f"Сесія [{self.firm.name}] з {self.opened_at.date()}"



class CashRegister(models.Model):
    name = models.CharField("Назва каси", max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")
    trade_point = models.ForeignKey(TradePoint, on_delete=models.CASCADE, verbose_name="Торгова точка")

    register_type = models.CharField("Тип каси", max_length=50, choices=[
        ('mock', 'Тестова каса'),
        ('dreamkas', 'Dreamkas API'),
        ('ekka', 'EKKA драйвер'),
        ('checkbox', 'Checkbox API'),
    ])

    ip_address = models.GenericIPAddressField("IP адреса", null=True, blank=True)
    port = models.IntegerField("Порт", null=True, blank=True)
    api_token = models.CharField("API токен", max_length=255, null=True, blank=True)
    login = models.CharField("Логін", max_length=100, null=True, blank=True)
    password = models.CharField("Пароль", max_length=100, null=True, blank=True)
    active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Дата створення", auto_now_add=True)

    class Meta:
        verbose_name = "Каса (ККМ)"
        verbose_name_plural = "Каси (ККМ)"

    def __str__(self):
        return f"{self.name} [{self.get_register_type_display()}]"


class CashShift(models.Model):
    cash_register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name='shifts', verbose_name="Каса")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")

    session = models.ForeignKey(
        'CashSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shifts',
        verbose_name="Сесія"
    )

    opened_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='opened_shifts', verbose_name="Відкрив")
    opened_at = models.DateTimeField("Час відкриття", auto_now_add=True)

    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_shifts', verbose_name="Закрив")
    closed_at = models.DateTimeField("Час закриття", null=True, blank=True)

    is_closed = models.BooleanField("Закрита", default=False)

    class Meta:
        verbose_name = "Касова зміна"
        verbose_name_plural = "Касові зміни"

    def __str__(self):
        return f"Зміна на {self.cash_register.name} [{self.opened_at.date()}] - {'ЗАКРИТА' if self.is_closed else 'ВІДКРИТА'}"


class FiscalReceipt(models.Model):
    shift = models.ForeignKey(CashShift, on_delete=models.CASCADE, related_name='receipts', verbose_name="Зміна")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")

    fiscal_number = models.CharField("Фіскальний номер", max_length=100, null=True, blank=True)
    printed_at = models.DateTimeField("Час друку", auto_now_add=True)
    status = models.CharField("Статус", max_length=20, choices=[
        ('success', 'Успішно'),
        ('fail', 'Помилка'),
        ('pending', 'Очікує'),
    ], default='pending')

    message = models.TextField("Повідомлення/помилка", null=True, blank=True)
    source = models.CharField("Джерело", max_length=100, null=True, blank=True)
    sale_document = models.OneToOneField(Document, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Документ продажу")

    class Meta:
        verbose_name = "Фіскальний чек"
        verbose_name_plural = "Фіскальні чеки"

    def __str__(self):
        return f"Чек #{self.fiscal_number or 'N/A'} [{self.get_status_display()}]"

class ReceiptItemBuffer(models.Model):
    shift = models.ForeignKey("CashShift", on_delete=models.CASCADE, related_name='buffer_items', verbose_name="Зміна")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.DecimalField("Кількість", max_digits=10, decimal_places=2)
    price = models.DecimalField("Ціна", max_digits=10, decimal_places=2)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Склад")
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")
    created_at = models.DateTimeField("Дата створення", auto_now_add=True)

    class Meta:
        verbose_name = "Буферна позиція чека"
        verbose_name_plural = "Буферні позиції чеків"

    def __str__(self):
        return f"{self.product.name} x {self.quantity} @ {self.price}"



class ReceiptOperation(models.Model):
    receipt = models.ForeignKey(FiscalReceipt, on_delete=models.CASCADE, related_name='operations', verbose_name="Чек")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.DecimalField("Кількість", max_digits=10, decimal_places=2)
    price = models.DecimalField("Ціна", max_digits=10, decimal_places=2)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Склад")
    created_at = models.DateTimeField("Дата створення", auto_now_add=True)

    class Meta:
        verbose_name = "Операція з чеку"
        verbose_name_plural = "Операції з чеків"

    def __str__(self):
        return f"{self.product.name} x {self.quantity} @ {self.price}"


class CashWorkstation(models.Model):
    ROLE_CHOICES = [
        ('bar', 'Бар'),
        ('waiter', 'Офіціант'),
        ('front', 'Фронт'),
        ('kitchen', 'Кухня'),
        ('admin', 'Адмін'),
    ]

    name = models.CharField("Назва ПК", max_length=100)
    app_key = models.CharField("APP ключ", max_length=100, unique=True)
    cash_register = models.ForeignKey("CashRegister", on_delete=models.CASCADE, verbose_name="Каса")
    role = models.CharField("Роль/позиція", max_length=20, choices=ROLE_CHOICES, default='front')
    active = models.BooleanField("Активний", default=True)

    class Meta:
        verbose_name = "Касовий ПК"
        verbose_name_plural = "Касові ПК"

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}) → {self.cash_register.name}"