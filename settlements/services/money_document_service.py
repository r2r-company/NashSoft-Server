from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from settlements.models import MoneyOperation
from settlements.services.money_ledger_service import create_money_ledger_entry


class MoneyDocumentService:
    def __init__(self, document):
        self.document = document

    def post(self):
        if self.document.status == 'posted':
            raise ValidationError("Документ вже проведено.")

        # ❌ Не треба проводити те, що вже є фактом боргу
        if self.document.doc_type == 'supplier_debt':
            raise ValidationError("Документ боргу вже є фактом. Його не потрібно проводити.")

        with transaction.atomic():
            operations = self.document.moneyoperation_set.all()

            if not operations.exists():
                direction = 'in' if self.document.doc_type.endswith('income') else 'out'
                amount = self.document.amount or Decimal("0.00")

                operation = MoneyOperation.objects.create(
                    document=self.document,
                    account=self.document.account,
                    supplier=self.document.supplier,
                    customer=self.document.customer,
                    source_document=self.document.source_document,
                    amount=amount,
                    direction=direction,
                    visible=True
                )

                create_money_ledger_entry(operation)
            else:
                operations.update(visible=True)

            self.document.status = 'posted'
            self.document.save()
