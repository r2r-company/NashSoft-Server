from babel.dates import parse_date
from django.core.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from backend import permissions
from .models import Contract, MoneyLedgerEntry
from .serializers import AccountSerializer, \
    ContractSerializer, MoneyLedgerEntrySerializer, MoneyOperationSerializer, MoneyDocumentSerializer
from .services.account_balance_service import calculate_account_ledger_balance
from .services.money_ledger_service import create_money_ledger_entry
from .services.services import ContractService
from settlements.services.money_document_service import MoneyDocumentService

from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import Account, MoneyDocument, MoneyOperation
from backend.models import Supplier
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F, Case, When, Value, DecimalField
from backend.models import Document


class AccountListCreateView(APIView):
    # permission_classes = [AllowAny]

    def get(self, request):
        company_id = request.query_params.get('company')
        accounts = Account.objects.select_related('company').all()

        if company_id:
            accounts = accounts.filter(company_id=company_id)

        serializer = AccountSerializer(accounts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AccountSerializer(data=request.data)
        if serializer.is_valid():
            account = serializer.save()
            return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContractListCreateView(APIView):
    def get(self, request):
        supplier_id = request.query_params.get("supplier")
        client_id = request.query_params.get("client")

        qs = Contract.objects.filter(is_active=True)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if client_id:
            qs = qs.filter(client_id=client_id)

        serializer = ContractSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ContractSerializer(data=request.data)
        if serializer.is_valid():
            contract = serializer.save()
            return Response(ContractSerializer(contract).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ContractsBySupplierView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        supplier_id = request.query_params.get("id")

        if not supplier_id:
            return Response({"error": "Не вказано id постачальника"}, status=400)

        contracts = Contract.objects.filter(supplier_id=supplier_id, is_active=True)
        serializer = ContractSerializer(contracts, many=True)
        return Response(serializer.data)


class ContractListCreateView(ListCreateAPIView):
    permission_classes = [AllowAny]
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

class ContractDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [AllowAny]
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer


class ContractCreateView(APIView):
    def post(self, request):
        serializer = ContractSerializer(data=request.data)
        if serializer.is_valid():
            contract = serializer.save()
            return Response(ContractSerializer(contract).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ContractsByClientView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        client_id = request.query_params.get("id")
        if not client_id:
            return Response({"error": "Не вказано id клієнта"}, status=400)

        contracts = Contract.objects.filter(client_id=client_id, is_active=True, status="active")
        serializer = ContractSerializer(contracts, many=True)
        return Response(serializer.data)

class ContractActionView(APIView):
    def get(self, request):
        contract_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not contract_id:
            return Response({"error": "Потрібен параметр id"}, status=400)

        try:
            contract = Contract.objects.get(id=int(contract_id))
        except Contract.DoesNotExist:
            return Response({"error": "Договір не знайдено"}, status=404)

        service = ContractService(contract)
        try:
            if action == "post":
                service.post()
                return Response({"message": f"Договір {contract.name} активовано"}, status=200)
            elif action == "unpost":
                service.unpost()
                return Response({"message": f"Договір {contract.name} повернуто в чернетку"}, status=200)
            else:
                return Response({"error": "Невідома дія"}, status=400)
        except ValidationError as e:
            return Response({"error": e.message}, status=400)



class MoneyDocumentActionView(APIView):
    def get(self, request):
        document_id = request.query_params.get("id")
        action = request.query_params.get("action")

        if not document_id or not action:
            return Response({"error": "Потрібно вказати id і action"}, status=400)

        try:
            document = MoneyDocument.objects.get(id=document_id)
        except MoneyDocument.DoesNotExist:
            return Response({"error": "Документ не знайдено."}, status=404)

        service = MoneyDocumentService(document)

        try:
            if action == "progress":
                if document.doc_type == "supplier_debt":
                    return Response({"error": "Документ боргу не потребує проведення."}, status=400)

                service.post()
                return Response({"message": f"Документ {document.doc_number} проведено."})
            elif action == "unprogress":
                service.unpost()
                return Response({"message": f"Документ {document.doc_number} розпроведено."})
            else:
                return Response({"error": "Невідома дія."}, status=400)
        except ValidationError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=400)



class MoneyBalanceView(APIView):
    def get(self, request):
        company_id = request.query_params.get("company")

        qs = MoneyOperation.objects.filter(
            visible=True,
            document__isnull=False,
            document__status='posted'
        ).select_related("account")

        if company_id:
            qs = qs.filter(document__company_id=company_id)

        balances = {}

        for op in qs:
            acc = op.account
            if not acc:
                continue  # 💣 Пропускаємо записи без рахунку (наприклад, борги)

            acc_key = acc.id
            if acc_key not in balances:
                balances[acc_key] = {
                    "account_id": acc.id,
                    "account_name": acc.name,
                    "account_type": acc.type,
                    "total_in": 0,
                    "total_out": 0,
                }

            if op.direction == "in":
                balances[acc_key]["total_in"] += float(op.amount)
            elif op.direction == "out":
                balances[acc_key]["total_out"] += float(op.amount)

        # Обчислення підсумкового балансу
        result = []
        for val in balances.values():
            val["balance"] = round(val["total_in"] - val["total_out"], 2)
            result.append(val)

        return Response(result)


class CreateManualPaymentView(APIView):
    """
    Створити вручну документ для оплати або повернення грошей
    """

    @swagger_auto_schema(
        operation_description="Створює фінансовий документ вручну (наприклад, оплата постачальнику).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["company_id", "firm_id", "account_id", "amount", "direction"],
            properties={
                'company_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID компанії'),
                'firm_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID фірми'),
                'account_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID рахунку (каса/банк)'),
                'source_document_id': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                     description='ID повʼязаного товарного документа (опціонально)'),
                'supplier_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID постачальника (опціонально)'),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, format='decimal', description='Сума платежу'),
                'direction': openapi.Schema(type=openapi.TYPE_STRING, enum=['in', 'out'],
                                            description="Напрям: 'in' (надходження) або 'out' (витрата)")
            },
            example={
                "company_id": 1,
                "firm_id": 2,
                "account_id": 5,
                "source_document_id": 10,
                "supplier_id": 3,
                "amount": 200.00,
                "direction": "out"
            }
        )
    )
    def post(self, request):
        data = request.data

        company_id = data.get('company_id')
        firm_id = data.get('firm_id')
        account_id = data.get('account_id')
        source_document_id = data.get('source_document_id')
        supplier_id = data.get('supplier_id')
        amount = data.get('amount')
        direction = data.get('direction')

        if not all([company_id, firm_id, account_id, amount, direction]):
            return Response({"error": "Обов'язкові поля: company_id, firm_id, account_id, amount, direction"},
                            status=400)

        if direction not in ['in', 'out']:
            return Response({"error": "Поле direction має бути 'in' або 'out'"}, status=400)

        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return Response({"error": "Рахунок не знайдено"}, status=404)

        source_document = None
        if source_document_id:
            try:
                source_document = Document.objects.get(id=source_document_id)
            except ObjectDoesNotExist:
                return Response({"error": "Документ не знайдено"}, status=404)

        supplier = None
        if supplier_id:
            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except ObjectDoesNotExist:
                return Response({"error": "Постачальник не знайдено"}, status=404)

        if not supplier and source_document:
            supplier = source_document.supplier

        doc_type = 'cash_income' if direction == 'in' and account.type == 'cash' else \
            'bank_income' if direction == 'in' else \
                'cash_outcome' if account.type == 'cash' else 'bank_outcome'

        with transaction.atomic():
            money_doc = MoneyDocument.objects.create(
                company_id=company_id,
                firm_id=firm_id,
                doc_type=doc_type,
                account=account,
                comment="Ручний платіж",
                status='draft'
            )

            MoneyOperation.objects.create(
                document=money_doc,
                account=account,
                supplier=supplier,
                source_document=source_document,
                amount=amount,
                direction=direction,
                visible=False
            )

        return Response({
            "message": f"Документ {money_doc.doc_number} створено на суму {amount} грн.",
            "document_id": money_doc.id
        }, status=201)


class SupplierBalanceView(APIView):
    def get(self, request):
        suppliers = Supplier.objects.all()
        result = []

        for s in suppliers:
            total_received = MoneyOperation.objects.filter(
                supplier=s,
                direction='in',
                visible=True,
                document__status='posted'
            ).aggregate(total=Sum('amount'))['total'] or 0

            total_paid = MoneyOperation.objects.filter(
                supplier=s,
                direction='out',
                visible=True,
                document__status='posted'
            ).aggregate(total=Sum('amount'))['total'] or 0

            result.append({
                'supplier_id': s.id,
                'supplier_name': s.name,
                'total_received': total_received,
                'total_paid': total_paid,
                'balance': total_received - total_paid
            })

        return Response(result)


class SupplierDebtListView(APIView):
    def get(self, request):
        result = []
        docs = Document.objects.filter(doc_type='receipt', status='posted')

        for doc in docs:
            total = doc.items.aggregate(sum=Sum(F('quantity') * F('price')))['sum'] or 0

            paid = MoneyOperation.objects.filter(
                source_document=doc,
                direction='out',
                visible=True,
                document__status='posted'
            ).aggregate(sum=Sum('amount'))['sum'] or 0

            result.append({
                'doc_id': doc.id,
                'doc_number': doc.doc_number,
                'supplier_name': doc.supplier.name if doc.supplier else None,
                'date': doc.date,
                'total': total,
                'paid': paid,
                'debt': total - paid
            })

        return Response(result)


class SupplierAnalyticsView(APIView):
    def get(self, request):
        supplier_id = request.query_params.get('supplier')
        if not supplier_id:
            return Response({"error": "Не вказано supplier"}, status=400)

        try:
            supplier = Supplier.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            return Response({"error": "Постачальника не знайдено"}, status=404)

        operations = []

        ops = MoneyOperation.objects.filter(
            supplier=supplier,
            visible=True,
            document__status='posted'
        ).order_by('created_at')

        for op in ops:
            operations.append({
                "date": op.created_at,
                "type": "Поступлення" if op.direction == 'in' else "Оплата",
                "document": op.document.doc_number if op.document else "-",
                "amount": op.amount,
                "direction": op.direction
            })

        return Response({
            "supplier": supplier.name,
            "operations": operations
        })


class PaySupplierDebtView(APIView):
    """
    API для створення документа оплати боргу постачальнику
    """

    def post(self, request):
        data = request.data

        company_id = data.get('company_id')
        firm_id = data.get('firm_id')
        account_id = data.get('account_id')
        source_document_id = data.get('source_document_id')
        amount = data.get('amount')

        if not all([company_id, firm_id, account_id, source_document_id, amount]):
            return Response(
                {"error": "Необхідні всі поля: company_id, firm_id, account_id, source_document_id, amount"},
                status=400)

        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return Response({"error": "Рахунок не знайдено"}, status=404)

        try:
            source_document = Document.objects.get(id=source_document_id)
        except Document.DoesNotExist:
            return Response({"error": "Документ не знайдено"}, status=404)

        supplier = source_document.supplier
        if not supplier:
            return Response({"error": "У документа немає постачальника"}, status=400)

        doc_type = 'cash_outcome' if account.type == 'cash' else 'bank_outcome'

        with transaction.atomic():
            money_doc = MoneyDocument.objects.create(
                doc_type=doc_type,
                company_id=company_id,
                firm_id=firm_id,
                account=account,
                supplier=supplier,
                source_document=source_document,
                comment=f"Оплата боргу за документом {source_document.doc_number}",
                status='posted'
            )

            operation = MoneyOperation.objects.create(
                document=money_doc,
                account=account,
                supplier=supplier,
                source_document=source_document,
                amount=amount,
                direction='out',
                visible=True
            )

            # ✅ Автопроводка через сервіс
            create_money_ledger_entry(operation)

        return Response({
            "message": f"Документ створено на суму {amount} грн для постачальника {supplier.name}.",
            "document_id": money_doc.id
        }, status=201)


class MoneyLedgerEntryListView(APIView):
    def get(self, request):
        document_id = request.query_params.get('document_id')

        qs = MoneyLedgerEntry.objects.select_related(
            "supplier", "customer", "document"
        )

        if document_id:
            qs = qs.filter(document_id=document_id)

        qs = qs.order_by('-date')
        serializer = MoneyLedgerEntrySerializer(qs, many=True)
        return Response(serializer.data)


class MoneyDocumentListView(ListAPIView):
    serializer_class = MoneyDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = MoneyDocument.objects.all().order_by("-date")

        # 🔍 Якщо треба виключити боргові докMoneyDocumentActionView ументи
        exclude_debt = self.request.query_params.get("exclude_debt")
        if exclude_debt == "true":
            queryset = queryset.exclude(doc_type="supplier_debt")

        return queryset


class MoneyOperationListView(ListAPIView):
    queryset = MoneyOperation.objects.select_related("account", "supplier", "document").order_by("-created_at")
    serializer_class = MoneyOperationSerializer
    permission_classes = [permissions.IsAuthenticated]


class MoneyLedgerListView(ListAPIView):
    queryset = MoneyLedgerEntry.objects.select_related("supplier", "customer", "document").order_by("-date")
    serializer_class = MoneyLedgerEntrySerializer


class VATReportView(APIView):
    def get(self, request):
        docs = MoneyDocument.objects.filter(vat_amount__gt=0).select_related('supplier')
        data = []

        for doc in docs:
            data.append({
                "date": doc.date,
                "doc_number": doc.doc_number,
                "supplier": doc.supplier.name if doc.supplier else "",
                "vat_20": float(doc.vat_20),
                "vat_7": float(doc.vat_7),
                "vat_0": float(doc.vat_0),
                "vat_total": float(doc.vat_amount),
            })

        return Response(data)

from datetime import datetime

class VatObligationReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start = request.GET.get("start")
        end = request.GET.get("end")

        try:
            start = datetime.strptime(start, "%Y-%m-%d")
            end = datetime.strptime(end, "%Y-%m-%d")
        except:
            return Response({"error": "Невірна дата"}, status=400)

        queryset = (
            MoneyDocument.objects
            .filter(
                doc_type__in=["cash_outcome", "bank_outcome"],
                date__range=[start, end],
                status='posted'
            )
            .values("supplier__id", "supplier__name")
            .annotate(
                vat_20=Sum("vat_20"),
                vat_7=Sum("vat_7"),
                vat_0=Sum("vat_0"),
                vat_total=Sum("vat_amount")
            )
            .order_by("supplier__name")
        )

        return Response(list(queryset))


class AccountLedgerBalanceView(APIView):
    def get(self, request):
        data = calculate_account_ledger_balance()
        return Response(data)