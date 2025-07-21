from decimal import Decimal
from settlements.models import MoneyLedgerEntry
from backend.models import Document, get_document_meta


class AccountingService:
    def __init__(self, document: Document):
        self.document = document
        self.meta = get_document_meta(self.document)

    def generate_entries(self):
        if not self.meta or "entries" not in self.meta:
            return

        for entry in self.meta["entries"]:
            debit = entry["debit"]
            credit = entry["credit"]
            amount_attr = entry["amount"]

            # Отримуємо суму (price_without_vat, vat_amount і т.д.)
            amount = getattr(self.document, amount_attr, None)
            if amount is None or Decimal(amount) == 0:
                continue
            print(f"DEBUG: processing doc {self.document.doc_number} | {self.document.doc_type}")
            for item in self.document.items.all():
                print(f"  item: {item.product.name} | no_vat={item.price_without_vat} | vat={item.vat_amount}")

            MoneyLedgerEntry.objects.create(
                document=self.document,
                debit_account=debit,
                credit_account=credit,
                amount=Decimal(amount),
                supplier=getattr(self.document, "supplier", None),
                customer=getattr(self.document, "customer", None),
                comment=f"Проводка по {self.meta.get('label')} #{self.document.doc_number}"
            )
