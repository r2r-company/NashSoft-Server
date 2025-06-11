from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.db.models import Max
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.contrib.postgres.fields import ArrayField

DOC_TYPE_CODES = {
    'receipt': '703',
    'sale': '704',
    'return_to_supplier': '705',
    'return_from_client': '706',
    'transfer': '707',
    'inventory': '708',
    'stock_in': '709',
    'conversion': '710',

}


# ========== ДОВІДНИКИ ==========

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
    vat_type = models.CharField(max_length=20, choices=[('ФОП', 'ФОП'), ('ТЗОВ', 'ТЗОВ'), ('ТОВ', 'ТОВ')])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Фірма'
        verbose_name_plural = 'Фірма'


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
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, verbose_name=_('Одиниця виміру'))
    group = models.ForeignKey('ProductGroup', null=True, blank=True, on_delete=models.SET_NULL,
                              verbose_name=_('Група товару'))
    firm = models.ForeignKey("Firm", on_delete=models.CASCADE, verbose_name="Фірма-власник")
    type = models.CharField(_('Тип'), max_length=20, choices=PRODUCT_TYPES, default='product')

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
    calculation = models.ForeignKey(ProductCalculation, on_delete=models.CASCADE, related_name='items',
                                    verbose_name='Калькуляція')
    component = models.ForeignKey(Product, on_delete=models.CASCADE,
                                  verbose_name='Компонент (інгредієнт або напівфабрикат)')
    quantity = models.DecimalField(_('Кількість'), max_digits=10, decimal_places=3)
    loss_percent = models.DecimalField(_('Втрати при обробці (%)'), max_digits=5, decimal_places=2, default=0)
    cooking_loss_percent = models.DecimalField(_('Втрати при термообробці (%)'), max_digits=5, decimal_places=2,
                                               default=0)
    note = models.CharField(_('Примітка'), max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Компонент калькуляції'
        verbose_name_plural = 'Компоненти калькуляції'

    def __str__(self):
        return f"{self.component.name} x {self.quantity}"


class ProductUnitConversion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    from_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="from_conversions", verbose_name="З од.")
    to_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="to_conversions", verbose_name="В од.")
    factor = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Фактор конвертації")

    class Meta:
        unique_together = ('product', 'from_unit', 'to_unit')
        verbose_name = "Конвертація одиниць"
        verbose_name_plural = "Конвертації одиниць"

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


DOCUMENT_META = {
    "receipt": {
        "prefix": "703",
        "entries": [
            {"debit": "281", "credit": "631", "amount": "price_without_vat"},
            {"debit": "644", "credit": "631", "amount": "vat_amount"},
        ],
    },
    "sale": {
        "prefix": "704",
        "entries": [
            {"debit": "361", "credit": "701", "amount": "price_without_vat"},
            {"debit": "361", "credit": "641", "amount": "vat_amount"},
        ],
    },
    "return_to_supplier": {
        "prefix": "RTS",
        "entries": [
            {"debit": "631", "credit": "281", "amount": "price_without_vat"},
            {"debit": "631", "credit": "644", "amount": "vat_amount"},
        ],
    },

    "return_from_client": {
        "prefix": "RFC",
        "entries": [
            {"debit": "281", "credit": "361", "amount": "price_without_vat"},
            {"debit": "641", "credit": "361", "amount": "vat_amount"},
        ],
    },

    "transfer": {
        "prefix": "TRF",
        "entries": [
            {"debit": "281", "credit": "281", "amount": "price_without_vat"},  # умовно, якщо сума відома
        ],
    },

    "inventory": {
        "prefix": "INV",
        "entries": [],  # бо це внутрішній документ, бухпроводок може не бути
    },

    "stock_in": {
        "prefix": "STI",
        "entries": [
            {"debit": "281", "credit": "719", "amount": "price_without_vat"},
        ],
    },
}


# ========== ДОКУМЕНТИ ==========

class Document(models.Model):
    DOC_TYPES = [
        ('receipt', _('Поступлення')),
        ('sale', _('Реалізація')),
        ('return_from_client', _('Повернення від клієнта')),
        ('return_to_supplier', _('Повернення постачальнику')),
        ('transfer', _('Переміщення')),
        ('inventory', _('Інвентаризація')),
        ('stock_in', _('Оприбуткування')),
        ('conversion', 'Фасування'),

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
        return DOCUMENT_META.get(self.doc_type, {}).get("prefix", "DOC")

    def get_accounting_entry(self):
        meta = DOCUMENT_META.get(self.doc_type, {})
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
    price = models.DecimalField(_('Ціна'), max_digits=10, decimal_places=2)
    source_operation = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                         verbose_name=_('Партія'))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name=_('Склад'))
    visible = models.BooleanField(_('Видимий залишок'), default=True)
    direction = models.CharField(_('Напрямок'), max_length=10)  # in/out
    created_at = models.DateTimeField(_('Створено'), auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Операція'
        verbose_name_plural = 'Операції'

    def __str__(self):
        return f"{self.direction.upper()} {self.product.name} x {self.quantity}"


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


from backend.models import Firm  # якщо ще не імпортнув


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


class PriceSettingItem(models.Model):
    price_setting_document = models.ForeignKey(PriceSettingDocument, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price_type = models.ForeignKey(PriceType, on_delete=models.CASCADE, default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    vat_included = models.BooleanField(default=True)
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    price_without_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source_item = models.ForeignKey('DocumentItem', on_delete=models.SET_NULL, null=True, blank=True)
    trade_point = models.ForeignKey(TradePoint, on_delete=models.CASCADE)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name="Одиниця ціни", null=True, blank=True)
    unit_conversion = models.ForeignKey(ProductUnitConversion, on_delete=models.PROTECT, null=True, blank=True)

    def calculate_price(self):
        if not self.vat_percent:
            self.vat_percent = self.product.vat_rate or 0

        if self.vat_included:
            self.price_without_vat = round(self.price / (1 + self.vat_percent / 100), 2)
            self.vat_amount = round(self.price - self.price_without_vat, 2)
        else:
            self.price_without_vat = self.price
            self.vat_amount = round(self.price * self.vat_percent / 100, 2)
            self.price = self.price_without_vat + self.vat_amount

    class Meta:
        unique_together = ('price_setting_document', 'product', 'price_type', 'trade_point')


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
