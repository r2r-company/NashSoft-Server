from collections import defaultdict
from django.db import transaction
from backend.models import Product, Warehouse, Document, DocumentItem
from kkm.models import CashShift, ReceiptItemBuffer, FiscalReceipt, ReceiptOperation
from kkm.service.kkm.stock import get_available_stock_for_sale


class MultiFirmReceiptBuilderService:
    def __init__(self, shift: CashShift):
        self.shift = shift
        self.company = shift.company

    @transaction.atomic
    def build_receipts(self, items: list):
        """
        items: [
            {"product_id": int, "quantity": float, "price": float, "warehouse_id": int},
            ...
        ]
        """
        grouped = defaultdict(list)

        # 🔁 Очистка старого буфера перед створенням нових чеків
        ReceiptItemBuffer.objects.filter(shift=self.shift).delete()

        # 1. Групуємо товари по фірмах
        for item in items:
            product = Product.objects.get(id=item["product_id"])
            warehouse = Warehouse.objects.get(id=item["warehouse_id"])
            firm = product.firm

            # Перевірка залишку по фірмі (FIFO + буфер)
            available = get_available_stock_for_sale(product, warehouse, self.shift)
            if available < item["quantity"]:
                raise Exception(f"Недостатньо залишку для товару '{product.name}' (фірма: {firm.name})")

            grouped[firm].append({
                "product": product,
                "quantity": item["quantity"],
                "price": item["price"],
                "warehouse": warehouse
            })

        receipts = []

        # 2. Створюємо окремий чек + документ реалізації для кожної фірми
        for firm, firm_items in grouped.items():
            receipt = FiscalReceipt.objects.create(
                shift=self.shift,
                company=self.company,
                firm=firm,
                status='success',
                fiscal_number=f"TEST-{firm.name[:3].upper()}-{self.shift.id}-{len(receipts) + 1}"
            )

            doc = Document.objects.create(
                doc_type='sale',
                company=self.company,
                firm=firm,
                warehouse=firm_items[0]["warehouse"],
                shift=self.shift,
                status='draft'  # ❗ не проводимо документ одразу
            )

            for item in firm_items:
                # Буфер
                ReceiptItemBuffer.objects.create(
                    shift=self.shift,
                    product=item["product"],
                    quantity=item["quantity"],
                    price=item["price"],
                    warehouse=item["warehouse"],
                    firm=firm
                )

                # Операції чека
                ReceiptOperation.objects.create(
                    receipt=receipt,
                    product=item["product"],
                    quantity=item["quantity"],
                    price=item["price"],
                    warehouse=item["warehouse"]
                )

                # Позиції документа
                DocumentItem.objects.create(
                    document=doc,
                    product=item["product"],
                    quantity=item["quantity"],
                    price=item["price"]
                )

            receipts.append(receipt)

        return receipts
