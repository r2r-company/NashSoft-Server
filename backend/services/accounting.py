from django.db import transaction

from backend.models import ChartOfAccounts, AccountingEntry


class AccountingService:
    """Сервіс для автоматичних бухгалтерських проводок"""

    def __init__(self, document):
        self.document = document

    def create_entries(self):
        """Створення проводок залежно від типу документа"""
        if self.document.doc_type == 'receipt':
            return self._create_receipt_entries()
        elif self.document.doc_type == 'sale':
            return self._create_sale_entries()
        elif self.document.doc_type == 'payment_to_supplier':
            return self._create_supplier_payment_entries()
        elif self.document.doc_type == 'payment_from_customer':
            return self._create_customer_payment_entries()

    def _create_receipt_entries(self):
        """Проводки поступлення товару"""
        entries = []

        with transaction.atomic():
            for item in self.document.items.all():
                # Дт 281 (Товари) - Кт 631 (Розрахунки з постачальниками)
                entry = AccountingEntry.objects.create(
                    date=self.document.date,
                    document=self.document,
                    debit_account=ChartOfAccounts.objects.get(code='281'),
                    credit_account=ChartOfAccounts.objects.get(code='631'),
                    amount=item.total_amount,
                    description=f"Поступлення: {item.product.name}",
                    supplier=self.document.supplier,
                    product=item.product
                )
                entries.append(entry)

                # ПДВ: Дт 644 (ПДВ до відшкодування) - Кт 631
                if item.vat_amount:
                    vat_entry = AccountingEntry.objects.create(
                        date=self.document.date,
                        document=self.document,
                        debit_account=ChartOfAccounts.objects.get(code='644'),
                        credit_account=ChartOfAccounts.objects.get(code='631'),
                        amount=item.vat_amount,
                        description=f"ПДВ поступлення: {item.product.name}",
                        supplier=self.document.supplier
                    )
                    entries.append(vat_entry)

        return entries

    def _create_sale_entries(self):
        """Проводки продажу"""
        entries = []

        with transaction.atomic():
            for item in self.document.items.all():
                # Дт 361 (Розрахунки з покупцями) - Кт 701 (Дохід від реалізації)
                sale_entry = AccountingEntry.objects.create(
                    date=self.document.date,
                    document=self.document,
                    debit_account=ChartOfAccounts.objects.get(code='361'),
                    credit_account=ChartOfAccounts.objects.get(code='701'),
                    amount=item.price_without_vat,
                    description=f"Реалізація: {item.product.name}",
                    customer=self.document.customer,
                    product=item.product
                )
                entries.append(sale_entry)

                # ПДВ: Дт 361 - Кт 641 (ПДВ зобов'язання)
                if item.vat_amount:
                    vat_entry = AccountingEntry.objects.create(
                        date=self.document.date,
                        document=self.document,
                        debit_account=ChartOfAccounts.objects.get(code='361'),
                        credit_account=ChartOfAccounts.objects.get(code='641'),
                        amount=item.vat_amount,
                        description=f"ПДВ реалізації: {item.product.name}",
                        customer=self.document.customer
                    )
                    entries.append(vat_entry)

                # Собівартість: Дт 902 (Собівартість) - Кт 281 (Товари)
                cost_entry = AccountingEntry.objects.create(
                    date=self.document.date,
                    document=self.document,
                    debit_account=ChartOfAccounts.objects.get(code='902'),
                    credit_account=ChartOfAccounts.objects.get(code='281'),
                    amount=item.quantity * item.product.cost_price,
                    description=f"Собівартість: {item.product.name}",
                    product=item.product
                )
                entries.append(cost_entry)

        return entries