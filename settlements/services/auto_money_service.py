from decimal import Decimal
from django.db import transaction
from django.utils.timezone import make_aware
from datetime import datetime, time

from settlements.models import MoneyDocument, MoneyLedgerEntry, MoneyOperation
from backend.models import DocumentItem


class AutoMoneyDocumentService:
    @staticmethod
    @transaction.atomic
    def create_from_document(document):
        if document.doc_type not in ["receipt", "sale"]:
            return

        items = DocumentItem.objects.filter(document=document)

        total_without_vat = Decimal("0.00")
        total_vat = Decimal("0.00")

        for item in items:
            total_without_vat += item.price_without_vat or 0
            total_vat += item.vat_amount or 0

        total_with_vat = total_without_vat + total_vat
        if total_with_vat <= 0:
            return

        # Параметри по типу документа
        if document.doc_type == "receipt":
            doc_type = "supplier_debt"
            direction = "in"
            counterparty = {"supplier": document.supplier}
            comment = f"Борг постачальнику за {document.doc_number}"
        else:
            doc_type = "client_debt"
            direction = "out"
            counterparty = {"customer": document.customer}
            comment = f"Борг клієнта за {document.doc_number}"

        # Обробка дати
        dt = document.date if isinstance(document.date, datetime) else make_aware(
            datetime.combine(document.date, time.min))

        # 📄 Створення грошового документа
        debt_doc = MoneyDocument.objects.create(
            doc_type=doc_type,
            company=document.company,
            firm=document.firm,
            source_document=document,
            amount=total_with_vat,
            total_without_vat=total_without_vat,
            total_with_vat=total_with_vat,
            vat_amount=total_vat,
            vat_20=0,
            vat_7=0,
            vat_0=0,
            comment=comment,
            date=dt,
            status="posted",
            **counterparty
        )

        # 🧾 Проводки по кожному рядку
        for item in items:
            price_no_vat = item.price_without_vat or 0
            vat_amount = item.vat_amount or 0

            if document.doc_type == "receipt":
                # 281 / 631 на суму без ПДВ
                MoneyLedgerEntry.objects.create(
                    document=debt_doc,
                    date=dt,
                    debit_account="281",
                    credit_account="631",
                    amount=price_no_vat,
                    comment=f"{item.product.name} (собівартість) по {document.doc_number}",
                    ** counterparty
                )
                # 644 / 631 на суму ПДВ
                if vat_amount > 0:
                    MoneyLedgerEntry.objects.create(
                        document=debt_doc,
                        date=dt,
                        debit_account="644",
                        credit_account="631",
                        amount=vat_amount,
                        comment=f"ПДВ по {item.product.name} ({document.doc_number})",
                        **counterparty
                    )
            else:  # sale
                # 361 / 701 на суму без ПДВ
                MoneyLedgerEntry.objects.create(
                    document=debt_doc,
                    date=dt,
                    debit_account="281",
                    credit_account="631",
                    amount=price_no_vat,
                    comment=f"{item.product.name} (собівартість) по {document.doc_number}",
                    **counterparty
                )
                # 361 / 641 на суму ПДВ
                if vat_amount > 0:
                    MoneyLedgerEntry.objects.create(
                        document=debt_doc,
                        date=dt,
                        debit_account="361",
                        credit_account="641",
                        amount=vat_amount,
                        comment=f"ПДВ по {item.product.name} ({document.doc_number})",
                        **counterparty
                    )

        # 💸 Грошова операція
        MoneyOperation.objects.create(
            document=debt_doc,
            source_document=document,
            amount=total_with_vat,
            direction=direction,
            visible=True,
            **counterparty
        )
