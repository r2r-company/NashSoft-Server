# test_cost_logic.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from backend.models import *
from backend.services.document_services import *
from backend.operations.stock import FIFOStockManager


def test_cost_logic():
    print("🧪 ТЕСТУВАННЯ НОВОЇ ЛОГІКИ СОБІВАРТОСТІ")
    print("=" * 50)

    # Отримуємо або створюємо тестові дані
    company, _ = Company.objects.get_or_create(name="Тестова компанія")
    firm, _ = Firm.objects.get_or_create(
        name="Тестова фірма",
        company=company,
        defaults={'vat_type': 'ТОВ'}
    )
    warehouse, _ = Warehouse.objects.get_or_create(
        name="Тестовий склад",
        company=company
    )
    supplier, _ = Supplier.objects.get_or_create(name="Тестовий постачальник")
    customer, _ = Customer.objects.get_or_create(name="Тестовий клієнт")

    unit, _ = Unit.objects.get_or_create(name="шт", symbol="шт")

    # Створюємо тестові товари
    product1, _ = Product.objects.get_or_create(
        name="Тестовий товар 1",
        firm=firm,
        defaults={'unit': unit, 'type': 'product'}
    )
    product2, _ = Product.objects.get_or_create(
        name="Тестовий товар 2",
        firm=firm,
        defaults={'unit': unit, 'type': 'product'}
    )

    print(f"✅ Створено тестові дані")

    # 🧪 ТЕСТ 1: ПОСТУПЛЕННЯ
    print("\n📦 ТЕСТ 1: ПОСТУПЛЕННЯ")
    receipt_doc = Document.objects.create(
        doc_type='receipt',
        doc_number='TEST-001',
        company=company,
        firm=firm,
        warehouse=warehouse,
        supplier=supplier
    )

    DocumentItem.objects.create(
        document=receipt_doc,
        product=product1,
        quantity=10,
        unit=unit,
        price=100,  # Ціна закупки
        vat_percent=20
    )

    # Проводимо поступлення
    receipt_service = ReceiptService(receipt_doc)
    receipt_service.post()

    # Перевіряємо операції
    ops = Operation.objects.filter(document=receipt_doc)
    for op in ops:
        print(f"   Операція: {op.product.name}, кількість: {op.quantity}, собівартість: {op.cost_price}")

    # 🧪 ТЕСТ 2: ДРУГЕ ПОСТУПЛЕННЯ (інша ціна)
    print("\n📦 ТЕСТ 2: ДРУГЕ ПОСТУПЛЕННЯ")
    receipt_doc2 = Document.objects.create(
        doc_type='receipt',
        doc_number='TEST-002',
        company=company,
        firm=firm,
        warehouse=warehouse,
        supplier=supplier
    )

    DocumentItem.objects.create(
        document=receipt_doc2,
        product=product1,
        quantity=5,
        unit=unit,
        price=120,  # Інша ціна закупки
        vat_percent=20
    )

    receipt_service2 = ReceiptService(receipt_doc2)
    receipt_service2.post()

    # Перевіряємо залишки
    stock = FIFOStockManager.get_available_stock(product1, warehouse, firm)
    print(f"   Залишок товару: {stock} шт")

    # 🧪 ТЕСТ 3: ПРОДАЖ (FIFO)
    print("\n💰 ТЕСТ 3: ПРОДАЖ (FIFO)")

    # Створюємо тип ціни і ціноутворення
    price_type, _ = PriceType.objects.get_or_create(name="Роздрібна", is_default=True)

    sale_doc = Document.objects.create(
        doc_type='sale',
        doc_number='TEST-003',
        company=company,
        firm=firm,
        warehouse=warehouse,
        customer=customer
    )

    DocumentItem.objects.create(
        document=sale_doc,
        product=product1,
        quantity=8,
        unit=unit,
        price=150,  # Ціна продажу
        vat_percent=20
    )

    sale_service = SaleService(sale_doc)
    sale_service.post()

    # Перевіряємо операції продажу
    sale_ops = Operation.objects.filter(document=sale_doc, direction='out')
    total_cost = 0
    total_sale = 0
    for op in sale_ops:
        print(f"   Продано: {op.product.name}, кількість: {op.quantity}")
        print(f"   Собівартість: {op.cost_price}, Ціна продажу: {op.sale_price}")
        print(f"   Прибуток за позицію: {op.profit}")
        total_cost += op.total_cost
        total_sale += op.total_sale or 0

    print(f"   ЗАГАЛЬНИЙ ПРИБУТОК: {total_sale - total_cost}")

    # 🧪 ТЕСТ 4: ФАСУВАННЯ
    print("\n🔄 ТЕСТ 4: ФАСУВАННЯ")

    conversion_doc = Document.objects.create(
        doc_type='conversion',
        doc_number='TEST-004',
        company=company,
        firm=firm,
        warehouse=warehouse
    )

    # Source товар (що розбираємо)
    DocumentItem.objects.create(
        document=conversion_doc,
        product=product1,
        quantity=2,  # Залишилось 7, беремо 2
        unit=unit,
        price=0,
        role='source'
    )

    # Target товар (що отримуємо)
    DocumentItem.objects.create(
        document=conversion_doc,
        product=product2,
        quantity=4,  # Отримуємо 4 од нового товару
        unit=unit,
        price=0,
        role='target'
    )

    conversion_service = ConversionDocumentService(conversion_doc)
    conversion_service.post()

    # Перевіряємо результат фасування
    conversion_ops = Operation.objects.filter(document=conversion_doc)
    for op in conversion_ops:
        print(f"   {op.direction.upper()}: {op.product.name}, кількість: {op.quantity}, собівартість: {op.cost_price}")

    # Перевіряємо фінальні залишки
    print("\n📊 ФІНАЛЬНІ ЗАЛИШКИ:")
    stock1 = FIFOStockManager.get_available_stock(product1, warehouse, firm)
    stock2 = FIFOStockManager.get_available_stock(product2, warehouse, firm)
    value1 = FIFOStockManager.get_stock_value(product1, warehouse, firm)
    value2 = FIFOStockManager.get_stock_value(product2, warehouse, firm)

    print(f"   {product1.name}: {stock1} шт, вартість: {value1}")
    print(f"   {product2.name}: {stock2} шт, вартість: {value2}")
    print(f"   ЗАГАЛЬНА ВАРТІСТЬ ЗАЛИШКІВ: {value1 + value2}")

    print("\n✅ ТЕСТУВАННЯ ЗАВЕРШЕНО!")


if __name__ == "__main__":
    test_cost_logic()