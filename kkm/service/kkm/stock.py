from django.db.models import Sum
from backend.models import Operation
from kkm.models import ReceiptItemBuffer

def get_available_stock_for_sale(product, warehouse, shift):
    # FIFO залишок
    total_in = Operation.objects.filter(
        product=product,
        warehouse=warehouse,
        visible=True,
        direction='in'
    ).aggregate(total=Sum('quantity'))['total'] or 0

    total_out = Operation.objects.filter(
        product=product,
        warehouse=warehouse,
        visible=True,
        direction='out'
    ).aggregate(total=Sum('quantity'))['total'] or 0

    fifo_balance = total_in - total_out

    # Буферні записи в межах цієї зміни
    buffer_qty = ReceiptItemBuffer.objects.filter(
        shift=shift,
        product=product,
        warehouse=warehouse
    ).aggregate(total=Sum('quantity'))['total'] or 0

    return fifo_balance - buffer_qty
