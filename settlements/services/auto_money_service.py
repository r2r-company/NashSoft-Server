from decimal import Decimal
from django.db import transaction
from django.utils.timezone import make_aware
from datetime import datetime, time

from settlements.models import MoneyDocument, MoneyLedgerEntry, MoneyOperation
from backend.models import DocumentItem, AccountingSettings


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

       # Отримуємо налаштування рахунків
       try:
           settings = AccountingSettings.objects.get(company=document.company)
       except AccountingSettings.DoesNotExist:
           # Фолбек на старі значення
           settings = type('obj', (object,), {
               'stock_account': '281', 'supplier_account': '631', 'vat_input_account': '644',
               'client_account': '361', 'revenue_account': '701', 'vat_output_account': '641'
           })()

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
               # Дт281 Кт631 на суму без ПДВ
               MoneyLedgerEntry.objects.create(
                   document=debt_doc,
                   date=dt,
                   debit_account=settings.stock_account,
                   credit_account=settings.supplier_account,
                   amount=price_no_vat,
                   comment=f"{item.product.name} (собівартість) по {document.doc_number}",
                   **counterparty
               )
               # Дт644 Кт631 на суму ПДВ
               if vat_amount > 0:
                   MoneyLedgerEntry.objects.create(
                       document=debt_doc,
                       date=dt,
                       debit_account=settings.vat_input_account,
                       credit_account=settings.supplier_account,
                       amount=vat_amount,
                       comment=f"ПДВ по {item.product.name} ({document.doc_number})",
                       **counterparty
                   )
           else:  # sale
               # Дт361 Кт701 на суму без ПДВ
               MoneyLedgerEntry.objects.create(
                   document=debt_doc,
                   date=dt,
                   debit_account=settings.client_account,
                   credit_account=settings.revenue_account,
                   amount=price_no_vat,
                   comment=f"{item.product.name} (дохід) по {document.doc_number}",
                   **counterparty
               )
               # Дт361 Кт641 на суму ПДВ
               if vat_amount > 0:
                   MoneyLedgerEntry.objects.create(
                       document=debt_doc,
                       date=dt,
                       debit_account=settings.client_account,
                       credit_account=settings.vat_output_account,
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
