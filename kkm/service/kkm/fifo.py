from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from backend.models import Operation

@transaction.atomic
def sell_product_fifo(document, product, warehouse, quantity_to_sell):
    # 1. Рахуємо залишок
    stock = Operation.objects.filter(
        product=product,
        warehouse=warehouse,
        visible=True,
        direction='in'
    ).aggregate(total=Sum('quantity'))['total'] or 0

    sold = Operation.objects.filter(
        product=product,
        warehouse=warehouse,
        visible=True,
        direction='out'
    ).aggregate(total=Sum('quantity'))['total'] or 0

    available = stock - sold
    if available < quantity_to_sell:
        raise ValidationError(
            f"Недостатньо залишку для '{product.name}'. Є {available}, потрібно {quantity_to_sell}"
        )

    # 2. FIFO списання
    ops_in = Operation.objects.select_for_update().filter(
        product=product,
        warehouse=warehouse,
        direction='in',
        visible=True
    ).order_by('created_at')

    qty_needed = quantity_to_sell

    for op in ops_in:
        if qty_needed <= 0:
            break

        sold_from_this = Operation.objects.filter(
            source_operation=op,
            direction='out',
            visible=True
        ).aggregate(total=Sum('quantity'))['total'] or 0

        available_from_op = op.quantity - sold_from_this

        if available_from_op <= 0:
            continue

        deduct_qty = min(available_from_op, qty_needed)

        Operation.objects.create(
            document=document,
            product=product,
            quantity=deduct_qty,
            price=op.price,
            warehouse=warehouse,
            direction='out',
            visible=True,
            source_operation=op
        )

        qty_needed -= deduct_qty
