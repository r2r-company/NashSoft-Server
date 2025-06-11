from django.utils import timezone

from backend.models import Document
from kkm.service.kkm.fifo import sell_product_fifo

class CashSessionService:
    def __init__(self, session):
        self.session = session

    def close_session(self, user):
        sales = Document.objects.filter(
            shift__session=self.session,
            doc_type='sale',
            status='draft'
        )

        for doc in sales:
            for item in doc.items.all():
                sell_product_fifo(
                    document=doc,
                    product=item.product,
                    warehouse=doc.warehouse,
                    quantity_to_sell=item.quantity
                )
            doc.status = 'posted'
            doc.save()

        self.session.is_closed = True
        self.session.closed_by = user
        self.session.closed_at = timezone.now()
        self.session.save()
