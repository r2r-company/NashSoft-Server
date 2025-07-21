# create_test_operations_fixed.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from backend.models import *
from backend.services.document_services import *
from settlements.models import *


def step(message):
    print(f"\n🔄 {message}")
    print("   " + "─" * (len(message) + 2))


def success(message):
    print(f"   ✅ {message}")


def info(message):
    print(f"   ℹ️  {message}")


def create_test_operations():
    print("📋 СТВОРЕННЯ ТЕСТОВИХ ОПЕРАЦІЙ (ВИПРАВЛЕНА ВЕРСІЯ)")
    print("=" * 60)

    # Отримуємо створені об'єкти з перевіркою
    try:
        main_company = Company.objects.get(name='ТОВ "Тестова Торгівля"')
        main_firm = Firm.objects.get(name='ТОВ "Головна фірма"')
        central_warehouse = Warehouse.objects.get(name='Центральний склад')
        retail_warehouse = Warehouse.objects.get(name='Роздрібний склад')

        main_supplier = Supplier.objects.get(name='ТОВ "Продукти України"')
        meat_supplier = Supplier.objects.get(name='ТОВ "М\'ясокомбінат"')

        retail_customer = Customer.objects.get(name='Іванов Іван Іванович')
        wholesale_customer = Customer.objects.get(name='ТОВ "Великий Оптовик"')

        price_type_retail = PriceType.objects.get(name='Роздрібна')
        price_type_wholesale = PriceType.objects.get(name='Оптова')

        trade_point_1 = TradePoint.objects.get(name='Магазин №1 (Центр)')
        trade_point_2 = TradePoint.objects.get(name='Магазин №2 (Спальний район)')
        wholesale_point = TradePoint.objects.get(name='Оптовий відділ')

        # Одиниці виміру з захистом від дублікатів
        unit_kg = Unit.objects.filter(symbol='кг').first()
        unit_sht = Unit.objects.filter(symbol='шт').first()
        unit_l = Unit.objects.filter(symbol='л').first()

        if not unit_kg or not unit_sht or not unit_l:
            raise Exception("Не знайдено одиниці виміру!")

        info(f"Знайдено всі необхідні довідники")

    except Exception as e:
        print(f"❌ ПОМИЛКА: {e}")
        print("💡 Спочатку запустіть: python create_test_system.py")
        return

    # Отримуємо товари
    products = {}
    product_names = [
        'Фарш свинячий', 'Окорок свинячий', 'Молоко 2.5%', 'Сир твердий',
        'Хліб білий', 'Булочка з маком', 'Вода мінеральна', 'Сік апельсиновий',
        'Котлета домашня'
    ]

    for name in product_names:
        try:
            products[name.lower().split()[0]] = Product.objects.get(name=name)
        except Product.DoesNotExist:
            print(f"❌ Товар '{name}' не знайдено!")
            return

    # ========== ЦІНОУТВОРЕННЯ ==========
    step("СТВОРЕННЯ ЦІНОУТВОРЕННЯ")

    # Роздрібні ціни
    retail_price_doc = PriceSettingDocument.objects.create(
        doc_number='PRICE-RETAIL-001',
        company=main_company,
        firm=main_firm,
        valid_from='2025-01-01',
        status='approved'
    )
    retail_price_doc.trade_points.add(trade_point_1, trade_point_2)

    retail_prices = [
        {'product': products['фарш'], 'price': 180, 'unit': unit_kg},
        {'product': products['окорок'], 'price': 220, 'unit': unit_kg},
        {'product': products['молоко'], 'price': 35, 'unit': unit_l},
        {'product': products['сир'], 'price': 280, 'unit': unit_kg},
        {'product': products['хліб'], 'price': 25, 'unit': unit_sht},
        {'product': products['булочка'], 'price': 15, 'unit': unit_sht},
        {'product': products['вода'], 'price': 12, 'unit': unit_l},
        {'product': products['сік'], 'price': 45, 'unit': unit_l},
        {'product': products['котлета'], 'price': 8, 'unit': unit_sht},
    ]

    for price_data in retail_prices:
        for tp in [trade_point_1, trade_point_2]:
            PriceSettingItem.objects.create(
                price_setting_document=retail_price_doc,
                product=price_data['product'],
                price_type=price_type_retail,
                trade_point=tp,
                firm=main_firm,
                price=price_data['price'],
                unit=price_data['unit'],
                vat_percent=20
            )
        success(f"Роздрібна ціна: {price_data['product'].name} - {price_data['price']} грн")

    # ========== ПОСТУПЛЕННЯ ==========
    step("СТВОРЕННЯ ПОСТУПЛЕНЬ")

    # Поступлення 1
    receipt_doc1 = Document.objects.create(
        doc_type='receipt',
        doc_number='REC-001',
        company=main_company,
        firm=main_firm,
        warehouse=central_warehouse,
        supplier=main_supplier
    )

    receipt1_items = [
        {'product': products['фарш'], 'qty': 50, 'cost': 120, 'unit': unit_kg},
        {'product': products['молоко'], 'qty': 100, 'cost': 22, 'unit': unit_l},
        {'product': products['хліб'], 'qty': 200, 'cost': 12, 'unit': unit_sht},
    ]

    for item_data in receipt1_items:
        DocumentItem.objects.create(
            document=receipt_doc1,
            product=item_data['product'],
            quantity=item_data['qty'],
            unit=item_data['unit'],
            price=item_data['cost'],
            vat_percent=20
        )

    ReceiptService(receipt_doc1).post()
    success(f"Поступлення {receipt_doc1.doc_number} проведено")

    # ========== ПРОДАЖІ ==========
    step("СТВОРЕННЯ ПРОДАЖІВ")

    sale_doc1 = Document.objects.create(
        doc_type='sale',
        doc_number='SAL-001',
        company=main_company,
        firm=main_firm,
        warehouse=central_warehouse,
        customer=retail_customer
    )

    sale1_items = [
        {'product': products['молоко'], 'qty': 20, 'price': 35, 'unit': unit_l},
        {'product': products['хліб'], 'qty': 50, 'price': 25, 'unit': unit_sht},
    ]

    for item_data in sale1_items:
        DocumentItem.objects.create(
            document=sale_doc1,
            product=item_data['product'],
            quantity=item_data['qty'],
            unit=item_data['unit'],
            price=item_data['price'],
            vat_percent=20
        )

    SaleService(sale_doc1).post()
    success(f"Продаж {sale_doc1.doc_number} проведено")

    # ========== ФАСУВАННЯ (ВИПРАВЛЕНЕ!) ==========
    step("СТВОРЕННЯ ФАСУВАННЯ")

    conversion_doc = Document.objects.create(
        doc_type='conversion',
        doc_number='CNV-001',
        company=main_company,
        firm=main_firm,
        warehouse=central_warehouse
    )

    # Source: 5 кг фаршу (ДОДАНА ЦІНА!)
    DocumentItem.objects.create(
        document=conversion_doc,
        product=products['фарш'],
        quantity=5,
        unit=unit_kg,
        price=120,  # ⬅️ ДОДАНА ЦІНА!
        vat_percent=20,
        role='source'
    )

    # Target: 25 котлет (ДОДАНА ЦІНА!)
    DocumentItem.objects.create(
        document=conversion_doc,
        product=products['котлета'],
        quantity=25,
        unit=unit_sht,
        price=0,  # ⬅️ БУДЕ РОЗРАХОВАНА АВТОМАТИЧНО
        vat_percent=20,
        role='target'
    )

    ConversionDocumentService(conversion_doc).post()
    success(f"Фасування {conversion_doc.doc_number} проведено")

    # ========== ПІДСУМОК ==========
    print(f"\n📊 ПІДСУМОК:")
    print(f"   📦 Поступлень: {Document.objects.filter(doc_type='receipt').count()}")
    print(f"   💰 Продажів: {Document.objects.filter(doc_type='sale').count()}")
    print(f"   🏭 Фасувань: {Document.objects.filter(doc_type='conversion').count()}")
    print(f"   📈 Операцій: {Operation.objects.count()}")

    # Показуємо залишки
    print(f"\n📋 ЗАЛИШКИ:")
    from backend.operations.stock import FIFOStockManager

    for key, product in products.items():
        if key in ['фарш', 'молоко', 'хліб', 'котлета']:
            stock = FIFOStockManager.get_available_stock(product, central_warehouse, main_firm)
            if stock > 0:
                value = FIFOStockManager.get_stock_value(product, central_warehouse, main_firm)
                avg_cost = value / stock if stock > 0 else 0
                print(
                    f"   {product.name}: {stock} {product.unit.symbol}, вартість {value:.2f}, сер.собівартість {avg_cost:.2f}")


if __name__ == "__main__":
    create_test_operations()