from decimal import Decimal
from django.db import models
from backend.models import Company, Firm, Supplier, Customer, Document, PaymentType

MONEY_DOC_TYPES = [
    ('cash_income', 'Надходження готівки'),
    ('bank_income', 'Надходження на рахунок'),
    ('cash_outcome', 'Витрата готівки'),
    ('bank_outcome', 'Витрата з рахунку'),
    ('supplier_debt', 'Борг постачальнику'),
]

ACCOUNT_TYPE_CHOICES = [
    ('cash', 'Готівка'),
    ('bank', 'Банк'),
]

class Account(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES)

    class Meta:
        verbose_name = 'Каса-Банк'
        verbose_name_plural = 'Каси-Банки'


class MoneyDocument(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=30, choices=MONEY_DOC_TYPES)
    doc_number = models.CharField(max_length=50, unique=True, blank=True, null=True)  # ➡️ Додати це поле
    comment = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='draft')  # draft / posted
    date = models.DateTimeField(auto_now_add=True)
    account = models.ForeignKey(
        'settlements.Account',
        on_delete=models.CASCADE,
        verbose_name='Рахунок',
        null=True,
        blank=True
    )
    supplier = models.ForeignKey('backend.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    source_document = models.ForeignKey('backend.Document', on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey('backend.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_without_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_with_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_20 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_7 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_0 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField("Сума до оплати", max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        if not self.doc_number:
            prefix = {
                'cash_income': '801',
                'bank_income': '802',
                'cash_outcome': '803',
                'bank_outcome': '804',
                'supplier_debt': '805',
            }.get(self.doc_type, '899')
            last_doc = MoneyDocument.objects.filter(doc_type=self.doc_type).order_by('-id').first()
            last_number = int(last_doc.doc_number.split('-')[-1]) if last_doc and last_doc.doc_number else 0
            self.doc_number = f"{prefix}-{str(last_number + 1).zfill(5)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_doc_type_display()} #{self.doc_number}"

    class Meta:
        verbose_name = 'Грошовий документ'
        verbose_name_plural = 'Грошові документи'

class MoneyOperation(models.Model):
    document = models.ForeignKey(
        MoneyDocument,
        on_delete=models.CASCADE,
        null=True,  # 🧠 це те, чого не вистачає
        blank=True
    )
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    source_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    direction = models.CharField(max_length=10)  # 'in' або 'out'
    visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Грошова операція'
        verbose_name_plural = 'Грошові операції'



class Contract(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Постачальник')
    client = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Клієнт')
    name = models.CharField(max_length=255, verbose_name='Назва договору', unique=True)
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, verbose_name='Тип оплати')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, verbose_name='Рахунок')
    doc_file = models.FileField(upload_to='contracts/', null=True, blank=True, verbose_name='Файл договору')
    contract_type = models.CharField(
        max_length=50,
        choices=[('partial', 'Оплата частинами'), ('prepaid', 'Оплата наперед')],
        verbose_name='Тип договору'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    status = models.CharField(
        max_length=20,
        choices=[('draft', 'Чернетка'), ('active', 'Діючий'), ('cancelled', 'Скасований')],
        default='draft',
        verbose_name='Статус'
    )

    def save(self, *args, **kwargs):
        if not self.name:
            prefix = 'CTR'
            last = Contract.objects.filter(name__startswith=prefix).order_by('-id').first()
            number = int(last.name.split('-')[-1]) + 1 if last else 1
            self.name = f"{prefix}-{str(number).zfill(5)}"
        super().save(*args, **kwargs)

    def __str__(self):
        side = self.supplier.name if self.supplier else self.client.name
        return f"{self.name} ({side})"

    class Meta:
        verbose_name = "Договір"
        verbose_name_plural = "Договори"



class MoneyLedgerEntry(models.Model):
    document = models.ForeignKey('MoneyDocument', on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    debit_account = models.CharField(max_length=100)   # Код або імʼя рахунку
    credit_account = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    supplier = models.ForeignKey('backend.Supplier', null=True, blank=True, on_delete=models.SET_NULL)
    customer = models.ForeignKey('backend.Customer', null=True, blank=True, on_delete=models.SET_NULL)

    comment = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Проводка"
        verbose_name_plural = "Проводки"

    def __str__(self):
        return f"{self.debit_account} ⬅️ {self.amount} ⬅️ {self.credit_account}"
