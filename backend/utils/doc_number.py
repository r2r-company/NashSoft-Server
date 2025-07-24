from django.db.models import Max
from backend.models import Document,  DocumentSettings


def generate_document_number(doc_type, company):
    from backend.models import Document
    from django.db import transaction

    # Префікси для різних типів документів
    prefix_map = {
        'receipt': 'REC',
        'sale': 'SALE',
        'transfer': 'TRF',
        'inventory': 'INV',
        'return_to_supplier': 'RTS',
        'return_from_client': 'RFC',
        'stock_in': 'STI',
        'conversion': 'CNV',
    }

    prefix = prefix_map.get(doc_type, 'DOC')

    with transaction.atomic():
        # ✅ ПРАВИЛЬНИЙ ЗАПИТ ДЛЯ ПОШУКУ ОСТАННЬОГО НОМЕРА:
        last_doc = (
            Document.objects
            .select_for_update()
            .filter(doc_number__startswith=prefix, company=company)  # ✅ ДОДАТИ company
            .order_by('-id')  # ✅ СОРТУВАННЯ ПО ID
            .first()
        )

        if last_doc and last_doc.doc_number:
            try:
                # Витягуємо номер після останнього дефіса
                last_seq = int(last_doc.doc_number.split('-')[-1])
            except (ValueError, IndexError):
                last_seq = 0
        else:
            last_seq = 0

        new_seq = str(last_seq + 1).zfill(5)
        new_number = f"{prefix}-{new_seq}"

        # ✅ ДОДАТКОВА ПЕРЕВІРКА НА УНІКАЛЬНІСТЬ:
        while Document.objects.filter(doc_number=new_number).exists():
            last_seq += 1
            new_number = f"{prefix}-{str(last_seq).zfill(5)}"

        return new_number