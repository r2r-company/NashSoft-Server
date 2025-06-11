from decimal import Decimal
from django.db.models import Avg
from backend.models import Operation


class StockPricing:
    @staticmethod
    def avg_price(product, warehouse=None, firm=None):
        queryset = Operation.objects.filter(
            product=product,
            direction='in',
            visible=True
        )

        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)

        if firm:
            queryset = queryset.filter(document__firm=firm)

        return queryset.aggregate(avg=Avg('price'))['avg'] or Decimal('0.00')
