from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import  render
from django.views.decorators.csrf import csrf_exempt
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
    Interface, TradePoint
from backend.serializers import DocumentSerializer, DocumentListSerializer, PriceSettingDocumentSerializer, \
    ProductSerializer, CompanySerializer, WarehouseSerializer, CustomerSerializer, SupplierSerializer, \
    ProductGroupSerializer, PaymentTypeSerializer, FirmSerializer, DepartmentSerializer, AccountSerializer, \
    TechCalculationSerializer, ProductGroupFlatSerializer, CustomerTypeSerializer, PriceTypeSerializer, \
    InterfaceSerializer, UnitSerializer, AppUserSerializer, TradePointSerializer
from backend.services.factory import get_document_service
from backend.services.logger import AuditLoggerService
from backend.services.tech_calc import TechCalculationService
from settlements.models import Account


class DocumentPostView(APIView):
    permission_classes = [AllowAny]

    # @require_document_permission("receipt", "create")  # Для Поступлення (Receipt) перевіряється право на створення
    def post(self, request):
        serializer = DocumentSerializer(data=request.data)
        if serializer.is_valid():
            document = serializer.save()
            return Response(
                {"message": f"Документ {document.doc_number} створено. ID: {document.id}"},
                status=201
            )
        return Response(serializer.errors, status=400)


class DocumentListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doc_type = request.query_params.get("type")  # необов'язковий фільтр
        queryset = Document.objects.all().order_by("-date")

        if doc_type:
            queryset = queryset.filter(doc_type=doc_type)

        serializer = DocumentListSerializer(queryset, many=True)
        return Response(serializer.data)


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
            data = (
                Operation.objects
                .filter(visible=True, direction='in')
                .values('product__id', 'product__name', 'warehouse__id', 'warehouse__name')
                .annotate(total=Sum('quantity'))
                .order_by('warehouse__name', 'product__name')
            )
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
    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))  # якщо id — число
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)
        except ValueError:
            return Response({"error": "Невалідний формат ID"}, status=400)

        if document.doc_type != 'transfer':
            return Response({"error": "Це не документ переміщення"}, status=400)

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
    def get(self, request):
        doc_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not doc_id:
            return Response({"error": "Не передано параметр 'id'"}, status=400)

        try:
            document = Document.objects.get(id=int(doc_id))
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)

        if document.doc_type != 'sale':
            return Response({"error": "Це не документ реалізації"}, status=400)

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
    def get(self, request):
        action = request.query_params.get('action')
        doc_number = request.query_params.get('id')

        if not action or not doc_number:
            raise ValidationError("Не вказано параметри action або id.")

        try:
            # Замість id використовуємо doc_number для пошуку документа
            document = PriceSettingDocument.objects.get(doc_number=doc_number)
        except PriceSettingDocument.DoesNotExist:
            # Якщо документ не знайдений, повертаємо 404
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
                "message": f"Документ ціноутворення {price_setting_document.doc_number} створено."
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