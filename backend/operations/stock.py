# operations/stock.py
from django.core.exceptions import ValidationError
from django.db.models import Sum
from backend.models import Operation


class FIFOStockManager:

    @staticmethod
    def get_available_stock(product, warehouse, firm):
        incoming = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            visible=True,
            direction='in'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        outgoing = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            visible=True,
            direction='out'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return incoming - outgoing

    @staticmethod
    def sell_fifo(document, product, warehouse, quantity):
        firm = document.firm  # ⬅️ важливо!
        available_stock = FIFOStockManager.get_available_stock(product, warehouse, firm)
        if available_stock < quantity:
            raise ValidationError(
                f"Недостатньо залишку для товару '{product.name}'. Є: {available_stock}, потрібно: {quantity}"
            )

        fifo_sources = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            direction='in',
            visible=True
        ).order_by('created_at')

        qty_needed = quantity

        for source in fifo_sources:
            if qty_needed <= 0:
                break

            used = Operation.objects.filter(
                source_operation=source,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            available_from_source = source.quantity - used

            if available_from_source <= 0:
                continue

            qty_to_deduct = min(available_from_source, qty_needed)

            Operation.objects.create(
                document=document,
                product=product,
                quantity=qty_to_deduct,
                price=source.price,
                warehouse=warehouse,
                direction='out',
                visible=True,
                source_operation=source
            )

            qty_needed -= qty_to_deduct