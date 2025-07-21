# create_business_scenario.py
# Реалістичний бізнес-сценарій: ФОП фасує фарш, ТЗОВ фасує віскі

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


def create_business_scenario():
    print("🏪 СТВОРЕННЯ БІЗНЕС-СЦЕНАРІЮ")
    print("=" * 60)
    print("📋 ФОП: фарш → пакетики")
    print("📋 ТЗОВ: віскі → порції")
    print("=" * 60)

    # ========== ОГОЛОШУЄМО ЗМІННІ ТОВАРІВ ==========
    # Будуть створені пізніше, але оголошуємо тут для видимості
    meat_packet = None
    whiskey_bottle = None
    whiskey_portion = None
    premium_cognac = None

    # ========== КРОК 1: БАЗОВІ НАЛАШТУВАННЯ ==========
    step("СТВОРЕННЯ БАЗОВИХ НАЛАШТУВАНЬ")

    # Очищуємо попередні дані
    Document.objects.all().delete()
    Operation.objects.all().delete()
    PriceSettingDocument.objects.all().delete()
    Product.objects.all().delete()
    Firm.objects.all().delete()
    Company.objects.all().delete()

    # Одиниці виміру
    unit_kg, _ = Unit.objects.get_or_create(name='кілограм', symbol='кг')
    unit_g, _ = Unit.objects.get_or_create(name='грам', symbol='г')
    unit_l, _ = Unit.objects.get_or_create(name='літр', symbol='л')
    unit_ml, _ = Unit.objects.get_or_create(name='мілілітр', symbol='мл')
    unit_sht, _ = Unit.objects.get_or_create(name='штука', symbol='шт')
    unit_pack, _ = Unit.objects.get_or_create(name='пакетик', symbol='пак')
    unit_portion, _ = Unit.objects.get_or_create(name='порція', symbol='порц')

    success("Одиниці виміру створено")

    # Типи цін
    price_retail, _ = PriceType.objects.get_or_create(name='Роздрібна', is_default=True)
    price_wholesale, _ = PriceType.objects.get_or_create(name='Оптова')

    success("Типи цін створено")

    # ========== КРОК 2: КОМПАНІЇ ТА ФІРМИ ==========
    step("СТВОРЕННЯ КОМПАНІЙ ТА ФІРМ")

    # Компанія
    company = Company.objects.create(
        name='Тестова Бізнес Група',
        tax_id='99999999'
    )
    success(f"Компанія: {company.name}")

    # Налаштування обліку
    AccountingSettings.objects.create(
        company=company,
        stock_account='281',
        supplier_account='631',
        vat_input_account='644',
        client_account='361',
        revenue_account='701',
        vat_output_account='641',
        default_vat_rate=Decimal('20.00'),
        default_price_type=price_retail
    )

    # Налаштування документів
    DocumentSettings.objects.create(
        company=company,
        receipt_prefix='REC',
        sale_prefix='SAL',
        conversion_prefix='CNV'
    )

    success("Налаштування створено")

    # Фірма 1: ФОП (без ПДВ)
    fop_firm = Firm.objects.create(
        name='ФОП М\'ясник',
        company=company,
        vat_type='ФОП'
    )
    success(f"ФОП фірма: {fop_firm.name} (БЕЗ ПДВ)")

    # Фірма 2: ТЗОВ (з ПДВ)
    tov_firm = Firm.objects.create(
        name='ТЗОВ Алкогольні Напої',
        company=company,
        vat_type='ТЗОВ'
    )
    success(f"ТЗОВ фірма: {tov_firm.name} (З ПДВ)")

    # ========== КРОК 3: СКЛАДИ ==========
    step("СТВОРЕННЯ СКЛАДІВ")

    fop_warehouse = Warehouse.objects.create(
        name='Склад ФОП М\'ясника',
        company=company
    )
    success(f"Склад ФОП: {fop_warehouse.name}")

    tov_warehouse = Warehouse.objects.create(
        name='Склад ТЗОВ Алкоголь',
        company=company
    )
    success(f"Склад ТЗОВ: {tov_warehouse.name}")

    # ========== КРОК 4: КОНТРАГЕНТИ ==========
    step("СТВОРЕННЯ КОНТРАГЕНТІВ")

    # Постачальники
    meat_supplier = Supplier.objects.create(
        name='М\'ясокомбінат Україна',
        tax_id='11111111'
    )
    success(f"Постачальник м\'яса: {meat_supplier.name}")

    alcohol_supplier = Supplier.objects.create(
        name='Алкогольний Дистриб\'ютор',
        tax_id='22222222'
    )
    success(f"Постачальник алкоголю: {alcohol_supplier.name}")

    # Клієнти
    retail_customer = Customer.objects.create(
        name='Роздрібний покупець'
    )
    success(f"Клієнт: {retail_customer.name}")

    # ========== КРОК 5: ТОВАРИ ==========
    step("СТВОРЕННЯ ТОВАРІВ")

    # Товари для ФОП
    minced_meat = Product.objects.create(
        name='Фарш свинячий (опт)',
        firm=fop_firm,
        unit=unit_kg,
        type='product'
    )
    success(f"Товар ФОП: {minced_meat.name}")

    meat_packet = Product.objects.create(
        name='Фарш в пакетику 100г',
        firm=fop_firm,
        unit=unit_pack,
        type='semi'  # Напівфабрикат з фасування
    )
    success(f"Фасований товар ФОП: {meat_packet.name}")

    # Товари для ТЗОВ
    whiskey_bottle = Product.objects.create(
        name='Віскі 700мл (пляшка)',
        firm=tov_firm,
        unit=unit_sht,
        type='product'
    )
    success(f"Товар ТЗОВ: {whiskey_bottle.name}")

    whiskey_portion = Product.objects.create(
        name='Віскі порція 50мл',
        firm=tov_firm,
        unit=unit_portion,
        type='semi'  # Напівфабрикат з фасування
    )
    success(f"Фасований товар ТЗОВ: {whiskey_portion.name}")

    # ========== КРОК 6: ТОРГОВІ ТОЧКИ ==========
    step("СТВОРЕННЯ ТОРГОВИХ ТОЧОК")

    meat_shop = TradePoint.objects.create(
        name='М\'ясна лавка ФОП',
        firm=fop_firm
    )
    success(f"Торгова точка ФОП: {meat_shop.name}")

    bar = TradePoint.objects.create(
        name='Бар ТЗОВ',
        firm=tov_firm
    )
    success(f"Торгова точка ТЗОВ: {bar.name}")

    # ========== КРОК 7: ЦІНОУТВОРЕННЯ ==========
    step("НАЛАШТУВАННЯ ЦІН")

    # Ціни ФОП (без ПДВ)
    fop_prices = PriceSettingDocument.objects.create(
        doc_number='PRICE-FOP-001',
        company=company,
        firm=fop_firm,
        valid_from='2025-01-01',
        status='approved'
    )
    fop_prices.trade_points.add(meat_shop)

    PriceSettingItem.objects.create(
        price_setting_document=fop_prices,
        product=meat_packet,
        price_type=price_retail,
        trade_point=meat_shop,
        firm=fop_firm,
        price=50,  # 50 грн за пакетик
        unit=unit_pack,
        vat_percent=0  # ФОП без ПДВ
    )
    success("Ціна ФОП: фарш пакетик 50 грн (без ПДВ)")

    # Ціни ТЗОВ (з ПДВ)
    tov_prices = PriceSettingDocument.objects.create(
        doc_number='PRICE-TOV-001',
        company=company,
        firm=tov_firm,
        valid_from='2025-01-01',
        status='approved'
    )
    tov_prices.trade_points.add(bar)

    PriceSettingItem.objects.create(
        price_setting_document=tov_prices,
        product=whiskey_portion,
        price_type=price_retail,
        trade_point=bar,
        firm=tov_firm,
        price=100,  # 100 грн за порцію
        unit=unit_portion,
        vat_percent=20  # ТЗОВ з ПДВ
    )
    success("Ціна ТЗОВ: віскі порція 100 грн (з ПДВ)")

    # Ціна на преміум коньяк (змінну отримаємо пізніше)
    # Додамо після створення товару

    # ========== КРОК 8: ПОСТУПЛЕННЯ ==========
    step("ПОСТУПЛЕННЯ ТОВАРІВ")

    # Поступлення фаршу на ФОП
    meat_receipt = Document.objects.create(
        doc_type='receipt',
        doc_number='REC-FOP-001',
        company=company,
        firm=fop_firm,
        warehouse=fop_warehouse,
        supplier=meat_supplier
    )

    DocumentItem.objects.create(
        document=meat_receipt,
        product=minced_meat,
        quantity=1,  # 1 кг
        unit=unit_kg,
        price=100,  # 100 грн за кг (без ПДВ для ФОП)
        vat_percent=0
    )

    ReceiptService(meat_receipt).post()
    success("Поступлення ФОП: 1кг фаршу за 100 грн")

    # Поступлення віскі на ТЗОВ
    whiskey_receipt = Document.objects.create(
        doc_type='receipt',
        doc_number='REC-TOV-001',
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse,
        supplier=alcohol_supplier
    )

    DocumentItem.objects.create(
        document=whiskey_receipt,
        product=whiskey_bottle,
        quantity=1,  # 1 пляшка
        unit=unit_sht,
        price=500,  # 500 грн за пляшку (без ПДВ, ПДВ додасться)
        vat_percent=20
    )

    # Застосовуємо правильну логіку ПДВ для поступлення ТЗОВ
    from backend.services.document_services import apply_vat
    for item in whiskey_receipt.items.all():
        apply_vat(item, mode="from_price_without_vat")  # Ціна БЕЗ ПДВ, додаємо ПДВ

    ReceiptService(whiskey_receipt).post()
    success("Поступлення ТЗОВ: 1 пляшка віскі за 500 грн + ПДВ")

    # ========== КРОК 9: ФАСУВАННЯ ==========
    step("ФАСУВАННЯ ТОВАРІВ")

    # Фасування фаршу: 1кг → 10 пакетиків по 100г
    meat_conversion = Document.objects.create(
        doc_type='conversion',
        doc_number='CNV-FOP-001',
        company=company,
        firm=fop_firm,
        warehouse=fop_warehouse
    )

    # Source: 1кг фаршу
    DocumentItem.objects.create(
        document=meat_conversion,
        product=minced_meat,
        quantity=1,
        unit=unit_kg,
        price=100,  # Собівартість
        vat_percent=0,
        role='source'
    )

    # Target: 10 пакетиків по 100г
    DocumentItem.objects.create(
        document=meat_conversion,
        product=meat_packet,
        quantity=10,
        unit=unit_pack,
        price=0,  # Розрахується автоматично
        vat_percent=0,
        role='target'
    )

    ConversionDocumentService(meat_conversion).post()
    success("Фасування ФОП: 1кг фаршу → 10 пакетиків")

    # Фасування віскі: 700мл → 14 порцій по 50мл
    whiskey_conversion = Document.objects.create(
        doc_type='conversion',
        doc_number='CNV-TOV-001',
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse
    )

    # Source: 1 пляшка 700мл
    DocumentItem.objects.create(
        document=whiskey_conversion,
        product=whiskey_bottle,
        quantity=1,
        unit=unit_sht,
        price=500,  # Собівартість без ПДВ
        vat_percent=20,
        role='source'
    )

    # Target: 14 порцій по 50мл (700мл / 50мл = 14)
    DocumentItem.objects.create(
        document=whiskey_conversion,
        product=whiskey_portion,
        quantity=14,
        unit=unit_portion,
        price=0,  # Розрахується автоматично
        vat_percent=20,
        role='target'
    )

    ConversionDocumentService(whiskey_conversion).post()
    success("Фасування ТЗОВ: 1 пляшка → 14 порцій")

    # ========== ОПРИБУТКУВАННЯ ВЛАСНОГО ВИРОБНИЦТВА ==========
    info("Оприбуткування коньяку власного виробництва")

    # Створюємо або отримуємо товар коньяк
    premium_cognac, created = Product.objects.get_or_create(
        name='Коньяк преміум власного виробництва',
        firm=tov_firm,
        defaults={
            'unit': unit_sht,
            'type': 'product'
        }
    )
    if created:
        success(f"Створено товар для оприбуткування: {premium_cognac.name}")

        # Додаємо ціну на коньяк
        PriceSettingItem.objects.create(
            price_setting_document=tov_prices,
            product=premium_cognac,
            price_type=price_retail,
            trade_point=bar,
            firm=tov_firm,
            price=2000,  # 2000 грн за пляшку
            unit=unit_sht,
            vat_percent=20  # ТЗОВ з ПДВ
        )
        success("Ціна ТЗОВ: коньяк преміум 2000 грн (з ПДВ)")

    # Оприбуткування коньяку власного виробництва
    inventory_doc = Document.objects.create(
        doc_type='inventory_in',
        # doc_number створюється автоматично
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse
    )

    DocumentItem.objects.create(
        document=inventory_doc,
        product=premium_cognac,  # Тепер змінна доступна
        quantity=3,  # 3 пляшки власного виробництва
        unit=unit_sht,
        price=800,  # Собівартість виробництва 800 грн за пляшку
        vat_percent=20
    )

    # Застосовуємо логіку ПДВ для оприбуткування
    from backend.services.document_services import apply_vat
    for item in inventory_doc.items.all():
        apply_vat(item, mode="from_price_without_vat")  # Собівартість БЕЗ ПДВ

    InventoryInService(inventory_doc).post()
    success("Оприбуткування ТЗОВ: 3 пляшки коньяку по 800 грн собівартість")

    # ========== КРОК 9.1: ОПРИБУТКУВАННЯ ==========
    step("ОПРИБУТКУВАННЯ ВЛАСНОГО ВИРОБНИЦТВА")

    # Оприбуткування коньяку власного виробництва
    inventory_doc = Document.objects.create(
        doc_type='inventory_in',
        doc_number='INV-TOV-001',
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse
    )

    DocumentItem.objects.create(
        document=inventory_doc,
        product=premium_cognac,  # Використовуємо змінну зі створення товарів
        quantity=3,  # 3 пляшки власного виробництва
        unit=unit_sht,
        price=800,  # Собівартість виробництва 800 грн за пляшку
        vat_percent=20
    )

    # Застосовуємо логіку ПДВ для оприбуткування
    for item in inventory_doc.items.all():
        apply_vat(item, mode="from_price_without_vat")  # Собівартість БЕЗ ПДВ

    InventoryInService(inventory_doc).post()
    success("Оприбуткування ТЗОВ: 3 пляшки коньяку по 800 грн собівартість")

    # ========== КРОК 10: ПРОДАЖІ ==========
    step("ПРОДАЖІ ТОВАРІВ")

    # Продаж пакетиків фаршу (ФОП)
    meat_sale = Document.objects.create(
        doc_type='sale',
        doc_number='SAL-FOP-001',
        company=company,
        firm=fop_firm,
        warehouse=fop_warehouse,
        customer=retail_customer
    )

    DocumentItem.objects.create(
        document=meat_sale,
        product=meat_packet,
        quantity=7,  # Продали 7 з 10 пакетиків
        unit=unit_pack,
        price=50,  # 50 грн за пакетик
        vat_percent=0  # ФОП без ПДВ
    )

    SaleService(meat_sale).post()
    success("Продаж ФОП: 7 пакетиків фаршу по 50 грн")

    # Продаж порцій віскі (ТЗОВ)
    whiskey_sale = Document.objects.create(
        doc_type='sale',
        doc_number='SAL-TOV-001',
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse,
        customer=retail_customer
    )

    DocumentItem.objects.create(
        document=whiskey_sale,
        product=whiskey_portion,
        quantity=10,  # Продали 10 з 14 порцій
        unit=unit_portion,
        price=100,  # 100 грн за порцію
        vat_percent=20  # ТЗОВ з ПДВ
    )

    # Застосовуємо правильну логіку ПДВ для ТЗОВ
    from backend.services.document_services import apply_vat
    for item in whiskey_sale.items.all():
        apply_vat(item, mode="from_price_with_vat")  # Ціна ВКЛЮЧАЄ ПДВ

    SaleService(whiskey_sale).post()
    success("Продаж ТЗОВ: 10 порцій віскі по 100 грн (З ПДВ)")

    # ========== ПРОДАЖ КОНЬЯКУ ВЛАСНОГО ВИРОБНИЦТВА ==========
    info("Продаж коньяку власного виробництва")

    # Отримуємо товар коньяк
    premium_cognac = Product.objects.get(name='Коньяк преміум власного виробництва')

    # Продаж коньяку преміум
    cognac_sale = Document.objects.create(
        doc_type='sale',
        # doc_number створюється автоматично
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse,
        customer=retail_customer
    )

    DocumentItem.objects.create(
        document=cognac_sale,
        product=premium_cognac,  # Тепер змінна доступна
        quantity=2,  # Продали 2 з 3 пляшок
        unit=unit_sht,
        price=2000,  # 2000 грн за пляшку З ПДВ
        vat_percent=20
    )

    # Застосовуємо правильну логіку ПДВ
    for item in cognac_sale.items.all():
        apply_vat(item, mode="from_price_with_vat")  # Ціна ВКЛЮЧАЄ ПДВ

    SaleService(cognac_sale).post()
    success("Продаж ТЗОВ: 2 пляшки коньяку по 2000 грн (З ПДВ)")

    # ========== КРОК 10.1: ПРОДАЖ ОПРИБУТКОВАНОГО ТОВАРУ ==========
    step("ПРОДАЖ КОНЬЯКУ ВЛАСНОГО ВИРОБНИЦТВА")

    # Продаж коньяку преміум
    cognac_sale = Document.objects.create(
        doc_type='sale',
        doc_number='SAL-TOV-002',
        company=company,
        firm=tov_firm,
        warehouse=tov_warehouse,
        customer=retail_customer
    )

    DocumentItem.objects.create(
        document=cognac_sale,
        product=premium_cognac,  # Використовуємо змінну зі створення товарів
        quantity=2,  # Продали 2 з 3 пляшок
        unit=unit_sht,
        price=2000,  # 2000 грн за пляшку З ПДВ
        vat_percent=20
    )

    # Застосовуємо правильну логіку ПДВ
    for item in cognac_sale.items.all():
        apply_vat(item, mode="from_price_with_vat")  # Ціна ВКЛЮЧАЄ ПДВ

    SaleService(cognac_sale).post()
    success("Продаж ТЗОВ: 2 пляшки коньяку по 2000 грн (З ПДВ)")

    # ========== ПІДСУМОК ==========
    print(f"\n📊 ПІДСУМОК БІЗНЕС-СЦЕНАРІЮ:")
    print(f"   🏢 Компаній: {Company.objects.count()}")
    print(f"   🏭 Фірм: {Firm.objects.count()}")
    print(f"   📦 Складів: {Warehouse.objects.count()}")
    print(f"   📋 Товарів: {Product.objects.count()}")
    print(f"   📄 Документів: {Document.objects.count()}")
    print(f"   📈 Операцій: {Operation.objects.count()}")

    # Залишки
    print(f"\n📋 ЗАЛИШКИ НА СКЛАДАХ:")
    from backend.operations.stock import FIFOStockManager

    # ФОП залишки
    meat_stock = FIFOStockManager.get_available_stock(meat_packet, fop_warehouse, fop_firm)
    meat_value = FIFOStockManager.get_stock_value(meat_packet, fop_warehouse, fop_firm)
    print(f"   ФОП: {meat_packet.name} - {meat_stock} пак, вартість {meat_value:.2f}")

    # ТЗОВ залишки
    whiskey_stock = FIFOStockManager.get_available_stock(whiskey_portion, tov_warehouse, tov_firm)
    whiskey_value = FIFOStockManager.get_stock_value(whiskey_portion, tov_warehouse, tov_firm)
    print(f"   ТЗОВ: {whiskey_portion.name} - {whiskey_stock} порц, вартість {whiskey_value:.2f}")

    # Залишки коньяку
    try:
        premium_cognac = Product.objects.get(name='Коньяк преміум власного виробництва')
        cognac_stock = FIFOStockManager.get_available_stock(premium_cognac, tov_warehouse, tov_firm)
        cognac_value = FIFOStockManager.get_stock_value(premium_cognac, tov_warehouse, tov_firm)
        print(f"   ТЗОВ: {premium_cognac.name} - {cognac_stock} шт, вартість {cognac_value:.2f}")
    except Product.DoesNotExist:
        print(f"   ТЗОВ: Коньяк - товар не знайдено")

    # Показуємо детальний ПДВ аналіз
    print(f"\n🧾 АНАЛІЗ ПДВ ТЗОВ:")

    # ПДВ з покупки
    receipt_items = DocumentItem.objects.filter(
        document__doc_type='receipt',
        document__firm=tov_firm
    )
    vat_from_purchases = sum(float(item.vat_amount or 0) * float(item.quantity) for item in receipt_items)

    # ПДВ з продажу
    sale_items = DocumentItem.objects.filter(
        document__doc_type='sale',
        document__firm=tov_firm
    )
    vat_from_sales = sum(float(item.vat_amount or 0) * float(item.quantity) for item in sale_items)

    vat_to_pay = vat_from_sales - vat_from_purchases

    print(f"   ПДВ з покупки: {vat_from_purchases:.2f} грн (до відшкодування)")
    print(f"   ПДВ з продажу: {vat_from_sales:.2f} грн (нарахований)")
    print(f"   ПДВ до доплати: {vat_to_pay:.2f} грн")

    print(f"\n✅ БІЗНЕС-СЦЕНАРІЙ СТВОРЕНО!")

    return {
        'fop_firm': fop_firm,
        'tov_firm': tov_firm,
        'meat_packet': meat_packet,
        'whiskey_portion': whiskey_portion,
        'premium_cognac': Product.objects.filter(name='Коньяк преміум власного виробництва').first(),
        'fop_warehouse': fop_warehouse,
        'tov_warehouse': tov_warehouse,
        'company': company
    }


if __name__ == "__main__":
    create_business_scenario()