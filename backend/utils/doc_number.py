from django.db.models import Max
from backend.models import Document,  DocumentSettings


def generate_document_number(doc_type: str, company) -> str:
    """Генерація номеру документа з налаштувань компанії"""
    try:
        settings = DocumentSettings.objects.get(company=company)
        prefix_map = {
            'receipt': settings.receipt_prefix,
            'sale': settings.sale_prefix,
            'return_to_supplier': settings.return_to_supplier_prefix,
            'return_from_client': settings.return_from_client_prefix,
            'transfer': settings.transfer_prefix,
            'inventory': settings.inventory_prefix,
            'stock_in': settings.stock_in_prefix,
            'conversion': settings.conversion_prefix,
        }
        prefix = prefix_map.get(doc_type, "999")
    except DocumentSettings.DoesNotExist:
        # Фолбек на старі значення
        fallback = {
            'receipt': '703', 'sale': '704', 'return_to_supplier': 'RTS',
            'return_from_client': 'RFC', 'transfer': 'TRF', 'inventory': 'INV',
            'stock_in': 'STI', 'conversion': 'CNV'
        }
        prefix = fallback.get(doc_type, "999")

    last = (
        Document.objects
        .filter(doc_type=doc_type, doc_number__startswith=prefix)
        .aggregate(max_num=Max("doc_number"))["max_num"]
    )
    if last:
        try:
            last_seq = int(last.split("-")[-1])
        except:
            last_seq = 0
    else:
        last_seq = 0

    return f"{prefix}-{str(last_seq + 1).zfill(5)}"