# services/document_services.py (з повним логуванням)
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q

from backend.exceptions import (
    InsufficientStockError,
    DocumentAlreadyPostedException,
    DocumentNotPostedException,
    ValidationError,
    InvalidDocumentTypeError,
    InvalidReturnQuantityError,
    MissingSourceDocumentError,
    ConversionValidationError
)
from backend.services.logger import AuditLoggerService, PerformanceLogger

from backend.models import Operation
from backend.operations.stock import FIFOStockManager
from backend.services.validators import DocumentValidator
from backend.services.logger import AuditLoggerService
from backend.utils.unit_converter import convert_to_base
from settlements.models import MoneyOperation, MoneyDocument
from settlements.services.accounting_service import AccountingService
from settlements.services.auto_money_service import AutoMoneyDocumentService


class BaseDocumentService:
    def __init__(self, document, request=None):
        self.document = document
        # Створюємо розширений logger
        if request:
            self.logger = AuditLoggerService.create_from_request(request, document=document)
        else:
            self.logger = AuditLoggerService(document=document)

    def post(self):
        raise NotImplementedError("Method `post` must be implemented.")

    def unpost(self):
        raise NotImplementedError("Method `unpost` must be implemented.")

# 🧾 Вираховує ПДВ на рівні DocumentItem

def apply_vat(item, mode="from_price_with_vat"):
    """
    ВИПРАВЛЕНА функція застосування ПДВ
    mode:
    - "from_price_with_vat" - ціна включає ПДВ (розділяємо)
    - "from_price_without_vat" - ціна без ПДВ (додаємо ПДВ)
    """
    from backend.models import AccountingSettings

    # Перевіряємо тип фірми
    firm = item.document.firm

    # ФОП не платить ПДВ
    if firm.vat_type == 'ФОП':
        item.vat_percent = 0
        item.vat_amount = 0
        item.price_without_vat = item.price
        item.price_with_vat = item.price
        item.save(update_fields=["price_with_vat", "price_without_vat", "vat_amount", "vat_percent"])
        return

    # ТОВ/ТЗОВ/ПАТ платять ПДВ
    if item.vat_percent is not None:
        vat_rate = Decimal(item.vat_percent)
    else:
        try:
            settings = AccountingSettings.objects.get(company=item.document.company)
            vat_rate = settings.default_vat_rate
            item.vat_percent = vat_rate
        except AccountingSettings.DoesNotExist:
            vat_rate = Decimal(20)
            item.vat_percent = vat_rate

    price = Decimal(item.price)

    if mode == "from_price_with_vat":
        # Ціна ВКЛЮЧАЄ ПДВ - розділяємо
        item.price_with_vat = price
        item.vat_amount = round(price * vat_rate / (100 + vat_rate), 2)
        item.price_without_vat = round(price - item.vat_amount, 2)
    else:
        # Ціна БЕЗ ПДВ - додаємо ПДВ
        item.price_without_vat = price
        item.vat_amount = round(price * vat_rate / 100, 2)
        item.price_with_vat = round(price + item.vat_amount, 2)

    item.save(update_fields=["price_with_vat", "price_without_vat", "vat_amount", "vat_percent"])


class ReceiptService(BaseDocumentService):
    def post(self):
        try:
            if self.document.status == 'posted':
                self.logger.log_business_logic_error(
                    "receipt_already_posted",
                    "Спроба повторного проведення документа",
                    {"doc_number": self.document.doc_number, "current_status": self.document.status}
                )
                raise DocumentAlreadyPostedException()

            DocumentValidator(self.document).check_can_post()

            # ✅ Перевірка на передоплату
            if self.document.contract and self.document.contract.contract_type == 'Оплата наперед':
                self.logger.log_business_logic_error(
                    "prepayment_required",
                    "Передоплата обов'язкова згідно з умовами договору",
                    {"contract_id": self.document.contract.id,
                     "contract_type": self.document.contract.contract_type}
                )
                raise ValidationError("Передоплата обовʼязкова згідно з умовами договору.")

            for item in self.document.items.all():
                converted_qty = convert_to_base(item.product, item.unit, item.quantity)
                item.converted_quantity = converted_qty

                if item.price_with_vat and not item.vat_amount:
                    apply_vat(item, mode="from_price_with_vat")
                else:
                    apply_vat(item)

                item.save(update_fields=["converted_quantity"])

                # ⬇️ НОВА ЛОГІКА: собівартість = ціна закупки
                Operation.objects.create(
                    document=self.document,
                    product=item.product,
                    quantity=converted_qty,
                    cost_price=item.price_without_vat,  # ⬅️ Собівартість = ціна закупки без ПДВ
                    price=item.price_without_vat,       # ⬅️ Для сумісності
                    warehouse=self.document.warehouse,
                    direction='in',
                    visible=True
                )
                self.logger.log_event("receipt_item_posted",
                    f"Надходження: {item.product.name} x {item.quantity} по собівартості {item.price_without_vat}")

            self.document.status = 'posted'
            self.document.save()
            self.logger.log_event("receipt_posted", f"Документ {self.document.doc_number} проведено")

            AutoMoneyDocumentService.create_from_document(self.document)

        except Exception as e:
            self.logger.log_error("receipt_posting_failed", e, {
                "doc_id": self.document.id,
                "doc_number": self.document.doc_number,
                "items_count": self.document.items.count()
            })
            raise

    def unpost(self):
        try:
            if self.document.status != 'posted':
                self.logger.log_business_logic_error(
                    "document_not_posted",
                    "Спроба розпроведення не проведеного документа",
                    {"doc_number": self.document.doc_number, "current_status": self.document.status}
                )
                raise DocumentNotPostedException()

            DocumentValidator(self.document).check_can_unpost()

            Operation.objects.filter(document=self.document).delete()
            self.logger.log_event("receipt_unposted", f"Операції документа {self.document.doc_number} видалені")

            self.document.status = 'draft'
            self.document.save()
            self.logger.log_event("receipt_draft", f"Документ {self.document.doc_number} переведено в чернетку")

        except Exception as e:
            self.logger.log_error("receipt_unposting_failed", e, {
                "doc_id": self.document.id,
                "doc_number": self.document.doc_number
            })
            raise


class ReturnToSupplierService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise DocumentAlreadyPostedException()

        DocumentValidator(self.document).check_can_post()

        source = self.document.source_document
        if not source or source.doc_type != 'receipt':
            raise MissingSourceDocumentError("Потрібно вказати дійсний документ Поступлення як джерело повернення.")

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
                raise InvalidReturnQuantityError(
                    f"Повернення '{item.product.name}' перевищує доступну кількість. Отримано: {total_received}, повернуто: {total_returned}, дозволено: {max_returnable}."
                )

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
            raise DocumentNotPostedException()

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
            raise DocumentAlreadyPostedException()

        DocumentValidator(self.document).check_can_post()
        target_warehouse = self.document.target_warehouse

        for item in self.document.items.all():
            stock = FIFOStockManager.get_available_stock(
                product=item.product,
                warehouse=self.document.warehouse,
                firm=self.document.firm  # ⬅️ додано
            )
            if stock < item.quantity:
                raise InsufficientStockError(
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
            raise DocumentNotPostedException()

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
            raise DocumentAlreadyPostedException()

        DocumentValidator(self.document).check_can_post()

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            item.converted_quantity = converted_qty

            if item.price_with_vat and not item.vat_amount:
                apply_vat(item, mode="from_price_with_vat")
            else:
                apply_vat(item)

            item.save(update_fields=["converted_quantity"])

            # ⬇️ НОВА ЛОГІКА: FIFO з роздільними цінами
            total_cost = FIFOStockManager.sell_fifo(
                document=self.document,
                product=item.product,
                warehouse=self.document.warehouse,
                quantity=converted_qty,
                sale_price=item.price_without_vat  # ⬅️ Передаємо ціну продажу
            )

            # Рахуємо прибуток
            total_sale = item.price_without_vat * converted_qty
            profit = total_sale - total_cost

            self.logger.log_event("sale_item",
                                  f"Реалізовано {item.product.name} x {item.quantity}. "
                                  f"Продажі: {total_sale}, Собівартість: {total_cost}, Прибуток: {profit}")

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
            raise DocumentAlreadyPostedException()

        DocumentValidator(self.document).check_can_post()

        source = self.document.source_document

        if not source or source.doc_type != 'sale':
            raise MissingSourceDocumentError("Потрібно вказати документ реалізації, з якого клієнт повертає товар.")

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            apply_vat(item)
            item.converted_quantity = converted_qty
            item.save(update_fields=["converted_quantity"])

            source_item = source.items.filter(product=item.product).first()
            if not source_item:
                raise ValidationError(f"Товар '{item.product.name}' відсутній у документі реалізації.")

            total_returned = Operation.objects.filter(
                document__doc_type='return_from_client',
                document__source_document=source,
                product=item.product,
                direction='in'
            ).aggregate(total=Sum('quantity'))['total'] or 0

            max_returnable = source_item.quantity - total_returned

            if item.quantity > max_returnable:
                raise InvalidReturnQuantityError(
                    f"Повернення '{item.product.name}' перевищує реалізовану кількість. "
                    f"Продано: {source_item.quantity}, вже повернуто: {total_returned}, "
                    f"дозволено: {max_returnable}."
                )

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
            raise DocumentNotPostedException()

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
            raise DocumentAlreadyPostedException()

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
            raise DocumentNotPostedException()

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
            raise DocumentAlreadyPostedException()

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


class ConversionDocumentService(BaseDocumentService):
    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise DocumentAlreadyPostedException()

        DocumentValidator(self.document).check_can_post()

        # ✅ Валідація наявності source і target товарів
        source_items = self.document.items.filter(role='source')
        target_items = self.document.items.filter(role='target')

        if not source_items.exists():
            raise ConversionValidationError("Документ фасування повинен містити хоча б один товар-джерело (source)")

        if not target_items.exists():
            raise ConversionValidationError("Документ фасування повинен містити хоча б один товар-результат (target)")

        # ✅ Перевірка залишків для source товарів
        for item in source_items:
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)
            stock = FIFOStockManager.get_available_stock(
                product=item.product,
                warehouse=self.document.warehouse,
                firm=self.document.firm
            )
            if stock < converted_qty:
                raise InsufficientStockError(
                    f"Недостатньо залишку для фасування товару '{item.product.name}'. "
                    f"Є: {stock}, потрібно: {converted_qty}"
                )

        with transaction.atomic():
            # ⬇️ НОВА ЛОГІКА ФАСУВАННЯ З СОБІВАРТІСТЮ
            total_source_cost = Decimal('0')
            total_target_quantity = Decimal('0')

            # 1️⃣ Спочатку рахуємо загальну собівартість source товарів
            for item in source_items:
                converted_qty = convert_to_base(item.product, item.unit, item.quantity)

                # Отримуємо собівартість для цієї кількості
                item_cost = FIFOStockManager.get_cost_price_for_quantity(
                    item.product, self.document.warehouse, self.document.firm, converted_qty
                )

                total_source_cost += item_cost * converted_qty

                self.logger.log_event("conversion_source_calculated",
                                      f"Source товар {item.product.name}: кількість {converted_qty}, собівартість {item_cost}")

            # 2️⃣ Рахуємо загальну кількість target товарів
            for item in target_items:
                converted_qty = convert_to_base(item.product, item.unit, item.quantity)
                total_target_quantity += converted_qty

            # 3️⃣ Розраховуємо собівартість одиниці target товару
            if total_target_quantity > 0:
                target_unit_cost = total_source_cost / total_target_quantity
            else:
                raise ConversionValidationError("Загальна кількість target товарів не може бути 0")

            # 4️⃣ Списуємо source товари по FIFO
            for item in source_items:
                converted_qty = convert_to_base(item.product, item.unit, item.quantity)
                apply_vat(item)
                item.converted_quantity = converted_qty
                item.save(update_fields=["converted_quantity"])

                # Списуємо через FIFO (створює операції списання)
                FIFOStockManager.sell_fifo(
                    document=self.document,
                    product=item.product,
                    warehouse=self.document.warehouse,
                    quantity=converted_qty
                )

            # 5️⃣ Оприбутковуємо target товари з розрахованою собівартістю
            for item in target_items:
                converted_qty = convert_to_base(item.product, item.unit, item.quantity)
                apply_vat(item)
                item.converted_quantity = converted_qty
                item.save(update_fields=["converted_quantity"])

                Operation.objects.create(
                    document=self.document,
                    product=item.product,
                    quantity=converted_qty,
                    cost_price=target_unit_cost,  # ⬅️ Розрахована собівартість
                    price=target_unit_cost,  # ⬅️ Для сумісності
                    warehouse=self.document.warehouse,
                    direction='in',
                    visible=True
                )

            self.document.status = 'posted'
            self.document.save()

            self.logger.log_event("conversion_posted",
                                  f"Фасування {self.document.doc_number} проведено. "
                                  f"Загальна собівартість source: {total_source_cost}, "
                                  f"Собівартість одиниці target: {target_unit_cost}")

    def unpost(self):
        if self.document.status != 'posted':
            raise DocumentNotPostedException()

        DocumentValidator(self.document).check_can_unpost()
        Operation.objects.filter(document=self.document).delete()
        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("conversion_unposted", f"Фасування {self.document.doc_number} розпроведено")


class InventoryInService(BaseDocumentService):
    """Сервіс оприбуткування товарів"""

    def post(self):
        if self.document.status == 'posted':
            self.logger.log_event("already_posted",
                                  f"Спроба повторного проведення документа {self.document.doc_number}")
            raise DocumentAlreadyPostedException()

        DocumentValidator(self.document).check_can_post()

        for item in self.document.items.all():
            converted_qty = convert_to_base(item.product, item.unit, item.quantity)

            if item.price_with_vat and not item.vat_amount:
                apply_vat(item, mode="from_price_with_vat")
            else:
                apply_vat(item)

            item.converted_quantity = converted_qty
            item.save(update_fields=["converted_quantity"])

            # Створюємо операцію оприбуткування
            Operation.objects.create(
                document=self.document,
                product=item.product,
                warehouse=self.document.warehouse,
                direction='in',
                quantity=converted_qty,
                cost_price=item.price_without_vat or item.price,
                total_cost=(item.price_without_vat or item.price) * converted_qty,
                price=item.price_without_vat or item.price,  # Для сумісності
                visible=True
            )

            self.logger.log_event("inventory_in_item",
                                  f"Оприбуткування: {item.product.name} x {item.quantity} по собівартості {item.price_without_vat or item.price}")

        self.document.status = 'posted'
        self.document.save()
        self.logger.log_event("inventory_in_posted", f"Документ {self.document.doc_number} проведено")

    def unpost(self):
        if self.document.status != 'posted':
            raise DocumentNotPostedException()

        DocumentValidator(self.document).check_can_unpost()

        Operation.objects.filter(document=self.document).delete()

        self.document.status = 'draft'
        self.document.save()
        self.logger.log_event("inventory_in_unposted", f"Документ {self.document.doc_number} розпроведено")