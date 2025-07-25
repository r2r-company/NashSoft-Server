from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.db.models import Max, Sum
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.contrib.postgres.fields import ArrayField


# ========== ДОВІДНИКИ ==========
from backend.exceptions import ValidationError


class Company(models.Model):
    name = models.CharField(_('Назва компанії'), max_length=255)
    tax_id = models.CharField(_('ЄДРПОУ / ІПН'), max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Компанія'
        verbose_name_plural = 'Компанії'


class Firm(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    vat_type = models.CharField(
        max_length=20,
        choices=[
            ('ФОП', 'ФОП (без ПДВ)'),
            ('ТОВ', 'ТОВ (з ПДВ)'),
            ('ТЗОВ', 'ТЗОВ (з ПДВ)'),
            ('ПАТ', 'ПАТ (з ПДВ)'),
            ('ПрАТ', 'ПрАТ (з ПДВ)'),
        ]
    )
    is_vat_payer = models.BooleanField(
        verbose_name="Платник ПДВ",
        help_text="Чи сплачує фірма ПДВ"
    )

    def save(self, *args, **kwargs):
        # Автоматично встановлюємо is_vat_payer
        self.is_vat_payer = self.vat_type in ['ТОВ', 'ТЗОВ', 'ПАТ', 'ПрАТ']
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Фірма'
        verbose_name_plural = 'Фірми'


class Warehouse(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Склад'
        verbose_name_plural = 'Склади'


class Department(models.Model):
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Відділ'
        verbose_name_plural = 'Відділи'


class DepartmentWarehouseAccess(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Відділ до складу '
        verbose_name_plural = 'Відділи до складу '


class TradePoint(models.Model):
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Торгова точка'
        verbose_name_plural = 'Торгові точки'


class Unit(models.Model):
    name = models.CharField(_('Одиниця виміру'), max_length=50)
    symbol = models.CharField(_('Символ'), max_length=10, blank=True, null=True)  # ✅ додано

    def __str__(self):
        return f"{self.name} ({self.symbol})" if self.symbol else self.name

    class Meta:
        verbose_name = 'Одиниця виміру'
        verbose_name_plural = 'Одиниці виміру'


class ProductGroup(models.Model):
    name = models.CharField(_('Назва групи'), max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE,
                               verbose_name=_('Батьківська група'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Група товарів'
        verbose_name_plural = 'Групи товарів'


class Product(models.Model):
    PRODUCT_TYPES = [
        ('product', 'Товар'),
        ('service', 'Послуга'),
        ('semi', 'Напівфабрикат'),
        ('ingredient', 'Інгредієнт'),
    ]
    name = models.CharField(_('Назва товару'), max_length=255)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True,
                             verbose_name=_('Базова одиниця виміру'))  # ✅ ДОДАВ "БАЗОВА"
    group = models.ForeignKey('ProductGroup', null=True, blank=True, on_delete=models.SET_NULL,
                              verbose_name=_('Група товару'))
    firm = models.ForeignKey("Firm", on_delete=models.CASCADE, verbose_name="Фірма-власник")
    type = models.CharField(_('Тип'), max_length=20, choices=PRODUCT_TYPES, default='product')

    # ✅ ДОДАТИ ЦІ ПОЛЯ:
    base_price = models.DecimalField(_('Базова ціна'), max_digits=10, decimal_places=2, null=True, blank=True,
                                     help_text="Ціна за базову одиницю виміру")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Номенклатура'
        verbose_name_plural = 'Номенклатура'


class ProductCalculation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='calculations', verbose_name='Продукт')
    date = models.DateField(_('Дата дії'))
    note = models.TextField(_('Примітка'), blank=True, null=True)

    class Meta:
        verbose_name = 'Калькуляція'
        verbose_name_plural = 'Калькуляції'
        ordering = ['-date']

    def __str__(self):
        return f"Калькуляція для {self.product.name} від {self.date}"


class ProductCalculationItem(models.Model):
    calculation = models.ForeignKey(ProductCalculation, on_delete=models.CASCADE, related_name='items')
    component = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Компонент")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Кількість")
    loss_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Відходи %")
    cooking_loss_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                               verbose_name="Втрати при готуванні %")
    note = models.TextField(blank=True, null=True, verbose_name="Примітка")

    # ✅ НОВЕ ПОЛЕ ДЛЯ ФАСУВАННЯ:
    unit_conversion = models.ForeignKey(
        'ProductUnitConversion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Фасування",
        help_text="Оберіть фасування або залиште пустим для базової одиниці"
    )

    class Meta:
        verbose_name = "Позиція калькуляції"
        verbose_name_plural = "Позиції калькуляції"

    def __str__(self):
        if self.unit_conversion:
            return f"{self.component.name} - {self.quantity} {self.unit_conversion.to_unit.name}"
        else:
            return f"{self.component.name} - {self.quantity} {self.component.unit.name}"

    def get_base_quantity(self):
        """Отримати кількість в базових одиницях"""
        if self.unit_conversion:
            # Якщо обрано фасування - конвертуємо в базові одиниці
            return self.quantity * self.unit_conversion.factor
        else:
            # Якщо базова одиниця
            return self.quantity

    def get_display_unit(self):
        """Отримати одиницю для відображення"""
        if self.unit_conversion:
            return self.unit_conversion.to_unit
        else:
            return self.component.unit


class ProductUnitConversion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    name = models.CharField("Назва фасування", max_length=100, help_text="Пакет 100г, Упаковка 2кг")
    from_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="from_conversions",
                                  verbose_name="Базова од.")
    to_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="to_conversions",
                                verbose_name="Од. фасування")
    factor = models.DecimalField("Коефіцієнт", max_digits=10, decimal_places=4,
                                 help_text="Скільки базових одиниць в одному фасуванні")

    class Meta:
        unique_together = ('product', 'name')
        verbose_name = "Фасування товару"
        verbose_name_plural = "Фасування товарів"

    def __str__(self):
        return f"{self.product.name}: {self.name}"


class CustomerType(models.Model):
    name = models.CharField(_('Назва типу'), max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип клієнта'
        verbose_name_plural = 'Типи клієнтів'


class Customer(models.Model):
    name = models.CharField(_('Назва клієнта'), max_length=255)
    type = models.ForeignKey("CustomerType", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Тип")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Клієнт'
        verbose_name_plural = 'Клієнти'


class Supplier(models.Model):
    name = models.CharField(_('Назва постачальника'), max_length=255)
    tax_id = models.CharField(_('ІПН'), max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Постачальник'
        verbose_name_plural = 'Постачальники'


class PaymentType(models.Model):
    name = models.CharField(_('Тип оплати'), max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип оплати'
        verbose_name_plural = 'Типи оплат'


def get_document_meta(document):
    """Отримати метадані для документа з налаштувань компанії"""
    try:
        acc_settings = AccountingSettings.objects.get(company=document.company)
    except AccountingSettings.DoesNotExist:
        # Фолбек на старі значення
        acc_settings = type('obj', (object,), {
            'stock_account': '281',
            'supplier_account': '631',
            'vat_input_account': '644',
            'client_account': '361',
            'revenue_account': '701',
            'vat_output_account': '641'
        })()

    # Отримуємо префікси з DocumentSettings
    try:
        doc_settings = DocumentSettings.objects.get(company=document.company)
    except DocumentSettings.DoesNotExist:
        doc_settings = type('obj', (object,), {
            'receipt_prefix': '703',
            'sale_prefix': '704',
            'return_to_supplier_prefix': 'RTS',
            'return_from_client_prefix': 'RFC',
            'transfer_prefix': 'TRF',
            'inventory_prefix': 'INV',
            'stock_in_prefix': 'STI',
        })()

    meta_map = {
        "receipt": {
            "prefix": doc_settings.receipt_prefix,
            "entries": [
                {"debit": acc_settings.stock_account, "credit": acc_settings.supplier_account,
                 "amount": "price_without_vat"},
                {"debit": acc_settings.vat_input_account, "credit": acc_settings.supplier_account,
                 "amount": "vat_amount"},
            ],
        },
        "sale": {
            "prefix": doc_settings.sale_prefix,
            "entries": [
                {"debit": acc_settings.client_account, "credit": acc_settings.revenue_account,
                 "amount": "price_without_vat"},
                {"debit": acc_settings.client_account, "credit": acc_settings.vat_output_account,
                 "amount": "vat_amount"},
            ],
        },
        "return_to_supplier": {
            "prefix": doc_settings.return_to_supplier_prefix,
            "entries": [
                {"debit": acc_settings.supplier_account, "credit": acc_settings.stock_account,
                 "amount": "price_without_vat"},
                {"debit": acc_settings.supplier_account, "credit": acc_settings.vat_input_account,
                 "amount": "vat_amount"},
            ],
        },
        "return_from_client": {
            "prefix": doc_settings.return_from_client_prefix,
            "entries": [
                {"debit": acc_settings.stock_account, "credit": acc_settings.client_account,
                 "amount": "price_without_vat"},
                {"debit": acc_settings.vat_output_account, "credit": acc_settings.client_account,
                 "amount": "vat_amount"},
            ],
        },
        "transfer": {
            "prefix": doc_settings.transfer_prefix,
            "entries": [
                {"debit": acc_settings.stock_account, "credit": acc_settings.stock_account,
                 "amount": "price_without_vat"},
            ],
        },
        "inventory": {
            "prefix": doc_settings.inventory_prefix,
            "entries": [],
        },
        "stock_in": {
            "prefix": doc_settings.stock_in_prefix,
            "entries": [
                {"debit": acc_settings.stock_account, "credit": "719", "amount": "price_without_vat"},
            ],
        },
    }

    return meta_map.get(document.doc_type, {})


# ========== ДОКУМЕНТИ ==========

class Document(models.Model):
    DOC_TYPES = [
        ('receipt', _('Поступлення')),
        ('inventory_in', 'Оприбуткування'),
        ('sale', _('Реалізація')),
        ('return_from_client', _('Повернення від клієнта')),
        ('return_to_supplier', _('Повернення постачальнику')),
        ('transfer', _('Переміщення')),
        ('inventory', _('Інвентаризація')),
        ('stock_in', _('Оприбуткування')),
        ('conversion', 'Фасування'),
        ('production_order', 'Виробниче замовлення'),
        ('production', 'Виробництво'),
        ('production_plan', 'План виробництва'),
        ('work_order', 'Робоче завдання'),
        ('quality_control', 'Контроль якості'),

    ]
    doc_type = models.CharField(_('Тип документа'), max_length=30, choices=DOC_TYPES)
    doc_number = models.CharField(_('Номер документа'), max_length=50, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_('Компанія'))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name=_('Склад'))
    date = models.DateTimeField(_('Дата створення'), auto_now_add=True)
    target_warehouse = models.ForeignKey(
        'Warehouse', on_delete=models.CASCADE, null=True, blank=True, related_name='incoming_docs',
        verbose_name='Склад призначення'
    )
    source_document = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Документ-джерело'
    )
    firm = models.ForeignKey('Firm', on_delete=models.CASCADE, verbose_name=_('Фірма'))
    shift = models.ForeignKey("kkm.CashShift", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Зміна")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Постачальник"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Клієнт"
    )
    contract = models.ForeignKey("settlements.Contract", on_delete=models.SET_NULL, null=True, blank=True)
    auto_payment = models.BooleanField(default=False, verbose_name="Автоматична оплата")
    status = models.CharField(
        _('Статус'),
        max_length=20,
        default='draft',
        choices=[
            ('draft', 'Чернетка'),
            ('posted', 'Проведено'),
            ('cancelled', 'Скасовано'),
        ]
    )

    def get_prefix(self):
        """Отримати префікс документа з налаштувань компанії"""
        try:
            settings = DocumentSettings.objects.get(company=self.company)
        except DocumentSettings.DoesNotExist:
            # Фолбек на старі значення
            fallback = {
                'receipt': '703',
                'sale': '704',
                'return_to_supplier': 'RTS',
                'return_from_client': 'RFC',
                'transfer': 'TRF',
                'inventory': 'INV',
                'stock_in': 'STI',
                'conversion': 'CNV',
            }
            return fallback.get(self.doc_type, 'DOC')

        # Маппінг типів документів на поля налаштувань
        prefix_map = {
            'receipt': settings.receipt_prefix,
            'sale': settings.sale_prefix,
            'return_to_supplier': settings.return_to_supplier_prefix,
            'return_from_client': settings.return_from_client_prefix,
            'transfer': settings.transfer_prefix,
            'inventory': settings.inventory_prefix,
            'stock_in': settings.stock_in_prefix,
            'conversion': settings.conversion_prefix,
        }

        return prefix_map.get(self.doc_type, 'DOC')

    def get_accounting_entry(self):
        meta = get_document_meta(self)
        return {
            "debit": meta.get("debit"),
            "credit": meta.get("credit"),
            "label": meta.get("label"),
        }

    def get_full_name(self):
        """Повертає 'Реалізація SALE-00014'"""
        meta = self.get_accounting_entry()
        return f"{meta.get('label', self.doc_type.title())} {self.doc_number}"

    def save(self, *args, **kwargs):
        if not self.doc_number:
            prefix = self.get_prefix()

            with transaction.atomic():
                last_number = (
                    Document.objects
                    .select_for_update()
                    .filter(doc_type=self.doc_type, doc_number__startswith=prefix)
                    .aggregate(max_num=Max('doc_number'))
                    .get('max_num')
                )

                if last_number:
                    try:
                        last_seq = int(last_number.split('-')[-1])
                    except:
                        last_seq = 0
                else:
                    last_seq = 0

                new_seq = str(last_seq + 1).zfill(5)
                self.doc_number = f"{prefix}-{new_seq}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_doc_type_display()} #{self.doc_number}"

    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        permissions = [
            # Поступлення
            ("create_receipt", "Can create Receipt"),
            ("view_receipt", "Can view Receipt"),
            ("edit_receipt", "Can edit Receipt"),
            ("delete_receipt", "Can delete Receipt"),

            # Реалізація
            ("create_sale", "Can create Sale"),
            ("view_sale", "Can view Sale"),
            ("edit_sale", "Can edit Sale"),
            ("delete_sale", "Can delete Sale"),

            # Повернення від клієнта
            ("create_return_from_client", "Can create Return From Client"),
            ("view_return_from_client", "Can view Return From Client"),
            ("edit_return_from_client", "Can edit Return From Client"),
            ("delete_return_from_client", "Can delete Return From Client"),

            # Повернення постачальнику
            ("create_return_to_supplier", "Can create Return To Supplier"),
            ("view_return_to_supplier", "Can view Return To Supplier"),
            ("edit_return_to_supplier", "Can edit Return To Supplier"),
            ("delete_return_to_supplier", "Can delete Return To Supplier"),

            # Переміщення
            ("create_transfer", "Can create Transfer"),
            ("view_transfer", "Can view Transfer"),
            ("edit_transfer", "Can edit Transfer"),
            ("delete_transfer", "Can delete Transfer"),

            # Інвентаризація
            ("create_inventory", "Can create Inventory"),
            ("view_inventory", "Can view Inventory"),
            ("edit_inventory", "Can edit Inventory"),
            ("delete_inventory", "Can delete Inventory"),

            ("create_stock_in", "Can create Stock In"),
            ("view_stock_in", "Can view Stock In"),
            ("edit_stock_in", "Can edit Stock In"),
            ("delete_stock_in", "Can delete Stock In"),
        ]
        verbose_name = 'Документ'
        verbose_name_plural = 'Документи'


# ========== ТАБЛИЧНІ ЧАСТИНИ ==========

class DocumentItem(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='items', verbose_name=_('Документ'))
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_('Товар'))
    quantity = models.DecimalField(_('Кількість'), max_digits=10, decimal_places=2)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name='Одиниця виміру')
    unit_conversion = models.ForeignKey(ProductUnitConversion, on_delete=models.SET_NULL, null=True, blank=True,
                                        verbose_name='Фасування')  # ✅ ДОДАТИ ЦЕ ПОЛЕ
    price = models.DecimalField(_('Ціна'), max_digits=10, decimal_places=2)
    discount = models.DecimalField(_('Знижка (%)'), max_digits=5, decimal_places=2, default=0)
    final_price = models.DecimalField(_('Ціна з урахуванням знижки'), max_digits=10, decimal_places=2, null=True,
                                      blank=True)
    converted_quantity = models.DecimalField(_('Кількість (баз.)'), max_digits=10, decimal_places=3, null=True,
                                             blank=True)
    vat_percent = models.DecimalField(_('Ставка ПДВ (%)'), max_digits=5, decimal_places=2, null=True, blank=True)
    vat_amount = models.DecimalField(_('Сума ПДВ'), max_digits=10, decimal_places=2, null=True, blank=True)
    price_without_vat = models.DecimalField(_('Ціна без ПДВ'), max_digits=10, decimal_places=2, null=True, blank=True)
    price_with_vat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    role = models.CharField(
        max_length=10,
        choices=[('source', 'Джерело'), ('target', 'Результат')],
        null=True,
        blank=True,
        verbose_name="Роль (для фасування)"
    )

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    class Meta:
        verbose_name = 'Позиція документа'
        verbose_name_plural = 'Позиції документів'


# ========== ОПЕРАЦІЇ ==========
class Operation(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name=_('Документ'))
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_('Товар'))
    quantity = models.DecimalField(_('Кількість'), max_digits=10, decimal_places=2)

    # ⬇️ НОВА СИСТЕМА ЦІН
    cost_price = models.DecimalField(_('Собівартість'), max_digits=10, decimal_places=2, default=0,
                                     help_text="Собівартість одиниці")
    sale_price = models.DecimalField(_('Ціна продажу'), max_digits=10, decimal_places=2, null=True, blank=True,
                                     help_text="Ціна продажу одиниці")

    # ⬇️ РОЗРАХУНКОВІ ПОЛЯ
    total_cost = models.DecimalField(_('Загальна собівартість'), max_digits=12, decimal_places=2, default=0,
                                     help_text="cost_price * quantity")
    total_sale = models.DecimalField(_('Загальна сума продажу'), max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text="sale_price * quantity")
    profit = models.DecimalField(_('Прибуток'), max_digits=12, decimal_places=2, null=True, blank=True,
                                 help_text="total_sale - total_cost")

    # ⬇️ СТАРЕ ПОЛЕ (для зворотної сумісності поки що)
    price = models.DecimalField(_('Ціна (застаріле)'), max_digits=10, decimal_places=2, default=0,
                                help_text="Тимчасово для сумісності")

    source_operation = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                         verbose_name=_('Партія'))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name=_('Склад'))
    visible = models.BooleanField(_('Видимий залишок'), default=True)
    direction = models.CharField(_('Напрямок'), max_length=10)  # in/out
    created_at = models.DateTimeField(_('Створено'), auto_now_add=True)

    def save(self, *args, **kwargs):
        """Автоматично рахуємо суми при збереженні"""
        self.total_cost = self.cost_price * self.quantity

        if self.sale_price:
            self.total_sale = self.sale_price * self.quantity
            self.profit = self.total_sale - self.total_cost

        # Для зворотної сумісності з існуючим кодом
        if not self.price:
            self.price = self.cost_price

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Операція'
        verbose_name_plural = 'Операції'

    def __str__(self):
        return f"{self.direction.upper()} {self.product.name} x {self.quantity} (собівартість: {self.cost_price})"


class AuditLog(models.Model):
    document = models.ForeignKey('Document', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Документ')
    price_setting_document = models.ForeignKey('PriceSettingDocument', null=True, blank=True, on_delete=models.SET_NULL,
                                               verbose_name='Документ ціноутворення')
    user = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Користувач')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP-адреса')
    endpoint = models.CharField(max_length=255, null=True, blank=True, verbose_name='Endpoint')
    action = models.CharField(max_length=100, verbose_name='Дія')
    message = models.TextField(verbose_name='Повідомлення')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Час')

    class Meta:
        verbose_name = 'Аудит лог'
        verbose_name_plural = 'Аудит логи'

    def __str__(self):
        return f"[{self.timestamp}] {self.action}: {self.message}"


class PriceType(models.Model):
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)  # Додаємо значення за замовчуванням

    class Meta:
        verbose_name = "Тип ціни"
        verbose_name_plural = "Типи цін"

    def __str__(self):
        return self.name


class PriceSettingDocument(models.Model):
    doc_number = models.CharField(max_length=20, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, verbose_name="Фірма")  # ← ось це додай
    created_at = models.DateTimeField(auto_now_add=True)
    valid_from = models.DateField(help_text="Дата початку дії цін")
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Чернетка'),
        ('approved', 'Затверджено'),
    ], default='draft')
    comment = models.TextField(blank=True, null=True)
    trade_points = models.ManyToManyField('TradePoint', blank=True)

    # Основание
    base_type = models.CharField(
        max_length=20,
        choices=[
            ('product_group', 'Група товарів'),
            ('receipt', 'Документ поступлення'),
            ('price_type', 'Інший тип ціни')
        ],
        null=True, blank=True
    )
    base_group = models.ForeignKey('ProductGroup', on_delete=models.SET_NULL, null=True, blank=True)
    base_receipt = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True,
                                     limit_choices_to={'doc_type': 'receipt'})
    base_price_type = models.ForeignKey('PriceType', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Документ ціноутворення"
        verbose_name_plural = "Документи ціноутворення"

    def __str__(self):
        return f"Ціноутворення {self.doc_number} ({self.company.name})"

    def save(self, *args, **kwargs):
        if not self.doc_number:
            prefix = 'PS'
            last_number = (
                PriceSettingDocument.objects
                .filter(doc_number__startswith=prefix)
                .aggregate(max_num=Max('doc_number'))
                .get('max_num')
            )

            if last_number:
                try:
                    last_seq = int(last_number.split('-')[-1])
                except:
                    last_seq = 0
            else:
                last_seq = 0

            new_seq = str(last_seq + 1).zfill(5)
            self.doc_number = f"{prefix}-{new_seq}"

        super().save(*args, **kwargs)


# models.py - ВИПРАВЛЕНА частина PriceSettingItem

class PriceSettingItem(models.Model):
    price_setting_document = models.ForeignKey(PriceSettingDocument, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price_type = models.ForeignKey(PriceType, on_delete=models.CASCADE, default=1)

    # ✅ НОВА ЛОГІКА ЦІН:
    price = models.DecimalField("Ціна продажу", max_digits=12, decimal_places=2,
                                help_text="Фінальна ціна за одиницю (з урахуванням фасування)")

    vat_included = models.BooleanField(default=True, verbose_name="ПДВ включено в ціну")
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    markup_percent = models.DecimalField("Націнка %", max_digits=5, decimal_places=2, default=0.00)

    # ✅ РОЗРАХОВАНІ ПОЛЯ ПДВ:
    price_without_vat = models.DecimalField("Ціна без ПДВ", max_digits=12, decimal_places=2, default=0)
    vat_amount = models.DecimalField("Сума ПДВ", max_digits=12, decimal_places=2, default=0)

    source_item = models.ForeignKey('DocumentItem', on_delete=models.SET_NULL, null=True, blank=True)
    trade_point = models.ForeignKey(TradePoint, on_delete=models.CASCADE)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, null=True, blank=True)

    # ✅ ФАСУВАННЯ:
    unit_conversion = models.ForeignKey(
        ProductUnitConversion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Фасування",
        help_text="Якщо не вказано - ціна за базову одиницю"
    )

    # ✅ АВТОМАТИЧНО РОЗРАХОВУЄТЬСЯ:
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        verbose_name="Одиниця ціни",
        null=True,
        blank=True,
        help_text="Автоматично: базова одиниця або одиниця фасування"
    )

    def save(self, *args, **kwargs):
        """Автоматично визначаємо одиницю та розраховуємо ПДВ"""

        # ✅ 1. ВИЗНАЧАЄМО ОДИНИЦЮ:
        if self.unit_conversion:
            # Якщо є фасування - одиниця з фасування
            self.unit = self.unit_conversion.to_unit
        else:
            # Якщо без фасування - базова одиниця товару
            self.unit = self.product.unit

        # ✅ 2. РОЗРАХОВУЄМО ПДВ:
        self._calculate_vat()

        super().save(*args, **kwargs)

    def _calculate_vat(self):
        """Розрахунок ПДВ"""
        if not self.vat_percent:
            # Автопідстановка ПДВ залежно від типу фірми
            if self.firm and self.firm.is_vat_payer:
                self.vat_percent = 20
            else:
                self.vat_percent = 0

        if self.vat_included and self.vat_percent > 0:
            # Ціна ВКЛЮЧАЄ ПДВ - витягуємо ПДВ
            self.price_without_vat = round(self.price / (1 + self.vat_percent / 100), 2)
            self.vat_amount = round(self.price - self.price_without_vat, 2)
        else:
            # Ціна БЕЗ ПДВ або ПДВ = 0
            self.price_without_vat = self.price
            if self.vat_percent > 0:
                self.vat_amount = round(self.price * self.vat_percent / 100, 2)
            else:
                self.vat_amount = 0

    def get_base_price(self):
        """Розрахувати ціну за базову одиницю товару"""
        if self.unit_conversion:
            # Якщо є фасування - перераховуємо в базову ціну
            return round(self.price / self.unit_conversion.factor, 2)
        else:
            # Якщо без фасування - ціна вже за базову одиницю
            return self.price

    def get_package_info(self):
        """Отримати інформацію про фасування для відображення"""
        if self.unit_conversion:
            return {
                'is_packaged': True,
                'package_name': self.unit_conversion.name,
                'package_unit': self.unit_conversion.to_unit.symbol,
                'base_unit': self.product.unit.symbol,  # ✅ ЗАВЖДИ базова одиниця ТОВАРУ
                'factor': float(self.unit_conversion.factor),
                'price_per_package': float(self.price),
                'price_per_base_unit': float(self.get_base_price())
            }
        else:
            return {
                'is_packaged': False,
                'package_name': 'Базова одиниця',
                'package_unit': self.product.unit.symbol,
                'base_unit': self.product.unit.symbol,
                'factor': 1.0,
                'price_per_package': float(self.price),
                'price_per_base_unit': float(self.price)
            }

    def __str__(self):
        package_info = self.get_package_info()
        return f"{self.product.name} ({package_info['package_name']}) - {self.price} грн/{package_info['package_unit']}"

    class Meta:
        unique_together = ('price_setting_document', 'product', 'price_type', 'trade_point', 'unit_conversion')
        verbose_name = "Позиція ціноутворення"
        verbose_name_plural = "Позиції ціноутворення"


User = get_user_model()


class Interface(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    access_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Інтерфейси'
        verbose_name_plural = 'Інтерфейси'


class AppUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='app_profiles')
    interfaces = models.ManyToManyField(Interface)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        roles = ", ".join(i.name for i in self.interfaces.all())
        return f"{self.user.username} - {roles}"

    class Meta:
        verbose_name = 'Користувачі системи'
        verbose_name_plural = 'Користувачі системи'


class DiscountRule(models.Model):
    name = models.CharField("Назва правила", max_length=255)
    percent = models.DecimalField("Знижка (%)", max_digits=5, decimal_places=2)

    # ⏰ Дата і час
    start_date = models.DateField("Початкова дата", null=True, blank=True)
    end_date = models.DateField("Кінцева дата", null=True, blank=True)
    weekdays = ArrayField(models.IntegerField(), null=True, blank=True,
                          help_text="0=Пн, ..., 6=Нд")
    start_time = models.TimeField("Час початку", null=True, blank=True)
    end_time = models.TimeField("Час завершення", null=True, blank=True)

    # 🧾 На які товари / точки діє
    products = models.ManyToManyField(Product, blank=True, verbose_name="Товари (опц.)")
    trade_points = models.ManyToManyField(TradePoint, blank=True, verbose_name="Торгові точки (опц.)")

    is_active = models.BooleanField("Активне", default=True)

    class Meta:
        verbose_name = "Правило знижки"
        verbose_name_plural = "Правила знижок"

    def __str__(self):
        return f"{self.name} - {self.percent}%"


class AccountingSettings(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE)

    # Рахунки для товарів
    stock_account = models.CharField("Рахунок товарів", max_length=10, default="281")
    supplier_account = models.CharField("Рахунок постачальників", max_length=10, default="631")
    vat_input_account = models.CharField("ПДВ вхідний", max_length=10, default="644")

    # Рахунки для продажів
    client_account = models.CharField("Рахунок клієнтів", max_length=10, default="361")
    revenue_account = models.CharField("Рахунок доходів", max_length=10, default="701")
    vat_output_account = models.CharField("ПДВ вихідний", max_length=10, default="641")

    # Ставки ПДВ
    default_vat_rate = models.DecimalField("Ставка ПДВ за замовчуванням (%)", max_digits=5, decimal_places=2,
                                           default=20.00)
    reduced_vat_rate = models.DecimalField("Знижена ставка ПДВ (%)", max_digits=5, decimal_places=2, default=7.00)
    zero_vat_rate = models.DecimalField("Нульова ставка ПДВ (%)", max_digits=5, decimal_places=2, default=0.00)

    # ⬇️ ДОДАЙТЕ ЦЕ ПОЛЕ:
    default_price_type = models.ForeignKey(
        'PriceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Тип ціни за замовчуванням"
    )

    class Meta:
        verbose_name = "Налаштування обліку"


class DocumentSettings(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='doc_settings')

    # Префікси документів
    receipt_prefix = models.CharField("Префікс поступлень", max_length=10, default="703")
    sale_prefix = models.CharField("Префікс продажів", max_length=10, default="704")
    return_to_supplier_prefix = models.CharField("Префікс повернень постачальнику", max_length=10, default="RTS")
    return_from_client_prefix = models.CharField("Префікс повернень від клієнта", max_length=10, default="RFC")
    transfer_prefix = models.CharField("Префікс переміщень", max_length=10, default="TRF")
    inventory_prefix = models.CharField("Префікс інвентаризації", max_length=10, default="INV")
    stock_in_prefix = models.CharField("Префікс оприбуткування", max_length=10, default="STI")
    conversion_prefix = models.CharField("Префікс фасування", max_length=10, default="CNV")

    class Meta:
        verbose_name = "Налаштування документів"


class ChartOfAccounts(models.Model):
    """План рахунків"""
    code = models.CharField("Код рахунку", max_length=10, unique=True)
    name = models.CharField("Назва рахунку", max_length=200)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               verbose_name="Батьківський рахунок")

    account_type = models.CharField("Тип рахунку", max_length=20, choices=[
        ('asset', 'Актив'),
        ('liability', 'Пасив'),
        ('equity', 'Капітал'),
        ('revenue', 'Доходи'),
        ('expense', 'Витрати'),
    ])

    is_active = models.BooleanField("Активний", default=True)
    is_analytic = models.BooleanField("Аналітичний", default=False)

    class Meta:
        verbose_name = "Рахунок"
        verbose_name_plural = "План рахунків"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class CostCenter(models.Model):
    """Центр витрат / фінансової відповідальності"""
    code = models.CharField("Код ЦВ", max_length=20, unique=True)
    name = models.CharField("Назва", max_length=200)

    # Ієрархія
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Батьківський ЦВ")

    # Зв'язки
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)

    # Тип центру
    center_type = models.CharField("Тип центру", max_length=20, choices=[
        ('profit', 'Центр прибутку'),
        ('cost', 'Центр витрат'),
        ('revenue', 'Центр доходу'),
        ('investment', 'Центр інвестицій'),
    ], default='cost')

    # Бюджет
    monthly_budget = models.DecimalField("Місячний бюджет", max_digits=15, decimal_places=2, default=0)

    # Відповідальний
    manager = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Менеджер")

    is_active = models.BooleanField("Активний", default=True)

    class Meta:
        verbose_name = "Центр витрат"
        verbose_name_plural = "Центри витрат"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_actual_costs(self, date_from, date_to):
        """Фактичні витрати за період"""
        return AccountingEntry.objects.filter(
            cost_center=self,
            date__range=[date_from, date_to],
            debit_account__account_type='expense'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')


class Currency(models.Model):
    """Валюти"""
    code = models.CharField("Код валюти", max_length=3, unique=True)  # USD, EUR, UAH
    name = models.CharField("Назва", max_length=100)
    symbol = models.CharField("Символ", max_length=5)  # $, €, ₴

    is_base = models.BooleanField("Базова валюта", default=False)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Валюта"
        verbose_name_plural = "Валюти"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        # Тільки одна базова валюта
        if self.is_base:
            Currency.objects.filter(is_base=True).update(is_base=False)
        super().save(*args, **kwargs)


class ExchangeRate(models.Model):
    """Курси валют"""
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    date = models.DateField("Дата курсу")
    rate = models.DecimalField("Курс", max_digits=12, decimal_places=6)

    # Джерело курсу
    source = models.CharField("Джерело", max_length=20, choices=[
        ('nbu', 'НБУ'),
        ('manual', 'Ручне введення'),
        ('bank', 'Банк'),
        ('api', 'API сервіс')
    ], default='nbu')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Курс валюти"
        verbose_name_plural = "Курси валют"
        unique_together = ('currency', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.currency.code}: {self.rate} ({self.date})"


class AccountingEntry(models.Model):
    """Бухгалтерська проводка"""
    date = models.DateField("Дата проводки")
    document = models.ForeignKey('Document', on_delete=models.CASCADE, null=True, blank=True)

    debit_account = models.ForeignKey(ChartOfAccounts, on_delete=models.CASCADE, related_name='debit_entries')
    credit_account = models.ForeignKey(ChartOfAccounts, on_delete=models.CASCADE, related_name='credit_entries')

    amount = models.DecimalField("Сума", max_digits=15, decimal_places=2)
    description = models.CharField("Опис", max_length=500)

    # Аналітика
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="Центр витрат")

    created_at = models.DateTimeField(auto_now_add=True)
    urrency = models.ForeignKey(Currency, on_delete=models.CASCADE, default=1)  # UAH по замовчуванню
    amount_currency = models.DecimalField("Сума у валюті", max_digits=15, decimal_places=2)
    exchange_rate = models.DecimalField("Курс", max_digits=12, decimal_places=6, default=1)
    def clean(self):
        if self.debit_account == self.credit_account:
            raise ValidationError("Дебет і кредит не можуть бути однаковими")
        if self.amount <= 0:
            raise ValidationError("Сума повинна бути більше 0")

    class Meta:
        verbose_name = "Проводка"
        verbose_name_plural = "Проводки"
        ordering = ['-date', '-created_at']


class BudgetPeriod(models.Model):
    """Бюджетний період"""
    name = models.CharField("Назва періоду", max_length=100)
    company = models.ForeignKey('Company', on_delete=models.CASCADE)

    start_date = models.DateField("Початок періоду")
    end_date = models.DateField("Кінець періоду")

    status = models.CharField("Статус", max_length=20, choices=[
        ('draft', 'Проект'),
        ('approved', 'Затверджено'),
        ('active', 'Діючий'),
        ('closed', 'Закритий')
    ], default='draft')

    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='approved_budgets')
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Бюджетний період"
        verbose_name_plural = "Бюджетні періоди"
        unique_together = ('company', 'start_date', 'end_date')

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"


class BudgetLine(models.Model):
    """Статті бюджету"""
    budget_period = models.ForeignKey(BudgetPeriod, on_delete=models.CASCADE, related_name='lines')

    # Прив'язка
    account = models.ForeignKey('ChartOfAccounts', on_delete=models.CASCADE)
    cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True)

    # Бюджетні суми по місяцях
    jan = models.DecimalField("Січень", max_digits=15, decimal_places=2, default=0)
    feb = models.DecimalField("Лютий", max_digits=15, decimal_places=2, default=0)
    mar = models.DecimalField("Березень", max_digits=15, decimal_places=2, default=0)
    apr = models.DecimalField("Квітень", max_digits=15, decimal_places=2, default=0)
    may = models.DecimalField("Травень", max_digits=15, decimal_places=2, default=0)
    jun = models.DecimalField("Червень", max_digits=15, decimal_places=2, default=0)
    jul = models.DecimalField("Липень", max_digits=15, decimal_places=2, default=0)
    aug = models.DecimalField("Серпень", max_digits=15, decimal_places=2, default=0)
    sep = models.DecimalField("Вересень", max_digits=15, decimal_places=2, default=0)
    oct = models.DecimalField("Жовтень", max_digits=15, decimal_places=2, default=0)
    nov = models.DecimalField("Листопад", max_digits=15, decimal_places=2, default=0)
    dec = models.DecimalField("Грудень", max_digits=15, decimal_places=2, default=0)

    notes = models.TextField("Примітки", blank=True)

    class Meta:
        verbose_name = "Стаття бюджету"
        verbose_name_plural = "Статті бюджету"
        unique_together = ('budget_period', 'account', 'cost_center')

    def get_total_budget(self):
        """Загальний бюджет за рік"""
        return (self.jan + self.feb + self.mar + self.apr + self.may + self.jun +
                self.jul + self.aug + self.sep + self.oct + self.nov + self.dec)

    def get_month_budget(self, month):
        """Бюджет за конкретний місяць"""
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        return getattr(self, months[month - 1])


class CashFlowForecast(models.Model):
    """Прогноз грошових потоків"""
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    account = models.ForeignKey('settlements.Account', on_delete=models.CASCADE)

    forecast_date = models.DateField("Дата прогнозу")
    amount = models.DecimalField("Сума", max_digits=15, decimal_places=2)

    flow_type = models.CharField("Тип потоку", max_length=20, choices=[
        ('inflow', 'Надходження'),
        ('outflow', 'Витрати')
    ])

    category = models.CharField("Категорія", max_length=50, choices=[
        ('sales', 'Продажі'),
        ('receivables', 'Дебіторка'),
        ('suppliers', 'Постачальники'),
        ('salaries', 'Зарплата'),
        ('taxes', 'Податки'),
        ('loans', 'Кредити'),
        ('investments', 'Інвестиції'),
        ('other', 'Інше')
    ])

    description = models.CharField("Опис", max_length=200)
    probability = models.IntegerField("Ймовірність (%)", default=100)

    # Прив'язка до документів
    document = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True)

    is_actual = models.BooleanField("Фактичний", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Прогноз cashflow"
        verbose_name_plural = "Прогнози cashflow"
        ordering = ['forecast_date']

    def __str__(self):
        return f"{self.forecast_date}: {self.amount} ({self.category})"


class PaymentSchedule(models.Model):
    """Графік платежів"""
    company = models.ForeignKey('Company', on_delete=models.CASCADE)

    # Тип графіку
    schedule_type = models.CharField("Тип", max_length=20, choices=[
        ('receivables', 'Дебіторська заборгованість'),
        ('payables', 'Кредиторська заборгованість'),
        ('loan', 'Кредитні платежі'),
        ('lease', 'Орендні платежі'),
        ('recurring', 'Регулярні платежі')
    ])

    # Деталі
    counterparty_name = models.CharField("Контрагент", max_length=200)
    amount = models.DecimalField("Сума", max_digits=15, decimal_places=2)
    due_date = models.DateField("Дата погашення")

    # Статус
    status = models.CharField("Статус", max_length=20, choices=[
        ('planned', 'Заплановано'),
        ('overdue', 'Прострочено'),
        ('paid', 'Сплачено'),
        ('cancelled', 'Скасовано')
    ], default='planned')

    paid_amount = models.DecimalField("Сплачено", max_digits=15, decimal_places=2, default=0)
    paid_date = models.DateField("Дата оплати", null=True, blank=True)

    # Прив'язки
    document = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True)

    notes = models.TextField("Примітки", blank=True)

    class Meta:
        verbose_name = "Графік платежів"
        verbose_name_plural = "Графіки платежів"
        ordering = ['due_date']

    def __str__(self):
        return f"{self.counterparty_name}: {self.amount} ({self.due_date})"

    def is_overdue(self):
        from django.utils import timezone
        return self.status == 'planned' and self.due_date < timezone.now().date()