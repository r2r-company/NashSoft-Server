# services/document_services.py (з повним логуванням)
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Q

from backend.models import Operation, DocumentItem
from backend.operations.stock import FIFOStockManager
from backend.services.validators import DocumentValidator
from backend.services.logger import AuditLoggerService
from backend.utils.unit_converter import convert_to_base
from settlements.models import MoneyOperation, MoneyDocument
from settlements.services.accounting_service import AccountingService
from settlements.services.auto_money_service import AutoMoneyDocumentService


class BaseDocumentService:
    def __init__(self, document):
        self.document = document
        self.logger = AuditLoggerService(document=document)

    def post(self):
        raise NotImplementedError("Method `post` must be implemented.")

    def unpost(self):
        raise NotImplementedError("Method `unpost` must be implemented.")

# 🧾 Вираховує ПДВ на рівні DocumentItem

def apply_vat(item, mode="from_price_without_vat"):
    vat = Decimal(item.vat_percent or 0)
    price = Decimal(item.price)

    if mode == "from_price_with_vat":
        item.price_with_vat = price
        item.vat_amount = round(price * vat / (100 + vat), 2)
        item.price_without_vat = round(price - item.vat_amount, 2)
    else:
        item.price_without_vat = price
        item.vat_amount = round(price * vat / 100, 2)
        item.price_with_vat = round(price + item.vat_amount, 2)

    item.save(update_fields=["price_with_vat", "price_without_vat", "vat_amount", "vat_percent"])




class ReceiptService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted", f"Спроба повторного проведення документа {self.document.doc_number}")
            raise ValidationError("Документ вже проведено.")

        DocumentValidator(self.document).check_can_post()

        # ✅ Перевірка на передоплату
        if self.document.contract and self.document.contract.contract_type == 'Оплата наперед':
            raise ValidationError("Передоплата обовʼязкова згідно з умовами договору.")

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            item.converted_quantity = converted_qty

            if item.price_with_vat and not item.vat_amount:
                apply_vat(item, mode="from_price_with_vat")
            else:
                apply_vat(item)

            item.save(update_fields=["converted_quantity"])

            Operation.objects.create(
                document=self.document,
                product=item.product,
                quantity=converted_qty,
                price=item.price,
                warehouse=self.document.warehouse,
                direction='in',
                visible=True
            )
            self.logger.log_event("receipt_item_posted", f"Надходження: {item.product.name} x {item.quantity}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("receipt_posted", f"Документ {self.document.doc_number} проведено")

        AutoMoneyDocumentService.create_from_document(self.document)

    def unpost(self):
        if self.document.status != 'posted':
            self.logger.log_event("not_posted", f"Спроба розпроведення не проведеного документа {self.document.doc_number}")
            raise ValidationError("Документ ще не проведено, тому розпровести неможливо.")

        DocumentValidator(self.document).check_can_unpost()

        Operation.objects.filter(document=self.document).delete()
        self.logger.log_event("receipt_unposted", f"Операції документа {self.document.doc_number} видалені")

        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("receipt_draft", f"Документ {self.document.doc_number} переведено в чернетку")



class ReturnToSupplierService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise ValidationError("Документ вже проведено.")

        DocumentValidator(self.document).check_can_post()

        source = self.document.source_document
        if not source or source.doc_type != 'receipt':
            raise ValidationError("Потрібно вказати дійсний документ Поступлення як джерело повернення.")

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            apply_vat(item)
            item.converted_quantity = converted_qty
            item.save(update_fields=["converted_quantity"])

            total_received = Operation.objects.filter(
                document=source,
                product=item.product,
                direction='in',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            total_returned = Operation.objects.filter(
                document__doc_type='return_to_supplier',
                document__source_document=source,
                product=item.product,
                direction='out'
            ).aggregate(total=Sum('quantity'))['total'] or 0

            max_returnable = total_received - total_returned

            if item.quantity > max_returnable:
                raise ValidationError([
                    f"Повернення '{item.product.name}' перевищує доступну кількість. Отримано: {total_received}, повернуто: {total_returned}, дозволено: {max_returnable}."
                ])

            Operation.objects.create(
                document=self.document,
                product=item.product,
                quantity=converted_qty,
                price=item.price,
                warehouse=self.document.warehouse,
                direction='out',
                visible=True
            )
            self.logger.log_event("return_supplier_item", f"Повернено постачальнику: {item.product.name} x {item.quantity}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("return_supplier_posted", f"Документ {self.document.doc_number} проведено")

    def unpost(self):
        if self.document.status != 'posted':
            raise ValidationError("Документ ще не проведено, тому розпровести неможливо.")

        DocumentValidator(self.document).check_can_unpost()

        Operation.objects.filter(document=self.document).delete()
        self.logger.log_event("return_supplier_unposted", f"Документ {self.document.doc_number} розпроведено")

        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("return_supplier_draft", f"Документ {self.document.doc_number} переведено в чернетку")


class TransferService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise ValidationError("Документ вже проведено.")

        DocumentValidator(self.document).check_can_post()
        target_warehouse = self.document.target_warehouse

        for item in self.document.items.all():
            stock = FIFOStockManager.get_available_stock(
                product=item.product,
                warehouse=self.document.warehouse,
                firm=self.document.firm  # ⬅️ додано
            )
            if stock < item.quantity:
                raise ValidationError(
                    f"Недостатньо залишку для переміщення: {item.product.name}. Є: {stock}, потрібно: {item.quantity}"
                )

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            apply_vat(item)
            item.converted_quantity = converted_qty
            item.save(update_fields=["converted_quantity"])

            Operation.objects.create(
                document=self.document,
                product=item.product,
                quantity=converted_qty,
                price=item.price,
                warehouse=self.document.warehouse,
                direction='out',
                visible=True
            )
            Operation.objects.create(
                document=self.document,
                product=item.product,
                quantity=converted_qty,
                price=item.price,
                warehouse=target_warehouse,
                direction='in',
                visible=True
            )
            self.logger.log_event("transfer_item", f"Переміщено {item.product.name} x {item.quantity} зі складу {self.document.warehouse.name} до {target_warehouse.name}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("transfer_posted", f"Документ {self.document.doc_number} проведено")

    def unpost(self):
        if self.document.status != 'posted':
            raise ValidationError("Документ ще не проведено, тому розпровести неможливо.")

        DocumentValidator(self.document).check_can_unpost()
        Operation.objects.filter(document=self.document).delete()
        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("transfer_unposted", f"Документ {self.document.doc_number} розпроведено")



class SaleService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise ValidationError("Документ вже проведено.")

        DocumentValidator(self.document).check_can_post()

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            item.converted_quantity = converted_qty

            if item.price_with_vat and not item.vat_amount:
                apply_vat(item, mode="from_price_with_vat")
            else:
                apply_vat(item)

            item.save(update_fields=["converted_quantity"])

            FIFOStockManager.sell_fifo(
                document=self.document,
                product=item.product,
                warehouse=self.document.warehouse,
                quantity=converted_qty,
            )
            self.logger.log_event("sale_item", f"Реалізовано {item.product.name} x {item.quantity}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("sale_posted", f"Документ {self.document.doc_number} проведено")

        AccountingService(self.document).generate_entries()
        AutoMoneyDocumentService.create_from_document(self.document)

    def _auto_create_payment(self):
        payment_type = self.document.payment_type
        if not payment_type or payment_type.name not in ["Готівка", "Безготівка"]:
            return

        doc_type = 'cash_income' if payment_type.name == "Готівка" else 'bank_income'

        from settlements.models import Account
        account = Account.objects.filter(
            company=self.document.company,
            type='cash' if doc_type == 'cash_income' else 'bank'
        ).first()

        if not account:
            return

        amount = sum(item.quantity * item.price for item in self.document.items.all())

        money_doc = MoneyDocument.objects.create(
            doc_type=doc_type,
            company=self.document.company,
            firm=self.document.firm,
            comment=f"Оплата за реалізацію {self.document.doc_number}",
            source_document=self.document,
            customer=self.document.customer,
            account=account,
            amount=amount,
            status='posted'
        )

        MoneyOperation.objects.create(
            document=money_doc,
            amount=amount,
            direction='in',
            account=account,
            source_document=self.document,
            customer=self.document.customer,
            visible=True
        )

        from settlements.models import MoneyLedgerEntry
        MoneyLedgerEntry.objects.create(
            document=money_doc,
            date=money_doc.date,
            debit_account=301,
            credit_account=361,
            amount=amount,
            comment=f"Автопроводка по {money_doc.doc_number}",
            customer=self.document.customer
        )

        self.logger.log_event("auto_payment_created", f"Створено оплату {money_doc.doc_number}")



class ReturnFromClientService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise ValidationError("Документ вже проведено.")

        DocumentValidator(self.document).check_can_post()

        source = self.document.source_document

        if not source or source.doc_type != 'sale':
            raise ValidationError("Потрібно вказати документ реалізації, з якого клієнт повертає товар.")

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            apply_vat(item)
            item.converted_quantity = converted_qty
            item.save(update_fields=["converted_quantity"])

            source_item = source.items.filter(product=item.product).first()
            if not source_item:
                raise ValidationError([f"Товар '{item.product.name}' відсутній у документі реалізації."])

            total_returned = Operation.objects.filter(
                document__doc_type='return_from_client',
                document__source_document=source,
                product=item.product,
                direction='in'
            ).aggregate(total=Sum('quantity'))['total'] or 0

            max_returnable = source_item.quantity - total_returned

            if item.quantity > max_returnable:
                raise ValidationError([
                    f"Повернення '{item.product.name}' перевищує реалізовану кількість. "
                    f"Продано: {source_item.quantity}, вже повернуто: {total_returned}, "
                    f"дозволено: {max_returnable}."
                ])

            Operation.objects.create(
                document=self.document,
                product=item.product,
                quantity=converted_qty,
                price=item.price,
                warehouse=self.document.warehouse,
                direction='in',
                visible=True
            )
            self.logger.log_event("return_client_item", f"Повернення від клієнта: {item.product.name} x {item.quantity}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("return_client_posted", f"Документ {self.document.doc_number} проведено")

    def unpost(self):
        if self.document.status != 'posted':
            raise ValidationError("Документ ще не проведено, тому розпровести неможливо.")

        DocumentValidator(self.document).check_can_unpost()

        Operation.objects.filter(document=self.document).delete()
        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("return_client_unposted", f"Документ {self.document.doc_number} розпроведено")


class InventoryService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise ValidationError("Документ вже проведено.")

        DocumentValidator(self.document).check_can_post()

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            apply_vat(item)
            item.converted_quantity = converted_qty
            item.save(update_fields=["converted_quantity"])

            product = item.product
            warehouse = self.document.warehouse
            firm = self.document.firm

            incoming = Operation.objects.filter(
                product=product,
                warehouse=warehouse,
                document__firm=firm,
                direction='in',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            outgoing = Operation.objects.filter(
                product=product,
                warehouse=warehouse,
                document__firm=firm,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            balance = incoming - outgoing
            diff = converted_qty - balance

            if diff == 0:
                continue

            Operation.objects.create(
                document=self.document,
                product=product,
                quantity=abs(diff),
                price=item.price,
                warehouse=warehouse,
                direction='in' if diff > 0 else 'out',
                visible=True
            )
            self.logger.log_event("inventory_adjustment", f"Інвентаризація: {product.name}, зміна: {diff}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("inventory_posted", f"Документ {self.document.doc_number} проведено")

    def unpost(self):
        if self.document.status != 'posted':
            raise ValidationError("Документ ще не проведено, тому розпровести неможливо.")

        DocumentValidator(self.document).check_can_unpost()

        Operation.objects.filter(document=self.document).delete()
        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("inventory_unposted", f"Документ {self.document.doc_number} розпроведено")




class StockInDocumentService:
    def __init__(self, document):
        self.document = document

    def post(self):
        if self.document.status == 'posted':
            raise ValidationError("Документ вже проведений.")

        with transaction.atomic():
            for item in self.document.items.all():
                converted_qty = convert_to_base(item.product, item.unit, item.quantity)
                apply_vat(item)
                item.converted_quantity = converted_qty
                item.save(update_fields=["converted_quantity"])

                Operation.objects.create(
                    document=self.document,
                    product=item.product,
                    quantity=converted_qty,
                    price=item.price,
                    warehouse=self.document.warehouse,
                    direction='in',
                    visible=True
                )

            self.document.status = 'posted'
            self.document.save()

    def unpost(self):
        if self.document.status != 'posted':
            raise ValidationError("Документ не проведений.")

        with transaction.atomic():
            operations = Operation.objects.filter(document=self.document, direction='in')

            for op in operations:
                used_qty = Operation.objects.filter(
                    source_operation=op,
                    direction='out',
                    visible=True
                ).count()

                if used_qty > 0:
                    raise ValidationError(f"Партія {op.id} вже використана у списанні. Неможливо розпровести.")

            operations.delete()
            self.document.status = 'draft'
            self.document.save()


class ConversionDocumentService:
    def __init__(self, document):
        self.document = document

    def post(self):
        for item in self.document.items.all():
            direction = 'out' if item.role == 'input' else 'in'
            Operation.objects.create(
                document=self.document,
                product=item.product,
                quantity=item.quantity,
                price=item.price,
                warehouse=self.document.warehouse,
                direction=direction,
                visible=True,
            )
        self.document.status = 'posted'
        self.document.save()