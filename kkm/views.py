from datetime import date

from django.shortcuts import render, get_object_or_404

# Create your views here.
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.models import Product, Warehouse, PriceSettingItem, PriceSettingDocument, PriceType
from kkm.models import CashShift, CashWorkstation
from kkm.service.kkm.multi_firm_receipt import MultiFirmReceiptBuilderService
from kkm.service.kkm.receipt import ReceiptBuilderService
from kkm.service.kkm.shift import get_workstation_from_request


class PrintReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Отримати workstation
        try:
            workstation = get_workstation_from_request(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        cash_register = workstation.cash_register

        # 2. 🔍 Перевірка обов'язкових полів
        required_fields = ["product_id", "quantity", "price", "warehouse_id"]
        missing = [field for field in required_fields if request.data.get(field) is None]

        if missing:
            return Response({"error": f"Не передано поля: {', '.join(missing)}"}, status=400)

        # 3. Витягти поля
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity")
        price = request.data.get("price")
        warehouse_id = request.data.get("warehouse_id")

        # 4. Отримати активну зміну
        shift = CashShift.objects.filter(
            cash_register=cash_register,
            is_closed=False
        ).order_by('-opened_at').first()

        if not shift:
            return Response({"error": "Немає відкритої зміни"}, status=400)

        product = get_object_or_404(Product, id=product_id)
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)

        # 5. Побудова чека
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









def get_workstation_from_request(request):
    app_key = request.data.get("app_key")
    pc_name = request.data.get("pc_name")

    if app_key:
        return get_object_or_404(CashWorkstation, app_key=app_key, active=True)
    elif pc_name:
        return get_object_or_404(CashWorkstation, name__iexact=pc_name.strip(), active=True)

    raise ValueError("Не передано APP KEY або pc_name")


def get_product_price(product, price_type_name='Роздрібна'):
    price_type = PriceType.objects.filter(name=price_type_name).first()
    if not price_type:
        raise ValueError(f"Тип ціни '{price_type_name}' не знайдено")

    company = product.firm.company

    price_docs = PriceSettingDocument.objects.filter(
        status='approved',
        valid_from__lte=date.today(),
        company=company
    ).order_by('-valid_from')  # 🔁 ВСІ, від новіших до старіших

    for price_doc in price_docs:
        item = PriceSettingItem.objects.filter(
            price_setting_document=price_doc,
            product=product,
            price_type=price_type
        ).first()

        if item:
            return item.price  # ✅ Ціну знайшли — віддаємо

    raise ValueError(f"Ціну не знайдено для товару '{product.name}' в жодному документі ціноутворення")



class PrintMultiFirmReceiptsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            workstation = get_workstation_from_request(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        shift = CashShift.objects.filter(
            cash_register=workstation.cash_register,
            is_closed=False
        ).order_by('-opened_at').first()

        if not shift:
            return Response({"error": "Немає відкритої зміни"}, status=400)

        raw_items = request.data.get("items")
        warehouse_id = request.data.get("warehouse_id")

        if not isinstance(raw_items, list):
            return Response({"error": "Поле 'items' має бути списком"}, status=400)
        if not warehouse_id:
            return Response({"error": "'warehouse_id' обовʼязковий"}, status=400)

        items = []
        for item in raw_items:
            product_id = item.get("product_id")
            quantity = item.get("quantity")

            if not product_id or not quantity:
                return Response({"error": "Кожен товар має містити 'product_id' та 'quantity'"}, status=400)

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response({"error": f"Товар з ID {product_id} не знайдено"}, status=400)

            try:
                price = get_product_price(product)
            except ValueError as e:
                return Response({"error": str(e)}, status=400)

            items.append({
                "product_id": product.id,
                "quantity": quantity,
                "price": price,
                "warehouse_id": warehouse_id
            })

        try:
            receipts = MultiFirmReceiptBuilderService(shift).build_receipts(items)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        result = []
        for receipt in receipts:
            result.append({
                "firm": receipt.firm.name,
                "type": getattr(receipt.firm, 'vat_type', 'Невідомо'),
                "fiscal_number": receipt.fiscal_number,
                "printed_at": receipt.printed_at,
                "items": [
                    {
                        "product": op.product.name,
                        "quantity": op.quantity,
                        "price": float(op.price)
                    } for op in receipt.operations.all()
                ]
            })

        return Response(result, status=200)