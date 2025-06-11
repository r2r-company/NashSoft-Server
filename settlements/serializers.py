from django.db.models import Sum
from rest_framework import serializers
from .models import Account, Contract, MoneyDocument, MoneyLedgerEntry, MoneyOperation

from rest_framework import serializers
from backend.models import Document,  Supplier



class PaymentEntrySerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        help_text="ID рахунку (каса/банк)"
    )
    source_document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(),
        required=False,
        help_text="ID документа, за яким оплачується"
    )
    partner = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        required=False,
        help_text="ID партнера (Supplier/Customer)"
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        help_text="Сума платежу"
    )
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        required=False,
        help_text="ID постачальника"
    )




class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'company', 'name', 'type']
        extra_kwargs = {
            'name': {'help_text': "Назва рахунку (каса/банк)"},
            'type': {'help_text': "Тип рахунку: 'cash' або 'bank'"}
        }


class ContractSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    payment_type_name = serializers.CharField(source='payment_type.name', read_only=True)

    class Meta:
        model = Contract
        fields = [
            'id', 'name', 'supplier', 'supplier_name', 'client', 'client_name',
            'payment_type', 'payment_type_name', 'account', 'account_name',
            'contract_type', 'doc_file', 'is_active', 'status'
        ]
        extra_kwargs = {
            'name': {'required': False, 'allow_blank': True, 'help_text': "Назва договору (не обов'язково)"},
            'contract_type': {'help_text': "Тип договору: 'поставка', 'обслуговування' тощо"},
            'doc_file': {'help_text': "Файл договору (PDF, DOCX)"},
            'is_active': {'help_text': "Чи активний договір"},
        }

    def validate(self, data):
        if not data.get("supplier") and not data.get("client"):
            raise serializers.ValidationError("Потрібно вказати або постачальника, або клієнта.")
        if data.get("supplier") and data.get("client"):
            raise serializers.ValidationError("Не можна вказувати і постачальника, і клієнта одночасно.")
        return data




class MoneyDocumentActionSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="ID грошового документа")
    action = serializers.ChoiceField(choices=["progress", "unprogress"], help_text="Дія: провести або розпровести")

    def validate(self, data):
        try:
            document = MoneyDocument.objects.get(id=data["id"])
        except MoneyDocument.DoesNotExist:
            raise serializers.ValidationError("Фінансовий документ не знайдено.")
        data["document"] = document
        return data


class SupplierBalanceSerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()
    supplier_name = serializers.CharField()
    total_received = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)


class SupplierDebtSerializer(serializers.Serializer):
    doc_id = serializers.IntegerField()
    doc_number = serializers.CharField()
    supplier_name = serializers.CharField()
    date = serializers.DateTimeField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    debt = serializers.DecimalField(max_digits=12, decimal_places=2)


class SupplierAnalyticsSerializer(serializers.Serializer):
    date = serializers.DateTimeField()
    type = serializers.CharField()
    document = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    direction = serializers.CharField()


class MoneyLedgerEntrySerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    document_number = serializers.CharField(source="document.doc_number", read_only=True)

    class Meta:
        model = MoneyLedgerEntry
        fields = [
            'id', 'date', 'debit_account', 'credit_account',
            'amount', 'comment',
            'supplier', 'supplier_name',
            'customer', 'customer_name',
            'document', 'document_number'
        ]
        extra_kwargs = {
            'debit_account': {'help_text': "Код рахунку дебету (Дт)"},
            'credit_account': {'help_text': "Код рахунку кредиту (Кт)"},
            'comment': {'help_text': "Коментар до проводки"},
        }




class MoneyDocumentSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    source_document_number = serializers.CharField(source="source_document.doc_number", read_only=True)

    class Meta:
        model = MoneyDocument
        fields = "__all__"


class MoneyOperationSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    document_number = serializers.CharField(source="document.doc_number", read_only=True)

    class Meta:
        model = MoneyOperation
        fields = "__all__"
