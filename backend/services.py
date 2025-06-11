from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from .models import Operation


@transaction.atomic
def sell_product_fifo(document, product, warehouse, quantity_to_sell):
    # Перевірка загального залишку
    stock = Operation.objects.filter(
        product=product,
        warehouse=warehouse,
        visible=True,
        direction='in'
    ).aggregate(total_in=Sum('quantity'))['total_in'] or 0

    stock_out = Operation.objects.filter(
        product=product,
        warehouse=warehouse,
        visible=True,
        direction='out'
    ).aggregate(total_out=Sum('quantity'))['total_out'] or 0

    available_stock = stock - stock_out

    if available_stock < quantity_to_sell:
        raise ValidationError(f"Недостатньо залишку для товару '{product.name}'. Доступно: {available_stock}, потрібно: {quantity_to_sell}")

    # FIFO-списання з блокуванням
    operations = Operation.objects.select_for_update().filter(
        product=product,
        warehouse=warehouse,
        direction='in',
        visible=True
    ).order_by('created_at')

    qty_needed = quantity_to_sell

    for op in operations:
        if qty_needed <= 0:
            break

        qty_sold = Operation.objects.filter(
            source_operation=op,
            direction='out',
            visible=True
        ).aggregate(total_sold=Sum('quantity'))['total_sold'] or 0

        available_in_operation = op.quantity - qty_sold

        if available_in_operation <= 0:
            continue

        qty_to_deduct = min(available_in_operation, qty_needed)

        Operation.objects.create(
            document=document,
            product=product,
            quantity=qty_to_deduct,
            price=op.price,
            warehouse=warehouse,
            direction='out',
            visible=True,
            source_operation=op
        )

        qty_needed -= qty_to_deduct


