# services/validators.py (оновлено з логуванням перевірок)
from django.core.exceptions import ValidationError
from django.db.models import  Sum
from backend.models import Operation
from backend.services.logger import AuditLoggerService


class DocumentValidator:
    def __init__(self, document):
        self.document = document
        self.logger = AuditLoggerService(document=document)

    def check_can_post(self):
        method_name = f"_can_post_{self.document.doc_type}"
        method = getattr(self, method_name, None)
        if method:
            self.logger.log_event("check_can_post", f"Запущено перевірку для проведення документа {self.document.doc_type}")
            method()

    def check_can_unpost(self):
        method_name = f"_can_unpost_{self.document.doc_type}"
        method = getattr(self, method_name, None)
        if method:
            self.logger.log_event("check_can_unpost", f"Запущено перевірку для розпроведення документа {self.document.doc_type}")
            method()

    # ====== ПРОВЕДЕННЯ ======
    def _can_post_sale(self):
        for item in self.document.items.all():
            available_qty = self._get_available_quantity(item.product, self.document.warehouse)
            if available_qty < item.quantity:
                self.logger.log_event("fail_post_sale", f"Недостатньо залишку: {item.product.name}, потрібно {item.quantity}, є {available_qty}")
                raise ValidationError(
                    f"Недостатньо залишку для товару '{item.product.name}'. Потрібно {item.quantity}, є {available_qty}"
                )

    def _can_post_return_from_client(self):
        source_doc = self.document.source_document
        for item in self.document.items.all():
            sold_qty = Operation.objects.filter(
                document=source_doc,
                product=item.product,
                direction='out'
            ).aggregate(total=Sum('quantity'))['total'] or 0

            already_returned = Operation.objects.filter(
                document=self.document,
                product=item.product,
                direction='in'
            ).exclude(document=self.document).aggregate(total=Sum('quantity'))['total'] or 0

            if item.quantity + already_returned > sold_qty:
                self.logger.log_event("fail_post_return_client", f"Забагато повертається: {item.product.name}, продано {sold_qty}, повертається {item.quantity + already_returned}")
                raise ValidationError(f"Товар '{item.product.name}' повертається у кількості більше ніж було продано")

    def _can_post_return_to_supplier(self):
        source_doc = self.document.source_document
        for item in self.document.items.all():
            received_qty = Operation.objects.filter(
                document=source_doc,
                product=item.product,
                direction='in'
            ).aggregate(total=Sum('quantity'))['total'] or 0

            already_returned = Operation.objects.filter(
                document=self.document,
                product=item.product,
                direction='out'
            ).exclude(document=self.document).aggregate(total=Sum('quantity'))['total'] or 0

            if item.quantity + already_returned > received_qty:
                self.logger.log_event("fail_post_return_supplier", f"Забагато повертається постачальнику: {item.product.name}, отримано {received_qty}, повертається {item.quantity + already_returned}")
                raise ValidationError(f"Товар '{item.product.name}' повертається більше ніж було отримано")

    def _can_post_transfer(self):
        for item in self.document.items.all():
            available_qty = self._get_available_quantity(item.product, self.document.warehouse)
            if available_qty < item.quantity:
                self.logger.log_event("fail_post_transfer", f"Недостатньо товару для переміщення: {item.product.name}, є {available_qty}, потрібно {item.quantity}")
                raise ValidationError(
                    f"Недостатньо товару на складі для переміщення '{item.product.name}'"
                )

    # ====== РОЗПРОВЕДЕННЯ ======
    def _can_unpost_receipt(self):
        used_ops = Operation.objects.filter(source_operation__document=self.document, visible=True)
        if used_ops.exists():
            self.logger.log_event("fail_unpost_receipt", "Товар вже використано в інших документах")
            raise ValidationError("Неможливо розпровести: товар уже використано в інших документах")

    def _can_unpost_sale(self):
        used_in_return = Operation.objects.filter(
            source_operation__document=self.document,
            direction='in',
            visible=True
        )
        if used_in_return.exists():
            self.logger.log_event("fail_unpost_sale", "Є повернення від клієнта")
            raise ValidationError("Неможливо розпровести: є повернення від клієнта")

    def _can_unpost_return_from_client(self):
        used_ops = Operation.objects.filter(source_operation__document=self.document, visible=True)
        if used_ops.exists():
            self.logger.log_event("fail_unpost_return_client", "Повернутий товар вже використаний")
            raise ValidationError("Неможливо розпровести: повернутий товар вже використаний")

    def _can_unpost_return_to_supplier(self):
        used_ops = Operation.objects.filter(source_operation__document=self.document, visible=True)
        if used_ops.exists():
            self.logger.log_event("fail_unpost_return_supplier", "Товар вже був реалізований або переміщений")
            raise ValidationError("Неможливо розпровести: товар вже був реалізований або переміщений")

    def _can_unpost_transfer(self):
        used_ops = Operation.objects.filter(
            source_operation__document=self.document,
            visible=True
        )
        if used_ops.exists():
            self.logger.log_event("fail_unpost_transfer", "Товар з переміщення вже використано")
            raise ValidationError("Неможливо розпровести: товар з переміщення вже використано")

    def _get_available_quantity(self, product, warehouse):
        total_in = Operation.objects.filter(product=product, warehouse=warehouse, direction='in', visible=True).aggregate(
            total=Sum('quantity'))['total'] or 0
        total_out = Operation.objects.filter(product=product, warehouse=warehouse, direction='out', visible=True).aggregate(
            total=Sum('quantity'))['total'] or 0
        return total_in - total_out
