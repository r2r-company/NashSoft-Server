from settlements.models import MoneyLedgerEntry


def create_money_ledger_entry(money_operation):
    doc = money_operation.document
    if doc.doc_type == 'supplier_debt':
        return  # ❌ ніяких проводок по боргу — воно вже враховано

    amount = money_operation.amount
    account_type = doc.account.type
    supplier = money_operation.supplier
    customer = money_operation.customer

    if doc.doc_type in ['cash_income', 'bank_income']:
        debit = '301' if account_type == 'cash' else '311'
        credit = '361'
    elif doc.doc_type in ['cash_outcome', 'bank_outcome']:
        debit = '631'
        credit = '301' if account_type == 'cash' else '311'
    else:
        raise ValueError(f"Невідомий тип документа: {doc.doc_type}")

    MoneyLedgerEntry.objects.create(
        document=doc,
        date=doc.date,
        debit_account=debit,
        credit_account=credit,
        amount=amount,
        supplier=supplier,
        customer=customer,
        comment=f"Автопроводка по {doc.doc_number}"
    )

    if doc.vat_amount and doc.vat_amount > 0:
        vat = doc.vat_amount
        cash_acc = '301' if account_type == 'cash' else '311'

        MoneyLedgerEntry.objects.create(
            document=doc,
            date=doc.date,
            debit_account='644',
            credit_account='631',
            amount=vat,
            supplier=supplier,
            comment=f"ПДВ по {doc.doc_number} (зобов’язання)"
        )

        MoneyLedgerEntry.objects.create(
            document=doc,
            date=doc.date,
            debit_account=cash_acc,
            credit_account='644',
            amount=vat,
            supplier=supplier,
            comment=f"ПДВ по {doc.doc_number} (оплата)"
        )
