from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import Product, Warehouse, Operation
from kkm.models import CashShift, ReceiptItemBuffer, FiscalReceipt, ReceiptOperation, CashWorkstation
from kkm.service.kkm.stock import get_available_stock_for_sale


class ReceiptBuilderService:
    def __init__(self, shift: CashShift):
        self.shift = shift
        self.company = shift.company
        self.firm = shift.firm

    @transaction.atomic
    def build_receipt(self, product: Product, quantity: float, price: float, warehouse: Warehouse):
        # 1. Перевірка залишку FIFO + буфер
        available = get_available_stock_for_sale(product, warehouse, self.shift)
        if available < quantity:
            return self._create_failed_receipt(
                f"Недостатньо залишку для товару '{product.name}'. Доступно: {available}, потрібно: {quantity}"
            )

        # 2. Додаємо в буфер
        ReceiptItemBuffer.objects.create(
            shift=self.shift,
            product=product,
            quantity=quantity,
            price=price,
            warehouse=warehouse
        )

        # 3. Створюємо фіскальний чек
        receipt = FiscalReceipt.objects.create(
            shift=self.shift,
            company=self.company,
            firm=self.firm,
            fiscal_number=f"TEST-{timezone.now().strftime('%H%M%S')}",  # моковий номер
            status='success'
        )

        # 4. Додаємо операції з чека
        ReceiptOperation.objects.create(
            receipt=receipt,
            product=product,
            quantity=quantity,
            price=price,
            warehouse=warehouse
        )

        return receipt

    def _create_failed_receipt(self, message):
        return FiscalReceipt.objects.create(
            shift=self.shift,
            company=self.shift.company,
            firm=self.shift.firm,
            status='fail',
            message=message
        )


def get_workstation_from_request(request):
    app_key = request.data.get("app_key")
    pc_name = request.data.get("pc_name")

    if app_key:
        return get_object_or_404(CashWorkstation, app_key=app_key, active=True)
    elif pc_name:
        return get_object_or_404(CashWorkstation, name__iexact=pc_name.strip(), active=True)

    raise ValueError("Не передано APP KEY або pc_name")


class PrintReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            workstation = get_workstation_from_request(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        cash_register = workstation.cash_register

        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity")
        price = request.data.get("price")
        warehouse_id = request.data.get("warehouse_id")

        if not all([product_id, quantity, price, warehouse_id]):
            return Response({"error": "Не всі поля передані"}, status=400)

        shift = CashShift.objects.filter(
            cash_register=cash_register,
            is_closed=False
        ).order_by('-opened_at').first()

        if not shift:
            return Response({"error": "Немає відкритої зміни"}, status=400)

        product = get_object_or_404(Product, id=product_id)
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)

        service = ReceiptBuilderService(shift)
        receipt = service.build_receipt(product, float(quantity), float(price), warehouse)

        if receipt.status == 'fail':
            return Response({
                "status": "fail",
                "message": receipt.message
            }, status=400)

        return Response({
            "status": "success",
            "fiscal_number": receipt.fiscal_number,
            "printed_at": receipt.printed_at,
            "product": product.name,
            "quantity": quantity,
            "price": price
        }, status=200)