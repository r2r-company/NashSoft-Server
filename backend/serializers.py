# serializers.py
from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from backend.models import Document, DocumentItem, PriceSettingItem, PriceSettingDocument, Product, \
    Company, Warehouse, Customer, Supplier, ProductGroup, PaymentType, Firm, Department, Unit, DOCUMENT_META, \
    PriceType, TradePoint, CustomerType, Interface, AppUser
from backend.services.document_services import apply_vat
from backend.services.price import get_price_from_setting

from backend.utils.doc_number import generate_document_number
from settlements.models import Account, Contract


class DocumentItemSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=False)
    vat_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    document = serializers.PrimaryKeyRelatedField(read_only=True)
    role = serializers.CharField(required=False, allow_null=True)  # 💡 тип: "source"/"target" для фасування

    class Meta:
        model = DocumentItem
        fields = "__all__"

    def validate(self, data):
        doc = self.context.get('document')

        # ⛔ Якщо документ фасування — поле role обов'язкове
        if doc and doc.doc_type == 'conversion':
            if 'role' not in data or data['role'] not in ['source', 'target']:
                raise serializers.ValidationError({
                    "role": "Для фасування потрібно вказати роль: 'source' або 'target'."
                })

        return data

    def create(self, validated_data):
        # 💡 Автопідстановка одиниці виміру
        if 'unit' not in validated_data or not validated_data['unit']:
            validated_data['unit'] = validated_data['product'].unit

        # 💡 Автопідстановка ставки ПДВ
        if 'vat_percent' not in validated_data or validated_data['vat_percent'] is None:
            validated_data['vat_percent'] = validated_data['product'].vat_rate or 0

        # 💡 Вирахування ціни без ПДВ і суми ПДВ
        price = validated_data.get('price', 0)
        vat_percent = validated_data.get('vat_percent', 0)
        price_without_vat = round(price / (1 + vat_percent / 100), 2)
        vat_amount = round(price - price_without_vat, 2)

        validated_data['price_without_vat'] = price_without_vat
        validated_data['vat_amount'] = vat_amount
        validated_data['price_with_vat'] = price  # для надійності

        return super().create(validated_data)

    class Meta:
        model = DocumentItem
        fields = "__all__"


class DocumentSerializer(serializers.ModelSerializer):
    items = DocumentItemSerializer(many=True)
    source_document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all(), required=False, allow_null=True)
    auto_payment = serializers.BooleanField(required=False, default=False)
    contract = serializers.PrimaryKeyRelatedField(queryset=Contract.objects.all(), required=False, allow_null=True)
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), required=False, allow_null=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
    trade_point = serializers.PrimaryKeyRelatedField(queryset=TradePoint.objects.all(), required=False, allow_null=True)
    price_type = serializers.PrimaryKeyRelatedField(queryset=PriceType.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Document
        fields = [
            'doc_type', 'company', 'firm', 'warehouse', 'target_warehouse',
            'source_document', 'items', 'trade_point', 'price_type',
            'auto_payment', 'contract', 'supplier', 'customer'
        ]
        read_only_fields = ['status']

    def validate(self, data):
        doc_type = data.get("doc_type")
        source_document = data.get("source_document")
        contract = data.get("contract")
        supplier = data.get("supplier")

        if doc_type == 'receipt':
            if not supplier:
                raise serializers.ValidationError("Для документа 'Поступлення' потрібно вибрати постачальника.")
            if contract and contract.supplier_id != supplier.id:
                raise serializers.ValidationError("Обраний договір не належить вказаному постачальнику.")

        if doc_type == 'sale' and not data.get("customer"):
            raise serializers.ValidationError("Для документа 'Реалізація' потрібно вибрати клієнта.")

        if doc_type == 'return_from_client':
            if not source_document or source_document.doc_type != 'sale':
                raise serializers.ValidationError("Документ джерела має бути типу 'реалізація'.")

        if doc_type == 'return_to_supplier':
            if not source_document or source_document.doc_type != 'receipt':
                raise serializers.ValidationError("Документ джерела має бути типу 'поступлення'.")

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        trade_point = validated_data.pop("trade_point", None)
        price_type = validated_data.pop("price_type", None)

        with transaction.atomic():
            validated_data['doc_number'] = generate_document_number(validated_data['doc_type'])
            validated_data['status'] = 'draft'
            document = Document.objects.create(**validated_data)

            for item in items_data:
                if 'unit' not in item or not item['unit']:
                    item['unit'] = item['product'].unit

                if validated_data['doc_type'] == 'sale':
                    if 'price' not in item or item['price'] is None:
                        pt = price_type or PriceType.objects.filter(is_default=True).first()
                        price = get_price_from_setting(
                            product=item['product'],
                            firm=validated_data['firm'],
                            trade_point=trade_point,
                            price_type=pt
                        )
                        if price is None:
                            raise serializers.ValidationError({
                                'items': [f"Ціна для товару '{item['product']}' по типу '{pt}' не знайдена."]
                            })
                        item['price'] = price

                    if 'vat_percent' not in item or item['vat_percent'] is None:
                        item['vat_percent'] = 20

                item_instance = DocumentItem.objects.create(document=document, **item)
                apply_vat(item_instance)
                item_instance.save()

        return document



class DocumentListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name')
    firm_name = serializers.CharField(source='firm.name', required=False)
    warehouse_name = serializers.CharField(source='warehouse.name', required=False)
    target_warehouse_name = serializers.CharField(source='target_warehouse.name', required=False)
    doc_type = serializers.CharField()
    doc_number = serializers.CharField()
    status = serializers.CharField()
    date = serializers.DateTimeField()

    class Meta:
        model = Document
        fields = [
            'id',
            'doc_type',
            'doc_number',
            'date',
            'company_name',
            'firm_name',
            'warehouse_name',
            'target_warehouse_name',
            'status',
        ]



class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'name', 'symbol']



class PriceSettingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSettingItem
        fields = [
            'product', 'price_type', 'price',
            'vat_percent', 'vat_included', 'markup_percent',
            'unit', 'unit_conversion'
        ]

    def validate(self, data):
        product = data.get("product")
        unit = data.get("unit")
        unit_conversion = data.get("unit_conversion")

        # 🔍 якщо одиниця співпадає з базовою — unit_conversion не треба
        if unit and product and unit != product.unit:
            if not unit_conversion:
                raise serializers.ValidationError("Оберіть фасування (unit_conversion), бо одиниця не базова.")
        return data


class PriceSettingDocumentSerializer(serializers.ModelSerializer):
    items = PriceSettingItemSerializer(many=True)

    class Meta:
        model = PriceSettingDocument
        fields = [
            'doc_number', 'company', 'firm', 'valid_from', 'status',
            'base_type', 'base_group', 'base_receipt', 'base_price_type',
            'trade_points', 'items'
        ]
        read_only_fields = ['doc_number']

    def validate(self, data):
        base_type = data.get("base_type")

        if base_type == "product_group" and not data.get("base_group"):
            raise serializers.ValidationError({
                "base_group": "Потрібно вказати групу товарів (base_group)."
            })

        if base_type == "receipt" and not data.get("base_receipt"):
            raise serializers.ValidationError({
                "base_receipt": "Потрібно вказати документ Поступлення (base_receipt)."
            })

        if base_type == "price_type" and not data.get("base_price_type"):
            raise serializers.ValidationError({
                "base_price_type": "Потрібно вказати тип ціни (base_price_type)."
            })

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        trade_points = validated_data.pop('trade_points', [])

        if not trade_points:
            raise serializers.ValidationError({
                "trade_points": "Потрібно вказати хоча б одну торгову точку."
            })

        with transaction.atomic():
            try:
                doc = PriceSettingDocument.objects.create(**validated_data)
                doc.trade_points.set(trade_points)

                for item in items_data:
                    for tp in trade_points:
                        if not item.get("unit_conversion"):
                            raise serializers.ValidationError({
                                "items": [
                                    f"Оберіть фасування (unit_conversion) для товару {item.get('product')}"
                                ]
                            })

                        PriceSettingItem.objects.create(
                            price_setting_document=doc,
                            product=item['product'],
                            price_type=item['price_type'],
                            price=item['price'],
                            vat_percent=item.get('vat_percent', 20),
                            vat_included=item.get('vat_included', True),
                            markup_percent=item.get('markup_percent', 0),
                            unit=item['unit'],
                            unit_conversion=item['unit_conversion'],
                            trade_point=tp,
                            firm=doc.firm
                        )
            except Exception as e:
                raise serializers.ValidationError({
                    "detail": f"Помилка при створенні документа: {str(e)}"
                })

        return doc


class ProductGroupMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductGroup
        fields = ['id', 'name']


class ProductSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField(source='group.id', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'unit',  'group_id', 'group_name', 'price']

    def get_price(self, obj):
        from backend.models import PriceSettingItem, PriceType

        try:
            price_type = PriceType.objects.filter(is_default=True).first()
            if not price_type:
                return None
            price_item = PriceSettingItem.objects.filter(
                product=obj,
                price_type=price_type,
                price_setting_document__status='approved'
            ).order_by('-price_setting_document__valid_from').first()

            return price_item.price if price_item else None
        except:
            return None


class AccountSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = '__all__'  # Спочатку покаже всі поля

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None


class AppUserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    roles = serializers.StringRelatedField(source='interfaces', many=True, read_only=True)

    class Meta:
        model = AppUser
        fields = ['id', 'user', 'username', 'email', 'first_name', 'last_name',
                  'company', 'company_name', 'interfaces', 'roles', 'is_active']


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'tax_id']


class WarehouseSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Warehouse
        fields = ["id", "name", "company_name"]

class WarehouseSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all(), source="company")

    class Meta:
        model = Warehouse
        fields = ["id", "name", "company_name", "company_id"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'type']


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'tax_id']


class ProductGroupSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = ProductGroup
        fields = ['id', 'name', 'parent', 'children']

    def get_children(self, obj):
        children = obj.children.all()
        return ProductGroupSerializer(children, many=True).data


class PaymentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentType
        fields = ['id', 'name']


class FirmSerializer(serializers.ModelSerializer):
    company = serializers.CharField(source='company.name', read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all(), write_only=True, source='company')
    is_vat = serializers.SerializerMethodField()

    def get_is_vat(self, obj):
        return obj.vat_type in ['ТОВ', 'ТЗОВ']

    class Meta:
        model = Firm
        fields = ['id', 'name', 'company', 'company_id', 'is_vat', 'vat_type']



class DepartmentSerializer(serializers.ModelSerializer):
    firm_name = serializers.CharField(source='firm.name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'firm', 'firm_name']


class TechCalculationSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    mode = serializers.ChoiceField(choices=['output', 'input'])
    weight = serializers.DecimalField(max_digits=10, decimal_places=3)



# serializers.py
class ProductGroupFlatSerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductGroup
        fields = ['id', 'name', 'parent_name']

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent else None



class CustomerTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerType
        fields = ['id', 'name']


class PriceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceType
        fields = ['id', 'name', 'is_default']


class InterfaceSerializer(serializers.ModelSerializer):
    access_group_name = serializers.CharField(source='access_group.name', read_only=True)
    permissions_count = serializers.SerializerMethodField()

    class Meta:
        model = Interface
        fields = ['id', 'code', 'name', 'access_group', 'access_group_name', 'permissions_count']

    def get_permissions_count(self, obj):
        return obj.access_group.permissions.count() if obj.access_group else 0


class TradePointSerializer(serializers.ModelSerializer):
    firm_name = serializers.CharField(source='firm.name', read_only=True)

    class Meta:
        model = TradePoint
        fields = ['id', 'name', 'firm', 'firm_name']