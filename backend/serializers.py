# serializers.py
from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from backend.models import Document, DocumentItem, PriceSettingItem, PriceSettingDocument, Product, \
    Company, Warehouse, Customer, Supplier, ProductGroup, PaymentType, Firm, Department, Unit,  \
    PriceType, TradePoint, CustomerType, Interface, AppUser, ProductUnitConversion
from backend.services.document_services import apply_vat
from backend.services.price import get_price_from_setting

from backend.utils.doc_number import generate_document_number
from settlements.models import Account, Contract


class DocumentItemSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=False)
    unit_conversion = serializers.PrimaryKeyRelatedField(queryset=ProductUnitConversion.objects.all(), required=False,
                                                         allow_null=True)  # ✅ ДОДАТИ ЦЕ ПОЛЕ
    vat_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    document = serializers.PrimaryKeyRelatedField(read_only=True)
    role = serializers.CharField(required=False, allow_null=True)

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

        # ⬇️ НОВА ВАЛІДАЦІЯ ЦІН
        doc_type = doc.doc_type if doc else data.get('doc_type')

        if doc_type == 'receipt':
            # Для поступлень ціна обов'язкова
            if 'price' not in data or not data['price']:
                raise serializers.ValidationError({
                    "price": "Для поступлення потрібно вказати ціну закупки."
                })

        elif doc_type == 'conversion' and data.get('role') == 'target':
            # Для target товарів у фасуванні ціна розраховується автоматично
            if 'price' in data:
                data['price'] = 0  # Буде перерахована при проведенні

        return data

    def create(self, validated_data):
        from backend.models import AccountingSettings

        # Автопідстановка одиниці виміру
        if 'unit' not in validated_data or not validated_data['unit']:
            validated_data['unit'] = validated_data['product'].unit

        # Перевіряємо тип фірми для ПДВ
        document = self.context.get('document')
        firm = document.firm if document else None

        if firm and not firm.is_vat_payer:
            # ФОП - без ПДВ
            validated_data['vat_percent'] = 0
        else:
            # ТОВ/ТЗОВ/ПАТ - з ПДВ
            if 'vat_percent' not in validated_data or validated_data['vat_percent'] is None:
                try:
                    if document:
                        settings = AccountingSettings.objects.get(company=document.company)
                        validated_data['vat_percent'] = settings.default_vat_rate
                    else:
                        validated_data['vat_percent'] = 20
                except AccountingSettings.DoesNotExist:
                    validated_data['vat_percent'] = 20

        # Вирахування ціни без ПДВ і суми ПДВ
        price = validated_data.get('price', 0)
        vat_percent = validated_data.get('vat_percent', 0)

        if price > 0 and vat_percent > 0:
            price_without_vat = round(price / (1 + vat_percent / 100), 2)
            vat_amount = round(price - price_without_vat, 2)

            validated_data['price_without_vat'] = price_without_vat
            validated_data['vat_amount'] = vat_amount
            validated_data['price_with_vat'] = price
        else:
            # Без ПДВ
            validated_data['price_without_vat'] = price
            validated_data['vat_amount'] = 0
            validated_data['price_with_vat'] = price

        return super().create(validated_data)


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
            validated_data['doc_number'] = generate_document_number(validated_data['doc_type'],
                                                                    validated_data['company'])
            validated_data['status'] = 'draft'
            document = Document.objects.create(**validated_data)

            for item_data in items_data:
                if 'unit' not in item_data or not item_data['unit']:
                    item_data['unit'] = item_data['product'].unit

                # ✅ НОВА ЛОГІКА: автопідстановка цін при створенні
                if validated_data['doc_type'] == 'sale':
                    price_value = item_data.get('price', 0)
                    if (not price_value or
                            price_value == 0 or
                            str(price_value) == '0.00' or
                            float(price_value) == 0.0):
                        print(f"🔍 Автопідстановка ціни для {item_data['product'].name}")
                        self._auto_fill_price_for_item(document, item_data)
                        print(f"✅ Ціна встановлена: {item_data.get('price', 'НЕ ЗНАЙДЕНО')}")

                # ✅ СПРОСТИТИ ЛОГІКУ ЦІН:
                if validated_data['doc_type'] == 'receipt':
                    # Для поступлень - ціна обов'язкова
                    if 'price' not in item_data or item_data['price'] is None:
                        raise serializers.ValidationError({
                            'items': [f"Для поступлення потрібно вказати ціну закупки товару '{item_data['product']}'."]
                        })

                # ✅ АВТОПІДСТАНОВКА ПДВ БЕЗ СКЛАДНОЇ ЛОГІКИ:
                if 'vat_percent' not in item_data or item_data['vat_percent'] is None:
                    # Перевіряємо чи фірма платник ПДВ
                    firm = validated_data.get('firm')
                    if firm and hasattr(firm, 'is_vat_payer') and firm.is_vat_payer:
                        item_data['vat_percent'] = 20
                    else:
                        item_data['vat_percent'] = 0

                # ✅ СТВОРЮЄМО ITEM:
                item_instance = DocumentItem.objects.create(document=document, **item_data)

                # ✅ ПРОСТИЙ РОЗРАХУНОК ПДВ:
                price = item_instance.price
                vat_percent = item_instance.vat_percent or 0

                if vat_percent > 0:
                    # Припускаємо що ціна з ПДВ
                    price_without_vat = round(price / (1 + vat_percent / 100), 2)
                    vat_amount = round(price - price_without_vat, 2)
                    price_with_vat = price
                else:
                    price_without_vat = price
                    vat_amount = 0
                    price_with_vat = price

                item_instance.price_without_vat = price_without_vat
                item_instance.vat_amount = vat_amount
                item_instance.price_with_vat = price_with_vat
                item_instance.save()

        return document

    def _auto_fill_price_for_item(self, document, item_data):
        """
        ✅ ВИПРАВЛЕНА функція: автопідстановка ціни з урахуванням unit_conversion
        """
        from backend.services.price import get_price_from_setting
        from backend.models import ProductUnitConversion, TradePoint

        product = item_data['product']
        unit = item_data.get('unit')

        # ✅ НОВА ЛОГІКА: використовуємо unit_conversion якщо передано
        unit_conversion = item_data.get('unit_conversion')

        if unit_conversion:
            # ✅ ВИПРАВЛЕННЯ: ЗАВЖДИ підставляємо правильну одиницю з фасування
            item_data['unit'] = unit_conversion.to_unit
            print(f"🔍 Використовуємо unit_conversion: {unit_conversion.name}")
            print(f"🔍 Підставляємо unit з фасування: {unit_conversion.to_unit.name}")
        else:
            # Якщо немає unit_conversion - шукаємо по одиниці
            if unit and unit != product.unit:
                unit_conversion = ProductUnitConversion.objects.filter(
                    product=product,
                    to_unit=unit
                ).first()
                print(f"🔍 Знайдено unit_conversion по одиниці: {unit_conversion.name if unit_conversion else 'None'}")

        # ✅ ВИПРАВЛЕННЯ: завжди шукаємо торгову точку для фірми
        trade_point = getattr(document, 'trade_point', None)
        if not trade_point:
            trade_point = TradePoint.objects.filter(firm=document.firm).first()
            print(f"🔍 Підставляємо торгову точку: {trade_point.name if trade_point else 'None'}")

        # Отримуємо ціну з ціноутворення
        price_data = get_price_from_setting(
            product=product,
            firm=document.firm,
            trade_point=trade_point,
            price_type=getattr(document, 'price_type', None),
            unit_conversion=unit_conversion
        )

        if price_data:
            item_data['price'] = price_data['price']
            item_data['vat_percent'] = price_data['vat_percent']
            print(
                f"✅ Автопідстановка ціни: {price_data['price']} грн (фасування: {unit_conversion.name if unit_conversion else 'базова'})")
        else:
            print(f"⚠️ Ціна не знайдена")


class DocumentListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name')
    firm_name = serializers.CharField(source='firm.name', required=False)
    warehouse_name = serializers.CharField(source='warehouse.name', required=False)
    target_warehouse_name = serializers.CharField(source='target_warehouse.name', required=False)

    # ✅ ДОДАТИ ДЛЯ РЕАЛІЗАЦІЇ:
    customer_id = serializers.IntegerField(source='customer.id', required=False)
    customer_name = serializers.CharField(source='customer.name', required=False)
    trade_point_id = serializers.IntegerField(source='trade_point.id', required=False)
    trade_point_name = serializers.CharField(source='trade_point.name', required=False)

    # ✅ ПОЛЯ ДЛЯ ПОСТУПЛЕННЯ:
    supplier_id = serializers.IntegerField(source='supplier.id', required=False)
    supplier_name = serializers.CharField(source='supplier.name', required=False)

    doc_type = serializers.CharField()
    doc_number = serializers.CharField()
    status = serializers.CharField()
    date = serializers.DateTimeField()

    class Meta:
        model = Document
        fields = [
            'id', 'doc_type', 'doc_number', 'date',
            'company_name', 'firm_name', 'warehouse_name', 'target_warehouse_name',
            'supplier_id', 'supplier_name',      # ✅ ДЛЯ ПОСТУПЛЕННЯ
            'customer_id', 'customer_name',      # ✅ ДЛЯ РЕАЛІЗАЦІЇ
            'trade_point_id', 'trade_point_name', # ✅ ДЛЯ РЕАЛІЗАЦІЇ
            'status',
        ]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'name', 'symbol']


class PriceSettingItemSerializer(serializers.ModelSerializer):
    price_type_name = serializers.CharField(source='price_type.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    trade_point_name = serializers.CharField(source='trade_point.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    # ✅ ДОДАТИ ФІРМУ:
    firm_name = serializers.CharField(source='firm.name', read_only=True)
    firm_is_vat_payer = serializers.BooleanField(source='firm.is_vat_payer', read_only=True)

    # ✅ РОЗРАХОВАНІ ПОЛЯ ПДВ:
    price_without_vat = serializers.SerializerMethodField()
    vat_amount = serializers.SerializerMethodField()
    price_with_vat = serializers.SerializerMethodField()

    class Meta:
        model = PriceSettingItem
        fields = [
            'product', 'product_name',
            'price_type', 'price_type_name',
            'price', 'vat_percent', 'vat_included', 'markup_percent',
            'unit', 'unit_name', 'unit_conversion',
            'trade_point', 'trade_point_name',
            'firm', 'firm_name', 'firm_is_vat_payer',  # ✅ ФІРМА
            'price_without_vat', 'vat_amount', 'price_with_vat'
        ]

    def get_price_without_vat(self, obj):
        """Розрахунок ціни без ПДВ"""
        if obj.vat_included and obj.vat_percent > 0:
            # Якщо ціна включає ПДВ - витягуємо ПДВ
            return round(obj.price / (1 + obj.vat_percent / 100), 2)
        else:
            # Якщо ціна без ПДВ
            return obj.price

    def get_vat_amount(self, obj):
        """Розрахунок суми ПДВ"""
        if obj.vat_percent > 0:
            price_without_vat = self.get_price_without_vat(obj)
            return round(price_without_vat * obj.vat_percent / 100, 2)
        return 0

    def get_price_with_vat(self, obj):
        """Розрахунок ціни з ПДВ"""
        if obj.vat_included:
            # Якщо ціна вже включає ПДВ
            return obj.price
        else:
            # Якщо ціна без ПДВ - додаємо ПДВ
            vat_amount = self.get_vat_amount(obj)
            return round(obj.price + vat_amount, 2)


class PriceSettingDocumentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)  # ← додаєш це
    items = PriceSettingItemSerializer(many=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    firm_name = serializers.CharField(source='firm.name', read_only=True)
    trade_points_names = serializers.SerializerMethodField()

    def get_trade_points_names(self, obj):
        return [tp.name for tp in obj.trade_points.all()]

    class Meta:
        model = PriceSettingDocument
        fields = [
            'id',
            'doc_number', 'company', 'company_name',
            'firm', 'firm_name',
            'valid_from', 'status',
            'base_type', 'base_group', 'base_receipt', 'base_price_type',
            'trade_points', 'trade_points_names', 'items'
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
    unit_name = serializers.CharField(source='unit.name', read_only=True)  # ✅ ДОДАЙ


    class Meta:
        model = Product
        fields = ['id', 'name', 'unit', 'unit_name', 'group_id', 'group_name', 'price']

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
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_id = serializers.IntegerField(source='company.id', read_only=True)
    firm_id = serializers.IntegerField(source='firm.id', read_only=True)  # ✅ ДОДАТИ
    firm_name = serializers.CharField(source='firm.name', read_only=True) # ✅ ДОДАТИ

    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'company_name', 'company_id', 'firm_id', 'firm_name']

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
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_id = serializers.IntegerField(source='company.id', read_only=True)  # ✅ ДОДАТИ ДЛЯ ЧИТАННЯ
    is_vat = serializers.SerializerMethodField()

    def get_is_vat(self, obj):
        return obj.vat_type in ['ТОВ', 'ТЗОВ']

    class Meta:
        model = Firm
        fields = ['id', 'name', 'company_name', 'company_id', 'is_vat', 'vat_type']

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



class ProductUnitConversionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductUnitConversion
        fields = '__all__'



class ContractSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    payment_type_name = serializers.CharField(source='payment_type.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    firm_id = serializers.IntegerField(source='firm.id', read_only=True)     # ✅ ДОДАТИ
    firm_name = serializers.CharField(source='firm.name', read_only=True)   # ✅ ДОДАТИ

    class Meta:
        model = Contract
        fields = [
            'id', 'name', 'supplier', 'supplier_name', 'client', 'client_name',
            'firm_id', 'firm_name',  # ✅ ДОДАТИ
            'payment_type', 'payment_type_name', 'account', 'account_name',
            'contract_type', 'doc_file', 'is_active', 'status'
        ]