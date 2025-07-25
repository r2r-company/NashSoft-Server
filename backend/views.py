from datetime import date, timedelta
from decimal import Decimal

import documents
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import  render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView, ListCreateAPIView, RetrieveUpdateAPIView, \
    RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, filters, generics, viewsets
from django.db.models import Sum, Case, When, Value, DecimalField, F
from backend.auth import CustomLoginSerializer
from backend.models import Operation, Document, PriceSettingDocument, AppUser, Product, Company, \
    Warehouse, Customer, Supplier, ProductGroup, Unit, PaymentType, Firm, Department, CustomerType, PriceType, \
    Interface, TradePoint, ProductUnitConversion, PriceSettingItem, BudgetPeriod, ExchangeRate
from backend.operations.stock import FIFOStockManager
from backend.serializers import DocumentSerializer, DocumentListSerializer, PriceSettingDocumentSerializer, \
    ProductSerializer, CompanySerializer, WarehouseSerializer, CustomerSerializer, SupplierSerializer, \
    ProductGroupSerializer, PaymentTypeSerializer, FirmSerializer, DepartmentSerializer, AccountSerializer, \
    TechCalculationSerializer, ProductGroupFlatSerializer, CustomerTypeSerializer, PriceTypeSerializer, \
    InterfaceSerializer, UnitSerializer, AppUserSerializer, TradePointSerializer, ProductUnitConversionSerializer
from backend.services.budget import BudgetService
from backend.services.cashflow import CashFlowService
from backend.services.cost_center import CostCenterService
from backend.services.currency import CurrencyService
from backend.services.document_services import SaleService, ReceiptService, InventoryInService
from backend.services.factory import get_document_service
from backend.services.financial_reports import FinancialReportsService
from backend.services.logger import AuditLoggerService
from backend.services.price import get_price_from_setting, get_all_prices_for_product
from backend.services.tech_calc import TechCalculationService
from backend.utils.responses import StandardResponse, DocumentActionResponse
from backend.utils.unit_converter import convert_to_base
from settlements.models import Account, Contract
from settlements.serializers import ContractSerializer


class DocumentPostView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = DocumentSerializer(data=request.data)
            if serializer.is_valid():
                document = serializer.save()
                return StandardResponse.created(
                    data=DocumentSerializer(document).data,
                    message=f"Документ {document.doc_number} створено успішно",
                    resource_id=document.id
                )

            return StandardResponse.error(
                message="Помилка створення документа",
                details=serializer.errors,
                error_code="VALIDATION_ERROR"
            )

        # ✅ ДОДАТИ ДЕТАЛЬНИЙ EXCEPTION HANDLER:
        except Exception as e:
            import traceback
            print("=== DJANGO CREATE DOCUMENT ERROR ===")
            print(f"Error: {e}")
            print(f"Error type: {type(e).__name__}")
            print(f"Traceback: {traceback.format_exc()}")
            print("Request data:", request.data)
            print("====================================")

            return StandardResponse.error(
                message=f"Внутрішня помилка: {str(e)}",
                error_code="INTERNAL_ERROR"
            )


class DocumentListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_type = request.query_params.get("type")
        queryset = Document.objects.all().order_by("-date")

        if doc_type:
            queryset = queryset.filter(doc_type=doc_type)

        # ✅ ВИПРАВИТИ - ПОТРІБНА ПРАВИЛЬНА ПАГІНАЦІЯ:
        serializer = DocumentListSerializer(queryset, many=True)

        return Response({
            "success": True,
            "data": serializer.data,  # ✅ МАСИВ ДОКУМЕНТІВ
            "message": "Список документів отримано"
        }, status=200)


class DocumentDetailView(APIView):
    permission_classes = [AllowAny]  # ← ось ця стрічка

    def get(self, request, doc_id):
        try:
            document = Document.objects.get(id=doc_id)
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)

        serializer = DocumentSerializer(document)
        data = serializer.data

        # 🔽 Підрахунок суми ПДВ
        total_vat = document.items.aggregate(
            total=Sum('vat_amount')
        )['total'] or 0

        data["total_vat"] = round(total_vat, 2)
        return Response(data, status=200)




class StockBalanceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            firm_id = request.query_params.get("firm")
            company_id = request.query_params.get("company")
            warehouse_id = request.query_params.get("warehouse")

            if not firm_id and not company_id:
                return Response({"error": "Потрібно вказати firm або company"}, status=400)

            from backend.operations.stock import FIFOStockManager

            # ✅ ЛОГІКА ПО ФІРМАМ
            if firm_id:
                # Для конкретної фірми
                firms = [Firm.objects.get(id=firm_id)]
            else:
                # Для всіх фірм компанії
                firms = Firm.objects.filter(company_id=company_id)

            # Склади
            warehouses = Warehouse.objects.all()
            if warehouse_id:
                warehouses = warehouses.filter(id=warehouse_id)

            data = []
            for firm in firms:
                for warehouse in warehouses:
                    # Товари що є на цьому складі для цієї фірми
                    products = Product.objects.filter(
                        operation__warehouse=warehouse,
                        operation__document__firm=firm,
                        operation__direction='in',
                        operation__visible=True
                    ).distinct()

                    for product in products:
                        stock = FIFOStockManager.get_available_stock(product, warehouse, firm)
                        if stock > 0:
                            data.append({
                                'product__id': product.id,
                                'product__name': product.name,
                                'warehouse__id': warehouse.id,
                                'warehouse__name': warehouse.name,
                                'firm__id': firm.id,  # ✅ ДОДАНО
                                'firm__name': firm.name,  # ✅ ДОДАНО
                                'total': float(stock)
                            })

            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ProductOperationsDebugView(APIView):
    def get(self, request, product_id):
        try:
            ops = Operation.objects.filter(product_id=product_id).values(
                'id',
                'product__name',
                'warehouse__id',
                'warehouse__name',
                'quantity',
                'price',
                'direction',
                'visible',
                'created_at',
                'document__doc_number'
            ).order_by('created_at')
            return Response(list(ops))
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class StockByWarehouseView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            warehouse_id = request.query_params.get("warehouse")

            operations = Operation.objects.filter(visible=True)
            if warehouse_id:
                operations = operations.filter(warehouse_id=warehouse_id)

            operations = operations.values('warehouse__id', 'warehouse__name', 'product__id', 'product__name') \
                .annotate(
                incoming=Sum(Case(
                    When(direction='in', then=F('quantity')),
                    default=Value(0),
                    output_field=DecimalField()
                )),
                outgoing=Sum(Case(
                    When(direction='out', then=F('quantity')),
                    default=Value(0),
                    output_field=DecimalField()
                ))
            ).order_by('warehouse__id', 'product__name')

            result = {}
            for item in operations:
                wid = item['warehouse__id']
                balance = (item['incoming'] or 0) - (item['outgoing'] or 0)

                if wid not in result:
                    result[wid] = {
                        'warehouse_name': item['warehouse__name'],
                        'products': []
                    }

                result[wid]['products'].append({
                    'product_id': item['product__id'],
                    'product_name': item['product__name'],
                    'quantity': balance
                })

            return Response(result)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class DocumentActionGetView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)
        except ValueError:
            return Response({"error": "Невалідний формат UUID"}, status=400)

        service = get_document_service(document)

        try:
            if action == "progress":
                service.post()
                return Response({"message": f"Документ {document.doc_number} проведено"}, status=200)

            if action == "unpost":
                service.unpost()
                return Response({"message": f"Документ {document.doc_number} розпроведено"}, status=200)

            return Response({"error": "Невідома дія"}, status=400)

        except ValidationError as e:
            return Response({"error": e.messages}, status=400)


class TransferActionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return StandardResponse.error("Не передано параметр 'id'", "MISSING_PARAMETER")

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return StandardResponse.not_found("Документ", "document")
        except ValueError:
            return StandardResponse.error("Невалідний формат ID", "INVALID_ID")

        if document.doc_type != 'transfer':
            return StandardResponse.error("Це не документ переміщення", "INVALID_DOCUMENT_TYPE")

        service = get_document_service(document)

        # Додаємо логування через middleware
        logger = AuditLoggerService.create_from_request(request, document=document)

        try:
            if action == "progress":
                logger.log_event("transfer_action_requested", f"Запит на проведення переміщення {document.doc_number}")
                service.post()
                return DocumentActionResponse.posted(document.doc_number, "Переміщення")

            if action == "unpost":
                logger.log_event("transfer_unpost_requested",
                                 f"Запит на розпроведення переміщення {document.doc_number}")
                service.unpost()
                return DocumentActionResponse.unposted(document.doc_number, "Переміщення")

            return StandardResponse.error("Невідома дія", "UNKNOWN_ACTION")

        except Exception as e:
            logger.log_error("transfer_action_failed", e, {"action": action, "doc_id": doc_id})
            return StandardResponse.error(str(e), "SERVICE_ERROR")


class ReturnToSupplierActionView(APIView):
    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)
        except ValueError:
            return Response({"error": "Невалідний формат ID"}, status=400)

        if document.doc_type != 'return_to_supplier':
            return Response({"error": "Це не документ повернення постачальнику"}, status=400)

        service = get_document_service(document)

        try:
            if action == "progress":
                service.post()
                return Response({"message": f"Документ {document.doc_number} проведено"}, status=200)

            if action == "unpost":
                service.unpost()
                return Response({"message": f"Документ {document.doc_number} розпроведено"}, status=200)

            return Response({"error": "Невідома дія"}, status=400)

        except ValidationError as e:
            return Response({"error": e.messages}, status=400)


class ReturnFromClientActionView(APIView):
    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)
        except ValueError:
            return Response({"error": "Невалідний формат ID"}, status=400)

        if document.doc_type != 'return_from_client':
            return Response({"error": "Це не документ повернення від клієнта"}, status=400)

        service = get_document_service(document)

        try:
            if action == "progress":
                service.post()
                return Response({"message": f"Документ {document.doc_number} проведено"}, status=200)

            if action == "unpost":
                service.unpost()
                return Response({"message": f"Документ {document.doc_number} розпроведено"}, status=200)

            return Response({"error": "Невідома дія"}, status=400)

        except ValidationError as e:
            return Response({"error": e.messages}, status=400)


class SaleActionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return StandardResponse.error("Не передано параметр 'id'", "MISSING_PARAMETER")

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return StandardResponse.not_found("Документ", "document")
        except ValueError:
            return StandardResponse.error("Невалідний формат ID", "INVALID_ID")

        if document.doc_type != 'sale':
            return StandardResponse.error("Це не документ продажу", "INVALID_DOCUMENT_TYPE")

        # ⬇️ ДОДАЙТЕ request ТУТ
        service = SaleService(document, request=request)

        try:
            if action == "progress":
                service.post()
                return DocumentActionResponse.posted(document.doc_number, "Реалізація")

            if action == "unpost":
                service.unpost()
                return DocumentActionResponse.unposted(document.doc_number, "Реалізація")

            return StandardResponse.error("Невідома дія", "UNKNOWN_ACTION")

        except Exception as e:
            return StandardResponse.error(str(e), "SERVICE_ERROR")


class ReceiptActionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return StandardResponse.error("Не передано параметр 'id'", "MISSING_PARAMETER")

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return StandardResponse.not_found("Документ", "document")

        if document.doc_type != 'receipt':
            return StandardResponse.error("Це не документ поступлення", "INVALID_DOCUMENT_TYPE")

        service = ReceiptService(document, request=request)

        try:
            if action == "progress":
                service.post()
                return DocumentActionResponse.posted(document.doc_number, "Поступлення")

            if action == "unpost":
                service.unpost()
                return DocumentActionResponse.unposted(document.doc_number, "Поступлення")

            return StandardResponse.error("Невідома дія", "UNKNOWN_ACTION")

        except Exception as e:
            return StandardResponse.error(str(e), "SERVICE_ERROR")

class InventoryActionView(APIView):
    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)

        if document.doc_type != 'inventory':
            return Response({"error": "Це не документ інвентаризації"}, status=400)

        service = get_document_service(document)

        try:
            if action == "progress":
                service.post()
                return Response({"message": f"Інвентаризацію {document.doc_number} проведено"}, status=200)

            if action == "unpost":
                service.unpost()
                return Response({"message": f"Інвентаризацію {document.doc_number} розпроведено"}, status=200)

            return Response({"error": "Невідома дія"}, status=400)

        except ValidationError as e:
            return Response({"error": e.messages}, status=400)




class StockInActionView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)

        if document.doc_type != 'stock_in':
            return Response({"error": "Це не документ оприбуткування"}, status=400)

        service = get_document_service(document)

        try:
            if action == "progress":
                service.post()
                return Response({"message": f"Документ {document.doc_number} проведено"}, status=200)
            if action == "unpost":
                service.unpost()
                return Response({"message": f"Документ {document.doc_number} розпроведено"}, status=200)
            return Response({"error": "Невідома дія"}, status=400)
        except ValidationError as e:
            return Response({"error": e.messages}, status=400)




class PriceSettingDocumentActionView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        action = request.query_params.get('action')
        doc_id = request.query_params.get('id')

        if not action or not doc_id:
            raise ValidationError("Не вказано параметри action або id.")

        try:
            document = PriceSettingDocument.objects.get(id=doc_id)
        except PriceSettingDocument.DoesNotExist:
            return Response({"error": "Документ ціноутворення не знайдено."}, status=status.HTTP_404_NOT_FOUND)

        if action == 'approve':
            return self._approve_document(document)
        elif action == 'unapprove':
            return self._unapprove_document(document)
        else:
            raise ValidationError("Невідомий параметр action.")

    def _approve_document(self, document):
        if document.status == 'approved':
            # Якщо документ вже затверджений, повертаємо 400
            return Response({"error": f"Документ {document.doc_number} вже затверджено."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Затверджуємо документ
        document.status = 'approved'
        document.save()

        # Логування
        logger = AuditLoggerService(document=document)
        logger.log_event("price_setting_approved", f"Ціноутворення {document.doc_number} затверджено.")

        return Response({"message": f"Ціноутворення {document.doc_number} затверджено."})

    def _unapprove_document(self, document):
        if document.status != 'approved':
            # Якщо документ не затверджений, повертаємо 400
            return Response(
                {"error": f"Документ {document.doc_number} не затверджено, тому його не можна розпровести."},
                status=status.HTTP_400_BAD_REQUEST)

        # Розпроведення документа
        document.status = 'draft'
        document.save()

        # Логування
        logger = AuditLoggerService(document=document)
        logger.log_event("price_setting_unapproved", f"Ціноутворення {document.doc_number} розпроведено.")

        return Response({"message": f"Ціноутворення {document.doc_number} розпроведено."})

    def _reject_document(self, document):
        if document.status == 'draft':
            raise ValidationError("Документ не затверджено, тому його не можна відхилити.")

        # Відхиляємо прайс
        document.status = 'draft'
        document.save()

        # Логування
        logger = AuditLoggerService(document=document)
        logger.log_event("price_setting_rejected", f"Ціноутворення {document.doc_number} відхилено.")

        return Response({"message": f"Ціноутворення {document.doc_number} відхилено."})


class CreatePriceSettingDocumentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PriceSettingDocumentSerializer(data=request.data)
        if serializer.is_valid():
            price_setting_document = serializer.save()  # Створення документа з елементами
            return Response({
                "message": f"Документ ціноутворення {price_setting_document.doc_number} створено.",
                "id": price_setting_document.id
            }, status=201)

        return Response(serializer.errors, status=400)


class PriceSettingDocumentListView(APIView):
    """
    Відображення всіх документів ціноутворення.
    """
    permission_classes = [AllowAny]  # або IsAuthenticated

    def get(self, request):
        try:
            # Отримуємо всі документи ціноутворення
            price_setting_documents = PriceSettingDocument.objects.all().order_by('-created_at')

            # Серіалізуємо дані
            serializer = PriceSettingDocumentSerializer(price_setting_documents, many=True)

            # Повертаємо серіалізовані дані у відповіді
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            # Обробка помилки
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from django.shortcuts import render
from django.db.models import Sum, Case, When, Value, DecimalField, F
from backend.models import Operation, Document

@csrf_exempt
def stock_report(request):

    # === Залишки по складах ===
    operations = (
        Operation.objects
        .filter(visible=True)
        .values('product__id', 'product__name', 'warehouse__id', 'warehouse__name')
        .annotate(
            incoming=Sum(Case(
                When(direction='in', then=F('quantity')),
                default=Value(0),
                output_field=DecimalField()
            )),
            outgoing=Sum(Case(
                When(direction='out', then=F('quantity')),
                default=Value(0),
                output_field=DecimalField()
            ))
        )
        .order_by('warehouse__id', 'product__name')
    )

    result = {}
    for item in operations:
        wid = item['warehouse__id']
        balance = (item['incoming'] or 0) - (item['outgoing'] or 0)

        if wid not in result:
            result[wid] = {
                'warehouse_name': item['warehouse__name'],
                'products': []
            }

        result[wid]['products'].append({
            'product_id': item['product__id'],
            'product_name': item['product__name'],
            'quantity': balance
        })

    # === Документи обліку ===
    document_types = [
        'receipt', 'sale', 'return_to_supplier',
        'return_from_client', 'transfer', 'inventory', 'stock_in'
    ]

    all_docs = {}
    for doc_type in document_types:
        docs = (
            Document.objects
            .filter(doc_type=doc_type)
            .prefetch_related("items", "items__product", "company", "warehouse")
            .order_by('-date')
        )

        for doc in docs:
            doc.total_amount = sum(item.quantity * item.price for item in doc.items.all())
            doc.total_vat = sum(item.vat_amount or 0 for item in doc.items.all())
            doc.total_without_vat = sum(item.price_without_vat or 0 for item in doc.items.all())
            doc.total_with_vat = doc.total_without_vat + doc.total_vat

            if doc.doc_type == 'sale':
                enriched_items = []
                for item in doc.items.all():
                    sale_op = Operation.objects.filter(
                        document=doc,
                        product=item.product,
                        direction='out',
                        visible=True
                    ).first()

                    source_price = sale_op.source_operation.price if sale_op and sale_op.source_operation else None

                    enriched_items.append({
                        'product_name': item.product.name,
                        'quantity': item.quantity,
                        'price': item.price,
                        'source_price': source_price,
                    })
                doc.enriched_items = enriched_items

        label_map = {
            'receipt': 'Поступлення',
            'sale': 'Реалізації',
            'return_to_supplier': 'Повернення постачальнику',
            'return_from_client': 'Повернення від клієнта',
            'transfer': 'Переміщення',
            'inventory': 'Інвентаризації',
            'stock_in': 'Оприбуткування',
        }

        all_docs[label_map[doc_type]] = docs

    # === Посилання на всі звіти (для відображення у вкладках або в UI) ===
    sections = {
        "Документи обліку": [
            ("Поступлення", "api/documents/?type=receipt"),
            ("Реалізація", "api/documents/?type=sale"),
            ("Повернення постачальнику", "api/documents/?type=return_to_supplier"),
            ("Повернення від клієнта", "api/documents/?type=return_from_client"),
            ("Переміщення", "api/documents/?type=transfer"),
            ("Інвентаризація", "api/documents/?type=inventory"),
            ("Оприбуткування", "api/documents/?type=stock_in"),
        ],
        "Фінанси": [
            ("Грошові документи", "api/money-documents/"),
            ("Грошові операції", "api/money-operations/"),
            ("Проводки", "api/money-ledger/"),
            ("Баланс кас/банку", "api/money/balance/"),
            ("Бухгалтерський баланс рахунків", "api/account-ledger-balance/"),
        ],
        "Аналітика": [
            ("Залишки по складах", "api/stock/warehouses/"),
            ("Борги постачальникам", "api/supplier-debts/"),
            ("Баланс постачальників", "api/supplier-balance/"),
            ("Аналітика постачальника", "api/supplier-payments/?supplier=1"),
            ("FIFO по товару", "api/debug/operations/1/"),
            ("Звіт по ПДВ (рах. 644)", "api/vat-report/"),
        ],
        "Ціноутворення": [
            ("Ціноутворення", "api/price-setting-documents/"),
        ],
        "Довідники": [
            ("Товари", "api/products/"),
            ("Групи товарів", "api/product-groups/"),
            ("Постачальники", "api/suppliers/"),
            ("Клієнти", "api/customers/"),
            ("Склади", "api/warehouses/"),
            ("Компанії", "api/companies/"),
            ("Фірми", "api/firms/"),
            ("Відділи", "api/departments/"),
        ],
        "Звітність": [
            ("Реєстр податкових зобовʼязань", "api/vat-obligation-report/"),
        ]
    }

    return render(request, "backend/stock_report.html", {
        "sections": sections
    })


class WhoAmIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user

        app_users = (
            AppUser.objects
            .filter(user=user, is_active=True, interfaces__isnull=False)
            .prefetch_related("interfaces__access_group__permissions", "company")
        )

        interfaces_data = []
        all_permissions = set()
        has_access = False

        for app_user in app_users:
            for interface in app_user.interfaces.all():
                has_access = True

                # ⬇️ Збираємо права з group, якщо вона є
                if interface.access_group:
                    perms = interface.access_group.permissions.values_list("codename", flat=True)
                    all_permissions.update(perms)

                interfaces_data.append({
                    "username": user.username,
                    "interface": interface.code,
                    "interface_name": interface.name,
                    "company_id": app_user.company.id if app_user.company else None,
                    "company_name": app_user.company.name if app_user.company else None,
                    "app_user_id": app_user.id
                })

        return Response({
            "access": has_access,
            "permissions": sorted(list(all_permissions)),  # ⬅️ всі права, без дублів
            "interfaces": interfaces_data
        })


class CustomLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomLoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=200)
        return Response(serializer.errors, status=400)


class ProductListView(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        queryset = Product.objects.all()
        warehouse_id = self.request.query_params.get('warehouse')
        company_id = self.request.query_params.get('company')

        if warehouse_id:
            queryset = queryset.filter(operation__warehouse_id=warehouse_id).distinct()
        if company_id:
            queryset = queryset.filter(operation__warehouse__company_id=company_id).distinct()

        return queryset


class ProductTotalStockView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        try:
            operations = (
                Operation.objects
                .filter(product_id=product_id, visible=True)
                .values('warehouse__id', 'warehouse__name')
                .annotate(
                    incoming=Sum(Case(
                        When(direction='in', then=F('quantity')),
                        default=Value(0),
                        output_field=DecimalField()
                    )),
                    outgoing=Sum(Case(
                        When(direction='out', then=F('quantity')),
                        default=Value(0),
                        output_field=DecimalField()
                    ))
                )
            )

            total = 0
            details = []

            for op in operations:
                qty = (op['incoming'] or 0) - (op['outgoing'] or 0)
                if qty > 0:
                    details.append({
                        'warehouse_id': op['warehouse__id'],
                        'warehouse_name': op['warehouse__name'],
                        'quantity': qty
                    })
                    total += qty

            return Response({
                'product_id': product_id,
                'total_quantity': total,
                'warehouses': details
            })

        except Exception as e:
            return Response({"error": str(e)}, status=500)




class ProductListCreateView(ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

class ProductDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]


class CompanyListView(ListCreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [AllowAny]


class WarehouseListView(ListAPIView):
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Warehouse.objects.all()
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset




class WarehouseListCreateView(ListCreateAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]


class WarehouseDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]





class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [AllowAny]

class CustomerDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [AllowAny]


class SupplierListCreateView(generics.ListCreateAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [AllowAny]



class ProductGroupTreeView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        # Отримуємо лише кореневі групи
        roots = ProductGroup.objects.filter(parent=None).prefetch_related("children")
        serializer = ProductGroupSerializer(roots, many=True)
        return Response(serializer.data)

class ProductGroupListCreateView(ListCreateAPIView):
    queryset = ProductGroup.objects.all()
    serializer_class = ProductGroupSerializer
    permission_classes = [AllowAny]

class ProductGroupDetailView(RetrieveUpdateDestroyAPIView):
    queryset = ProductGroup.objects.all()
    serializer_class = ProductGroupSerializer
    permission_classes = [AllowAny]



class UserListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        User = get_user_model()
        users = User.objects.all().values("id", "username", "email", "first_name", "last_name")
        return Response(list(users))

class UnitListView(APIView):
    permission_classes = [AllowAny]  # ← ось це треба

    def get(self, request):
        units = Unit.objects.all().values("id", "name", "symbol")
        return Response(list(units))

class UnitListCreateView(ListCreateAPIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [AllowAny]

class UnitDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [AllowAny]


class PaymentTypeListCreateView(ListCreateAPIView):
    queryset = PaymentType.objects.all()
    serializer_class = PaymentTypeSerializer
    permission_classes = [AllowAny]

class SupplierDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [AllowAny]

class FirmListView(ListCreateAPIView):
    queryset = Firm.objects.all()
    serializer_class = FirmSerializer
    permission_classes = [AllowAny]

class DepartmentListView(ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]


class DepartmentDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]


class AccountListView(ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Account.objects.select_related('company').all()
        company_id = self.request.query_params.get('company')

        if company_id:
            queryset = queryset.filter(company_id=company_id)

        return queryset


class AccountListCreateView(ListCreateAPIView):
    serializer_class = AccountSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Account.objects.select_related('company').all()
        company_id = self.request.query_params.get('company')

        if company_id:
            queryset = queryset.filter(company_id=company_id)

        return queryset


class AccountDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Account.objects.select_related('company').all()
    serializer_class = AccountSerializer
    permission_classes = [AllowAny]


class TechCalculationAPIView(APIView):
    def post(self, request):
        serializer = TechCalculationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        try:
            service = TechCalculationService(
                validated['product_id'], validated['mode'], validated['weight']
            )
            result = service.calculate()

            return Response(result)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProductGroupFlatView(ListAPIView):
    queryset = ProductGroup.objects.select_related("parent").all().order_by("name")
    serializer_class = ProductGroupFlatSerializer
    permission_classes = [AllowAny]


class CustomerTypeListView(ListAPIView):
    queryset = CustomerType.objects.all()
    serializer_class = CustomerTypeSerializer
    permission_classes = [AllowAny]


class CustomerTypeListCreateView(ListCreateAPIView):
    queryset = CustomerType.objects.all()
    serializer_class = CustomerTypeSerializer
    permission_classes = [AllowAny]

class CustomerTypeDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomerType.objects.all()
    serializer_class = CustomerTypeSerializer
    permission_classes = [AllowAny]


class PriceTypeListView(ListAPIView):
    queryset = PriceType.objects.all()
    serializer_class = PriceTypeSerializer
    permission_classes = [AllowAny]

class PriceTypeListCreateView(ListCreateAPIView):
    queryset = PriceType.objects.all()
    serializer_class = PriceTypeSerializer
    permission_classes = [AllowAny]

class PriceTypeDetailView(RetrieveUpdateDestroyAPIView):
    queryset = PriceType.objects.all()
    serializer_class = PriceTypeSerializer
    permission_classes = [AllowAny]


class AppUserListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data = []
        for app_user in AppUser.objects.select_related("user", "company").prefetch_related("interfaces"):
            data.append({
                "id": app_user.id,
                "username": app_user.user.username,
                "email": app_user.user.email,
                "first_name": app_user.user.first_name,
                "last_name": app_user.user.last_name,
                "company": app_user.company.name if app_user.company else None,
                "roles": [i.name for i in app_user.interfaces.all()],
                "is_active": app_user.is_active,
            })
        return Response(data)


class AppUserListCreateView(ListCreateAPIView):
    queryset = AppUser.objects.select_related("user", "company").prefetch_related("interfaces")
    serializer_class = AppUserSerializer
    permission_classes = [AllowAny]


class AppUserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = AppUser.objects.select_related("user", "company").prefetch_related("interfaces")
    serializer_class = AppUserSerializer
    permission_classes = [AllowAny]




class InterfaceListCreateView(ListCreateAPIView):
    queryset = Interface.objects.select_related('access_group').all()
    serializer_class = InterfaceSerializer
    permission_classes = [AllowAny]

class InterfaceDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Interface.objects.select_related('access_group').all()
    serializer_class = InterfaceSerializer
    permission_classes = [AllowAny]

from rest_framework.generics import RetrieveAPIView

class CompanyDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [AllowAny]




class FirmViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def retrieve(self, request, pk=None):
        try:
            firm = Firm.objects.get(pk=pk)
        except Firm.DoesNotExist:
            raise NotFound("Фірму не знайдено")
        serializer = FirmSerializer(firm)
        return Response(serializer.data)

    def update(self, request, pk=None):
        try:
            firm = Firm.objects.get(pk=pk)
        except Firm.DoesNotExist:
            raise NotFound("Фірму не знайдено")
        serializer = FirmSerializer(firm, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        try:
            firm = Firm.objects.get(pk=pk)
        except Firm.DoesNotExist:
            raise NotFound("Фірму не знайдено")
        firm.delete()
        return Response({"detail": "Фірму видалено"}, status=status.HTTP_204_NO_CONTENT)



class FirmListCreateView(ListCreateAPIView):
    queryset = Firm.objects.all()
    serializer_class = FirmSerializer
    permission_classes = [AllowAny]




class FirmDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Firm.objects.all()
    serializer_class = FirmSerializer
    permission_classes = [AllowAny]


class VatTypeChoicesView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        choices = ["ФОП", "ТОВ", "ТЗОВ"]

        return Response(choices)

class TradePointListCreateView(ListCreateAPIView):
    queryset = TradePoint.objects.all()
    serializer_class = TradePointSerializer
    permission_classes = [AllowAny]

class TradePointDetailView(RetrieveUpdateDestroyAPIView):
    queryset = TradePoint.objects.all()
    serializer_class = TradePointSerializer
    permission_classes = [AllowAny]




class ReceiptProductsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        doc_id = request.query_params.get("document_id")

        if not doc_id:
            return Response({"error": "Не вказано document_id"}, status=400)

        try:
            document = Document.objects.get(id=doc_id, doc_type='receipt')
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено або це не Поступлення"}, status=404)

        items = document.items.select_related("product", "unit").all()
        result = []

        for item in items:
            result.append({
                "product": item.product.id,
                "unit": item.unit.id if item.unit else None,
                "quantity": float(item.quantity),
                "price": float(item.price),
                "vat_percent": float(item.vat_percent or 0),
                "converted_quantity": float(item.converted_quantity or item.quantity),
                "source_item_id": item.id
            })

        return Response(result)


class ProductUnitConversionListCreateView(ListCreateAPIView):
    queryset = ProductUnitConversion.objects.all()
    serializer_class = ProductUnitConversionSerializer
    permission_classes = [AllowAny]

class ProductUnitConversionDetailView(RetrieveUpdateDestroyAPIView):
    queryset = ProductUnitConversion.objects.all()
    serializer_class = ProductUnitConversionSerializer
    permission_classes = [AllowAny]

class ProductConversionsByProductIdView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        conversions = ProductUnitConversion.objects.filter(product_id=product_id)
        serializer = ProductUnitConversionSerializer(conversions, many=True)
        return Response(serializer.data)


class ConversionActionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return StandardResponse.error("Не передано параметр 'id'", "MISSING_PARAMETER")

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return StandardResponse.not_found("Документ", "document")

        if document.doc_type != 'conversion':
            return StandardResponse.error("Це не документ фасування", "INVALID_DOCUMENT_TYPE")

        service = get_document_service(document)
        logger = AuditLoggerService.create_from_request(request, document=document)

        try:
            if action == "progress":
                logger.log_event("conversion_action_requested", f"Запит на проведення фасування {document.doc_number}")
                service.post()
                return DocumentActionResponse.posted(document.doc_number, "Фасування")

            if action == "unpost":
                logger.log_event("conversion_unpost_requested", f"Запит на розпроведення фасування {document.doc_number}")
                service.unpost()
                return DocumentActionResponse.unposted(document.doc_number, "Фасування")

            return StandardResponse.error("Невідома дія", "UNKNOWN_ACTION")

        except Exception as e:
            logger.log_error("conversion_action_failed", e, {"action": action, "doc_id": doc_id})
            return StandardResponse.error(str(e), "SERVICE_ERROR")


class ProfitabilityReportView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Звіт по прибутковості товарів"""
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        product_id = request.query_params.get('product_id')
        warehouse_id = request.query_params.get('warehouse_id')

        # Операції продажів
        sales_ops = Operation.objects.filter(
            direction='out',
            document__doc_type='sale',
            sale_price__isnull=False
        ).select_related('product', 'warehouse', 'document')

        if date_from:
            sales_ops = sales_ops.filter(created_at__gte=date_from)
        if date_to:
            sales_ops = sales_ops.filter(created_at__lte=date_to)
        if product_id:
            sales_ops = sales_ops.filter(product_id=product_id)
        if warehouse_id:
            sales_ops = sales_ops.filter(warehouse_id=warehouse_id)

        # Агрегація по товарах
        report_data = []

        products = Product.objects.filter(
            id__in=sales_ops.values_list('product_id', flat=True)
        ).distinct()

        for product in products:
            product_ops = sales_ops.filter(product=product)

            total_quantity = product_ops.aggregate(
                total=Sum('quantity')
            )['total'] or 0

            total_cost = product_ops.aggregate(
                total=Sum('total_cost')
            )['total'] or 0

            total_sale = product_ops.aggregate(
                total=Sum('total_sale')
            )['total'] or 0

            profit = total_sale - total_cost
            margin = (profit / total_sale * 100) if total_sale > 0 else 0

            report_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'quantity_sold': float(total_quantity),
                'total_cost': float(total_cost),
                'total_revenue': float(total_sale),
                'profit': float(profit),
                'margin_percent': round(float(margin), 2),
                'avg_cost_price': float(total_cost / total_quantity) if total_quantity > 0 else 0,
                'avg_sale_price': float(total_sale / total_quantity) if total_quantity > 0 else 0,
            })

        # Сортування по прибутку
        report_data.sort(key=lambda x: x['profit'], reverse=True)

        # Загальна статистика
        totals = {
            'total_products': len(report_data),
            'total_quantity': sum(item['quantity_sold'] for item in report_data),
            'total_cost': sum(item['total_cost'] for item in report_data),
            'total_revenue': sum(item['total_revenue'] for item in report_data),
            'total_profit': sum(item['profit'] for item in report_data),
        }

        if totals['total_revenue'] > 0:
            totals['overall_margin'] = round(totals['total_profit'] / totals['total_revenue'] * 100, 2)
        else:
            totals['overall_margin'] = 0

        return StandardResponse.success({
            'items': report_data,
            'totals': totals
        }, "Звіт по прибутковості сформовано")


class StockValueReportView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Звіт по вартості залишків"""
        from backend.operations.stock import FIFOStockManager

        warehouse_id = request.query_params.get('warehouse_id')
        firm_id = request.query_params.get('firm_id')

        if not firm_id:
            return StandardResponse.error("Потрібно вказати firm_id")

        firm = Firm.objects.get(id=firm_id)

        warehouses = Warehouse.objects.all()
        if warehouse_id:
            warehouses = warehouses.filter(id=warehouse_id)

        report_data = []

        for warehouse in warehouses:
            # Всі товари що є на складі
            products_with_stock = Operation.objects.filter(
                warehouse=warehouse,
                document__firm=firm,
                direction='in',
                visible=True
            ).values_list('product_id', flat=True).distinct()

            warehouse_data = {
                'warehouse_id': warehouse.id,
                'warehouse_name': warehouse.name,
                'products': [],
                'total_value': 0
            }

            for product_id in products_with_stock:
                product = Product.objects.get(id=product_id)

                stock = FIFOStockManager.get_available_stock(product, warehouse, firm)
                if stock > 0:
                    value = FIFOStockManager.get_stock_value(product, warehouse, firm)
                    avg_cost = value / stock if stock > 0 else 0

                    warehouse_data['products'].append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'quantity': float(stock),
                        'avg_cost_price': float(avg_cost),
                        'total_value': float(value)
                    })

                    warehouse_data['total_value'] += float(value)

            if warehouse_data['products']:
                report_data.append(warehouse_data)

        total_value = sum(w['total_value'] for w in report_data)

        return StandardResponse.success({
            'warehouses': report_data,
            'total_value': total_value
        }, "Звіт по вартості залишків сформовано")


@api_view(['GET'])
def inventory_in_action(request):
    """Проведення оприбуткування"""
    doc_id = request.query_params.get('id')
    action = request.query_params.get('action')

    try:
        document = Document.objects.get(id=doc_id, doc_type='inventory_in')

        if action == 'progress':
            InventoryInService(document).post()
            return StandardResponse.success(
                {"doc_number": document.doc_number},
                "Оприбуткування проведено успішно"
            )

        return StandardResponse.error("Невідома дія")

    except Document.DoesNotExist:
        return StandardResponse.error("Документ не знайдено")
    except Exception as e:
        return StandardResponse.error(f"Помилка: {e}")


class PriceSettingDocumentDetailView(RetrieveAPIView):
    queryset = PriceSettingDocument.objects.all()
    serializer_class = PriceSettingDocumentSerializer
    permission_classes = [AllowAny]


class ContractsByCustomerView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        customer_id = request.query_params.get('id')

        if not customer_id:
            return Response({"error": "Не передано customer_id"}, status=400)

        try:
            contracts = Contract.objects.filter(
                client_id=customer_id,
                is_active=True
            ).select_related('supplier', 'client', 'payment_type', 'account')

            serializer = ContractSerializer(contracts, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ProductUnitConversionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product')

        if not product_id:
            return Response({"error": "Не передано product_id"}, status=400)

        try:
            conversions = ProductUnitConversion.objects.filter(
                product_id=product_id
            ).select_related('product', 'from_unit', 'to_unit')

            data = []
            for conv in conversions:
                data.append({
                    'id': conv.id,
                    'name': conv.name,
                    'product': conv.product.id,
                    'from_unit': conv.from_unit.id,
                    'to_unit': conv.to_unit.id,
                    'factor': conv.factor,
                    'from_unit_name': conv.from_unit.name,
                    'to_unit_name': conv.to_unit.name,
                })

            return Response(data)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ProductPricesView(APIView):
    """
    ✅ НОВИЙ endpoint: отримання всіх доступних цін для товару

    GET /api/product-prices/?product=1&firm=1&trade_point=2&price_type=1
    """
    permission_classes = [AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product')
        firm_id = request.query_params.get('firm')
        trade_point_id = request.query_params.get('trade_point')
        price_type_id = request.query_params.get('price_type')

        # ✅ Валідація обов'язкових параметрів
        if not product_id or not firm_id:
            return StandardResponse.error(
                "Потрібно вказати product та firm",
                "MISSING_PARAMETERS"
            )

        try:
            product = Product.objects.get(id=product_id)
            firm = Firm.objects.get(id=firm_id)

            trade_point = None
            if trade_point_id:
                trade_point = TradePoint.objects.get(id=trade_point_id)

            price_type = None
            if price_type_id:
                price_type = PriceType.objects.get(id=price_type_id)

        except (Product.DoesNotExist, Firm.DoesNotExist, TradePoint.DoesNotExist, PriceType.DoesNotExist) as e:
            return StandardResponse.error(
                f"Обʼєкт не знайдено: {str(e)}",
                "OBJECT_NOT_FOUND"
            )

        # ✅ Отримуємо всі ціни
        prices = get_all_prices_for_product(
            product=product,
            firm=firm,
            trade_point=trade_point,
            price_type=price_type
        )

        # ✅ Додаємо інформацію про доступні залишки
        enriched_prices = []
        for price_data in prices:
            # Отримуємо залишок товару
            if trade_point and trade_point.firm.warehouse_set.exists():
                warehouse = trade_point.firm.warehouse_set.first()
                stock = FIFOStockManager.get_available_stock(product, warehouse, firm)
            else:
                stock = 0

            price_data['available_stock'] = float(stock)
            price_data['can_sell'] = stock > 0
            enriched_prices.append(price_data)

        return StandardResponse.success(
            data={
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'base_unit': product.unit.name,
                    'base_unit_symbol': product.unit.symbol
                },
                'prices': enriched_prices,
                'total_variants': len(enriched_prices)
            },
            message=f"Знайдено {len(enriched_prices)} варіантів цін для товару"
        )


class ProductSpecificPriceView(APIView):
    """
    ✅ НОВИЙ endpoint: отримання ціни для конкретного фасування

    GET /api/product-specific-price/?product=1&firm=1&unit_conversion=3&trade_point=2
    """
    permission_classes = [AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product')
        firm_id = request.query_params.get('firm')
        unit_conversion_id = request.query_params.get('unit_conversion')
        trade_point_id = request.query_params.get('trade_point')
        price_type_id = request.query_params.get('price_type')

        if not product_id or not firm_id:
            return StandardResponse.error(
                "Потрібно вказати product та firm",
                "MISSING_PARAMETERS"
            )

        try:
            product = Product.objects.get(id=product_id)
            firm = Firm.objects.get(id=firm_id)

            unit_conversion = None
            if unit_conversion_id:
                unit_conversion = ProductUnitConversion.objects.get(id=unit_conversion_id)

            trade_point = None
            if trade_point_id:
                trade_point = TradePoint.objects.get(id=trade_point_id)

            price_type = None
            if price_type_id:
                price_type = PriceType.objects.get(id=price_type_id)

        except (Product.DoesNotExist, Firm.DoesNotExist, ProductUnitConversion.DoesNotExist,
                TradePoint.DoesNotExist, PriceType.DoesNotExist) as e:
            return StandardResponse.error(
                f"Обʼєкт не знайдено: {str(e)}",
                "OBJECT_NOT_FOUND"
            )

        # ✅ Отримуємо конкретну ціну
        price_data = get_price_from_setting(
            product=product,
            firm=firm,
            trade_point=trade_point,
            price_type=price_type,
            unit_conversion=unit_conversion
        )

        if not price_data:
            return StandardResponse.error(
                "Ціна не знайдена для вказаних параметрів",
                "PRICE_NOT_FOUND"
            )

        return StandardResponse.success(
            data=price_data,
            message="Ціна знайдена"
        )


# views.py - ДОДАТИ цей debug view для діагностики

class ProductPricesDebugView(APIView):
    """
    🔍 DEBUG endpoint для діагностики проблем з цінами
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            product_id = request.query_params.get('product')
            firm_id = request.query_params.get('firm')

            if not product_id:
                return StandardResponse.error("Потрібно вказати product_id")

            try:
                product = Product.objects.get(id=product_id)
                firm = Firm.objects.get(id=firm_id) if firm_id else None
            except (Product.DoesNotExist, Firm.DoesNotExist):
                return StandardResponse.error("Товар або фірма не знайдені")

            debug_info = {
                'product_info': {
                    'id': product.id,
                    'name': product.name,
                    'firm_id': getattr(product, 'firm_id', 'Не встановлено'),
                    'base_unit': product.unit.name if product.unit else 'Не встановлено'
                }
            }

            # Весь інший код як в артифакті...

            return StandardResponse.success(
                data=debug_info,
                message="Діагностична інформація отримана"
            )

        except Exception as e:
            return StandardResponse.error(
                f"Помилка виконання: {str(e)}",
                "INTERNAL_ERROR"
            )


class ProductPricesSimpleDebugView(APIView):
    """Спрощений debug для пошуку проблеми"""
    permission_classes = [AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product')
        firm_id = request.query_params.get('firm')

        try:
            product = Product.objects.get(id=product_id)
            firm = Firm.objects.get(id=firm_id) if firm_id else None
        except:
            return StandardResponse.error("Товар або фірма не знайдені")

        debug_info = {}

        # 1️⃣ Інформація про товар
        debug_info['product'] = {
            'id': product.id,
            'name': product.name,
            'firm_id': getattr(product, 'firm_id', None),
            'unit': product.unit.name if product.unit else None
        }

        # 2️⃣ Документи ціноутворення для фірми
        if firm:
            docs_count = PriceSettingDocument.objects.filter(firm=firm).count()
            approved_count = PriceSettingDocument.objects.filter(firm=firm, status='approved').count()

            debug_info['documents'] = {
                'total': docs_count,
                'approved': approved_count
            }

            # Останні документи
            recent_docs = PriceSettingDocument.objects.filter(firm=firm).order_by('-id')[:3]
            debug_info['recent_docs'] = [
                {
                    'id': doc.id,
                    'number': doc.doc_number,
                    'status': doc.status,
                    'valid_from': str(doc.valid_from),
                    'firm_id': doc.firm.id
                }
                for doc in recent_docs
            ]

        # 3️⃣ Позиції ціноутворення для товару
        price_items_count = PriceSettingItem.objects.filter(product=product).count()
        debug_info['price_items_total'] = price_items_count

        if firm:
            price_items_for_firm = PriceSettingItem.objects.filter(product=product, firm=firm).count()
            debug_info['price_items_for_firm'] = price_items_for_firm

        # 4️⃣ Типи цін
        price_types = PriceType.objects.all()
        debug_info['price_types'] = [
            {'id': pt.id, 'name': pt.name, 'is_default': pt.is_default}
            for pt in price_types
        ]

        # 5️⃣ Фасування
        conversions_count = ProductUnitConversion.objects.filter(product=product).count()
        debug_info['conversions_count'] = conversions_count

        return StandardResponse.success(debug_info, "Debug інформація")



class ProductSalePreviewView(APIView):
    """
    🔍 ПОВНИЙ АНАЛІЗ товару для продажу

    GET /api/product-sale-preview/?product=1&firm=1&warehouse=1&quantity=5&unit=2&trade_point=1

    Показує:
    - Залишки і FIFO партії
    - Доступні ціни з ціноутворення
    - Розрахунок собівартості
    - ПДВ та фасування
    - Прибутковість
    """
    permission_classes = [AllowAny]

    def get(self, request):
        # Параметри запиту
        product_id = request.query_params.get('product')
        firm_id = request.query_params.get('firm')
        warehouse_id = request.query_params.get('warehouse')
        quantity = request.query_params.get('quantity', 1)
        unit_id = request.query_params.get('unit')
        trade_point_id = request.query_params.get('trade_point')
        price_type_id = request.query_params.get('price_type')

        if not all([product_id, firm_id, warehouse_id]):
            return StandardResponse.error("Потрібно вказати product, firm, warehouse")

        try:
            product = Product.objects.get(id=product_id)
            firm = Firm.objects.get(id=firm_id)
            warehouse = Warehouse.objects.get(id=warehouse_id)
            quantity = Decimal(str(quantity))

            unit = Unit.objects.get(id=unit_id) if unit_id else product.unit
            trade_point = TradePoint.objects.get(id=trade_point_id) if trade_point_id else None
            price_type = PriceType.objects.get(id=price_type_id) if price_type_id else None

        except (Product.DoesNotExist, Firm.DoesNotExist, Warehouse.DoesNotExist,
                Unit.DoesNotExist, TradePoint.DoesNotExist, PriceType.DoesNotExist) as e:
            return StandardResponse.error(f"Об'єкт не знайдено: {str(e)}")

        # Конвертуємо кількість в базову одиницю
        converted_qty = convert_to_base(product, unit, quantity)

        result = {
            'input_parameters': {
                'product_name': product.name,
                'firm_name': firm.name,
                'warehouse_name': warehouse.name,
                'requested_quantity': float(quantity),
                'unit_name': unit.name,
                'converted_quantity_base': float(converted_qty),
                'base_unit': product.unit.name
            }
        }

        # 1️⃣ АНАЛІЗ ЗАЛИШКІВ ТА FIFO
        result['stock_analysis'] = self._analyze_stock_fifo(product, warehouse, firm, converted_qty)

        # 2️⃣ АНАЛІЗ ЦІН З ЦІНОУТВОРЕННЯ
        result['price_analysis'] = self._analyze_pricing(product, firm, trade_point, price_type, unit)

        # 3️⃣ РОЗРАХУНОК СОБІВАРТОСТІ
        result['cost_analysis'] = self._analyze_cost(product, warehouse, firm, converted_qty)

        # 4️⃣ АНАЛІЗ ФАСУВАННЯ
        result['packaging_analysis'] = self._analyze_packaging(product, unit)

        # 5️⃣ РОЗРАХУНОК ПРИБУТКОВОСТІ
        result['profitability_analysis'] = self._analyze_profitability(result)

        # 6️⃣ РЕКОМЕНДАЦІЇ
        result['recommendations'] = self._generate_recommendations(result)

        return StandardResponse.success(result, "Аналіз продажу товару виконано")

    def _analyze_stock_fifo(self, product, warehouse, firm, quantity):
        """Аналіз залишків та FIFO партій"""

        # Загальний залишок
        total_stock = FIFOStockManager.get_available_stock(product, warehouse, firm)

        # Детальний FIFO аналіз
        fifo_sources = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            direction='in',
            visible=True
        ).order_by('created_at')

        fifo_details = []
        qty_collected = Decimal('0')

        for source in fifo_sources:
            # Скільки вже використано з цієї партії
            used = Operation.objects.filter(
                source_operation=source,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            available_from_source = source.quantity - used

            if available_from_source > 0:
                qty_to_take = min(available_from_source, quantity - qty_collected)

                fifo_details.append({
                    'source_operation_id': source.id,
                    'document_number': source.document.doc_number,
                    'document_date': source.created_at.isoformat(),
                    'original_quantity': float(source.quantity),
                    'already_used': float(used),
                    'available': float(available_from_source),
                    'will_use': float(qty_to_take),
                    'cost_price': float(source.cost_price),
                    'cost_for_this_part': float(qty_to_take * source.cost_price)
                })

                qty_collected += qty_to_take

                if qty_collected >= quantity:
                    break

        return {
            'total_available_stock': float(total_stock),
            'requested_quantity': float(quantity),
            'can_sell': total_stock >= quantity,
            'shortage': float(max(0, quantity - total_stock)),
            'fifo_breakdown': fifo_details,
            'total_sources_used': len(fifo_details)
        }

    def _analyze_pricing(self, product, firm, trade_point, price_type, unit):
        """Аналіз ціноутворення"""
        from backend.services.price import get_all_prices_for_product, get_price_from_setting
        from backend.models import ProductUnitConversion

        # Визначаємо фасування
        unit_conversion = None
        if unit != product.unit:
            unit_conversion = ProductUnitConversion.objects.filter(
                product=product,
                to_unit=unit
            ).first()

        # Всі доступні ціни
        all_prices = get_all_prices_for_product(product, firm, trade_point, price_type)

        # Конкретна ціна для запитаних параметрів
        specific_price = get_price_from_setting(product, firm, trade_point, price_type, unit_conversion)

        return {
            'all_available_prices': all_prices,
            'selected_price': specific_price,
            'unit_conversion_used': {
                'id': unit_conversion.id if unit_conversion else None,
                'name': unit_conversion.name if unit_conversion else 'Базова одиниця',
                'factor': float(unit_conversion.factor) if unit_conversion else 1.0
            },
            'price_documents_count': PriceSettingDocument.objects.filter(
                firm=firm,
                status='approved'
            ).count()
        }

    def _analyze_cost(self, product, warehouse, firm, quantity):
        """Розрахунок собівартості"""
        try:
            # ✅ ВИПРАВЛЕННЯ: розраховуємо собівартість правильно
            avg_cost = FIFOStockManager.get_cost_price_for_quantity(product, warehouse, firm, quantity)
            total_cost = avg_cost * quantity

            # ✅ ДОДАЄМО: собівартість за одиницю продажу (не базову)
            # Якщо продаємо в грамах, то собівартість треба перерахувати

            return {
                'average_cost_per_base_unit': float(avg_cost),  # 100 грн/кг
                'average_cost_per_sale_unit': float(avg_cost),  # ✅ ДОДАМО ЛОГІКУ НИЖЧЕ
                'total_cost': float(total_cost),
                'calculation_method': 'FIFO',
                'success': True
            }
        except Exception as e:
            return {
                'error': str(e),
                'success': False
            }

    def _analyze_packaging(self, product, unit):
        """Аналіз фасування"""
        conversions = ProductUnitConversion.objects.filter(product=product)

        return {
            'base_unit': {
                'id': product.unit.id,
                'name': product.unit.name,
                'symbol': product.unit.symbol
            },
            'selected_unit': {
                'id': unit.id,
                'name': unit.name,
                'symbol': unit.symbol
            },
            'is_base_unit': unit == product.unit,
            'available_conversions': [
                {
                    'id': conv.id,
                    'name': conv.name,
                    'from_unit': conv.from_unit.name,
                    'to_unit': conv.to_unit.name,
                    'factor': float(conv.factor)
                }
                for conv in conversions
            ]
        }

    def _analyze_profitability(self, result):
        """Розрахунок прибутковості"""
        try:
            cost_data = result['cost_analysis']
            price_data = result['price_analysis']['selected_price']
            input_params = result['input_parameters']

            if not cost_data['success'] or not price_data:
                return {'error': 'Недостатньо даних для розрахунку'}

            # ✅ ВИПРАВЛЕННЯ: правильний розрахунок собівартості за одиницю продажу
            requested_qty = Decimal(str(input_params['requested_quantity']))
            converted_qty = Decimal(str(input_params['converted_quantity_base']))

            sale_price_per_unit = Decimal(str(price_data['price']))  # ціна за одиницю продажу (грам)
            base_cost_per_kg = Decimal(str(cost_data['average_cost_per_base_unit']))  # собівартість за кг

            # ✅ РОЗРАХОВУЄМО собівартість за одиницю продажу
            if converted_qty > 0 and requested_qty > 0:
                # Скільки коштує 1 одиниця продажу (1 грам)
                cost_per_sale_unit = (base_cost_per_kg * converted_qty) / requested_qty
            else:
                cost_per_sale_unit = base_cost_per_kg

            # Розрахунки за загальну кількість
            total_revenue = sale_price_per_unit * requested_qty
            total_cost = cost_per_sale_unit * requested_qty
            profit = total_revenue - total_cost
            margin = (profit / total_revenue * 100) if total_revenue > 0 else 0

            return {
                'sale_price_per_unit': float(sale_price_per_unit),
                'cost_price_per_unit': float(cost_per_sale_unit),  # ✅ ВИПРАВЛЕНО
                'profit_per_unit': float(sale_price_per_unit - cost_per_sale_unit),
                'total_revenue': float(total_revenue),
                'total_cost': float(total_cost),
                'total_profit': float(profit),
                'margin_percent': float(margin),
                'is_profitable': profit > 0,
                # ✅ ДОДАЄМО DEBUG INFO
                'debug': {
                    'base_cost_per_kg': float(base_cost_per_kg),
                    'requested_qty': float(requested_qty),
                    'converted_qty_kg': float(converted_qty),
                    'calculation': f"{float(base_cost_per_kg)} * {float(converted_qty)} / {float(requested_qty)} = {float(cost_per_sale_unit)}"
                }
            }
        except Exception as e:
            return {'error': str(e)}

    def _generate_recommendations(self, result):
        """Генерація рекомендацій"""
        recommendations = []

        # Перевірка залишків
        if not result['stock_analysis']['can_sell']:
            recommendations.append({
                'type': 'warning',
                'message': f"Недостатньо залишку! Потрібно: {result['stock_analysis']['requested_quantity']}, є: {result['stock_analysis']['total_available_stock']}"
            })

        # Перевірка цін
        if not result['price_analysis']['selected_price']:
            recommendations.append({
                'type': 'error',
                'message': 'Ціна не знайдена в ціноутворенні! Додайте ціну для цього товару.'
            })

        # Перевірка прибутковості
        prof = result.get('profitability_analysis', {})
        if 'margin_percent' in prof:
            if prof['margin_percent'] < 10:
                recommendations.append({
                    'type': 'warning',
                    'message': f"Низька рентабельність: {prof['margin_percent']:.1f}%"
                })
            elif prof['margin_percent'] > 50:
                recommendations.append({
                    'type': 'info',
                    'message': f"Висока рентабельність: {prof['margin_percent']:.1f}%"
                })

        return recommendations


@api_view(['GET'])
def get_product_packaging(request, product_id):
    """Отримати список фасувань для товару"""
    try:
        product = Product.objects.get(id=product_id)

        # Отримуємо всі фасування для цього товару
        packagings = ProductUnitConversion.objects.filter(
            product=product
        ).select_related('from_unit', 'to_unit').values(
            'id', 'factor',
            'from_unit__name', 'from_unit__symbol',
            'to_unit__name', 'to_unit__symbol'
        )

        return Response({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'base_unit': {
                    'name': product.unit.name,
                    'symbol': product.unit.symbol
                }
            },
            'packagings': list(packagings)
        })

    except Product.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Товар не знайдено'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)



class TrialBalanceView(APIView):
    """Оборотно-сальдова відомість"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        date_to = request.query_params.get('date_to', date.today())

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            balance = FinancialReportsService.get_trial_balance(company, date_to)
            return StandardResponse.success(balance, "Оборотно-сальдова відомість")

        except Exception as e:
            return StandardResponse.error(str(e))


class BalanceSheetView(APIView):
    """Бухгалтерський баланс"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        date_to = request.query_params.get('date_to', date.today())

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            balance_sheet = FinancialReportsService.get_balance_sheet(company, date_to)
            return StandardResponse.success(balance_sheet, "Бухгалтерський баланс")

        except Exception as e:
            return StandardResponse.error(str(e))


class ProfitLossView(APIView):
    """Звіт про прибутки та збитки"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if not all([company_id, date_from, date_to]):
            return StandardResponse.error("Потрібно вказати company, date_from, date_to")

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            report = FinancialReportsService.get_profit_loss(company, date_from, date_to)
            return StandardResponse.success(report, "Звіт про прибутки та збитки")

        except Exception as e:
            return StandardResponse.error(str(e))


class CostCenterAnalysisView(APIView):
    """Аналіз по центрах витрат"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            analysis = CostCenterService.get_cost_analysis(company, date_from, date_to)
            return StandardResponse.success(analysis, "Аналіз центрів витрат")

        except Exception as e:
            return StandardResponse.error(str(e))


class ExchangeRatesView(APIView):
    """Курси валют"""
    permission_classes = [AllowAny]

    def get(self, request):
        """Поточні курси"""
        try:
            rates = ExchangeRate.objects.filter(
                date=date.today()
            ).select_related('currency')

            data = [{
                'currency_code': rate.currency.code,
                'currency_name': rate.currency.name,
                'rate': rate.rate,
                'date': rate.date,
                'source': rate.source
            } for rate in rates]

            return StandardResponse.success(data, "Курси валют")

        except Exception as e:
            return StandardResponse.error(str(e))

    def post(self, request):
        """Оновлення курсів з НБУ"""
        try:
            result = CurrencyService.get_nbu_rates()

            if result['success']:
                return StandardResponse.success(
                    {'updated_rates': result['created']},
                    f"Оновлено {result['created']} курсів"
                )
            else:
                return StandardResponse.error(result['error'])

        except Exception as e:
            return StandardResponse.error(str(e))


class BudgetExecutionView(APIView):
    """Виконання бюджету"""
    permission_classes = [AllowAny]

    def get(self, request):
        budget_period_id = request.query_params.get('budget_period')

        try:

            budget_period = BudgetPeriod.objects.get(id=budget_period_id)

            execution = BudgetService.get_budget_execution(budget_period)
            return StandardResponse.success(execution, "Виконання бюджету")

        except Exception as e:
            return StandardResponse.error(str(e))


class CashFlowForecastView(APIView):
    """Прогноз грошових потоків"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        date_from = request.query_params.get('date_from', date.today())
        date_to = request.query_params.get('date_to')

        if not date_to:
            date_to = date.today() + timedelta(days=90)

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            forecast = CashFlowService.get_cashflow_report(company, date_from, date_to)
            return StandardResponse.success(forecast, "Прогноз cashflow")

        except Exception as e:
            return StandardResponse.error(str(e))

    def post(self, request):
        """Генерація прогнозу"""
        company_id = request.data.get('company')
        days_ahead = request.data.get('days_ahead', 90)

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            CashFlowService.generate_forecast(company, days_ahead)
            return StandardResponse.success(None, "Прогноз згенеровано")

        except Exception as e:
            return StandardResponse.error(str(e))


class LiquidityRiskView(APIView):
    """Аналіз ризику ліквідності"""
    permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        days_ahead = int(request.query_params.get('days_ahead', 30))

        try:
            from .models import Company
            company = Company.objects.get(id=company_id)

            risk_analysis = CashFlowService.check_liquidity_risk(company, days_ahead)
            return StandardResponse.success(risk_analysis, "Аналіз ризику ліквідності")

        except Exception as e:
            return StandardResponse.error(str(e))