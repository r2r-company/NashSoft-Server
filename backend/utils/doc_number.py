from django.db.models import Max
from backend.models import Document, DOC_TYPE_CODES

def generate_document_number(doc_type: str) -> str:
    prefix = DOC_TYPE_CODES.get(doc_type, "999")
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
