# create_simple_erp_setup.py
# Простий скрипт для створення базових налаштувань ERP системи

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from datetime import date
from backend.models import *
from settlements.models import *


def step(message):
    print(f"\n🔄 {message}")
    print("   " + "─" * (len(message) + 2))


def success(message):
    print(f"   ✅ {message}")


def create_simple_erp_setup():
    print("🏪 СТВОРЕННЯ БАЗОВОГО НАЛАШТУВАННЯ ERP")
    print("=" * 50)

    # ========== ОЧИЩЕННЯ СТАРИХ ДАНИХ ==========
    step("ОЧИЩЕННЯ СТАРИХ ДАНИХ")

    Document.objects.all().delete()
    Operation.objects.all().delete()
    PriceSettingDocument.objects.all().delete()
    ProductUnitConversion.objects.all().delete()
    Product.objects.all().delete()
    Contract.objects.all().delete()
    Account.objects.all().delete()
    TradePoint.objects.all().delete()
    Warehouse.objects.all().delete()
    Firm.objects.all().delete()
    Company.objects.all().delete()
    Customer.objects.all().delete()
    Supplier.objects.all().delete()
    PaymentType.objects.all().delete()
    CustomerType.objects.all().delete()

    success("Старі дані видалено")

    # ========== ОДИНИЦІ ВИМІРУ ==========
    step("СТВОРЕННЯ ОДИНИЦЬ ВИМІРУ")

    unit_kg = Unit.objects.get_or_create(name='кілограм', defaults={'symbol': 'кг'})[0]
    unit_g = Unit.objects.get_or_create(name='грам', defaults={'symbol': 'г'})[0]
    unit_sht = Unit.objects.get_or_create(name='штука', defaults={'symbol': 'шт'})[0]

    success(f"Створено одиниці виміру: кг, г, шт")

    # ========== ТИПИ ЦІН ==========
    step("СТВОРЕННЯ ТИПІВ ЦІН")

    price_retail = PriceType.objects.get_or_create(
        name='Роздрібна',
        defaults={'is_default': True}
    )[0]

    success("Тип ціни: Роздрібна (за замовчуванням)")

    # ========== ТИПИ КЛІЄНТІВ ==========
    step("СТВОРЕННЯ ТИПІВ КЛІЄНТІВ")

    customer_type_retail = CustomerType.objects.create(name='Роздрібний')
    customer_type_wholesale = CustomerType.objects.create(name='Оптовий')

    success("Типи клієнтів: Роздрібний, Оптовий")

    # ========== ТИПИ ОПЛАТ ==========
    step("СТВОРЕННЯ ТИПІВ ОПЛАТ")

    payment_cash = PaymentType.objects.create(name='Готівка')
    payment_card = PaymentType.objects.create(name='Картка')

    success("Типи оплат: Готівка, Картка")

    # ========== КОМПАНІЯ ==========
    step("СТВОРЕННЯ КОМПАНІЇ")

    company = Company.objects.create(
        name='Тестова Компанія',
        tax_id='12345678'
    )

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
        conversion_prefix='CNV',
        transfer_prefix='TRF',
        inventory_prefix='INV',
        stock_in_prefix='STI'
    )

    success(f"Компанія: {company.name}")

    # ========== ФІРМА ==========
    step("СТВОРЕННЯ ФІРМИ")

    firm = Firm.objects.create(
        name='ФОП Тестовий',
        company=company,
        vat_type='ФОП'  # Без ПДВ для простоти
    )

    success(f"Фірма: {firm.name} (без ПДВ)")

    # ========== СКЛАД ==========
    step("СТВОРЕННЯ СКЛАДУ")

    warehouse = Warehouse.objects.create(
        name='Основний склад',
        company=company
    )

    success(f"Склад: {warehouse.name}")

    # ========== ТОРГОВА ТОЧКА ==========
    step("СТВОРЕННЯ ТОРГОВОЇ ТОЧКИ")

    trade_point = TradePoint.objects.create(
        name='Торгова точка #1',
        firm=firm
    )

    success(f"Торгова точка: {trade_point.name}")

    # ========== КОНТРАГЕНТИ ==========
    step("СТВОРЕННЯ КОНТРАГЕНТІВ")

    # Постачальник
    supplier = Supplier.objects.create(
        name='Постачальник ТОВ "Продукти"',
        tax_id='87654321'
    )

    # Клієнт
    customer = Customer.objects.create(
        name='Роздрібний покупець',
        type=customer_type_retail
    )

    success(f"Постачальник: {supplier.name}")
    success(f"Клієнт: {customer.name}")

    # ========== РАХУНКИ ==========
    step("СТВОРЕННЯ РАХУНКІВ")

    account_cash = Account.objects.create(
        company=company,
        name='Каса',
        type='cash'
    )

    account_bank = Account.objects.create(
        company=company,
        name='Банківський рахунок',
        type='bank'
    )

    success(f"Рахунки: {account_cash.name}, {account_bank.name}")

    # ========== ДОГОВОРИ ==========
    step("СТВОРЕННЯ ДОГОВОРІВ")

    # Договір з постачальником
    supplier_contract = Contract.objects.create(
        name='Договір постачання #001',
        supplier=supplier,
        contract_type='Стандартний',
        payment_type=payment_cash,
        account=account_bank,
        is_active=True,
        status='active'
    )

    # Договір з клієнтом
    customer_contract = Contract.objects.create(
        name='Договір з клієнтом #001',
        client=customer,
        contract_type='Стандартний',
        payment_type=payment_cash,
        account=account_cash,
        is_active=True,
        status='active'
    )

    success(f"Договір з постачальником: {supplier_contract.name}")
    success(f"Договір з клієнтом: {customer_contract.name}")

    # ========== ТОВАР ==========
    step("СТВОРЕННЯ ТОВАРУ")

    product = Product.objects.create(
        name='Фарш свинячий',
        firm=firm,
        unit=unit_kg,  # Базова одиниця: кг
        type='product'
    )

    success(f"Товар: {product.name} (базова од.: {product.unit.name})")

    # ========== ФАСУВАННЯ ==========
    step("СТВОРЕННЯ ФАСУВАННЯ")

    # Фасування: грам → кілограм (1000 грам = 1 кг)
    unit_conversion = ProductUnitConversion.objects.create(
        product=product,
        name='Грам',
        from_unit=unit_kg,    # кілограм
        to_unit=unit_g,       # грам
        factor=1000           # 1 кг = 1000 грам
    )

    success(f"Фасування: {unit_conversion.name} (1 кг = {unit_conversion.factor} г)")

    # ========== ЦІНОУТВОРЕННЯ ==========
    step("СТВОРЕННЯ ЦІНОУТВОРЕННЯ")

    price_doc = PriceSettingDocument.objects.create(
        company=company,
        firm=firm,
        valid_from=date.today(),
        status='approved'
    )
    price_doc.trade_points.add(trade_point)

    # Ціна за базову одиницю (кг)
    price_item_kg = PriceSettingItem.objects.create(
        price_setting_document=price_doc,
        product=product,
        price_type=price_retail,
        trade_point=trade_point,
        firm=firm,
        price=250,  # 250 грн за кг
        unit=unit_kg,
        unit_conversion=None,  # Базова одиниця
        vat_percent=0,
        vat_included=False
    )

    # Ціна за фасування (грам)
    price_item_g = PriceSettingItem.objects.create(
        price_setting_document=price_doc,
        product=product,
        price_type=price_retail,
        trade_point=trade_point,
        firm=firm,
        price=0.25,  # 0.25 грн за грам
        unit=unit_g,
        unit_conversion=unit_conversion,  # Фасування
        vat_percent=0,
        vat_included=False
    )

    success(f"Ціна за кг: {price_item_kg.price} грн")
    success(f"Ціна за грам: {price_item_g.price} грн")
    success(f"Документ ціноутворення: {price_doc.doc_number}")

    # ========== ПІДСУМОК ==========
    print(f"\n📊 ПІДСУМОК НАЛАШТУВАНЬ:")
    print(f"   🏢 Компанія: {company.name}")
    print(f"   🏭 Фірма: {firm.name}")
    print(f"   📦 Склад: {warehouse.name}")
    print(f"   🏪 Торгова точка: {trade_point.name}")
    print(f"   📋 Товар: {product.name}")
    print(f"   📏 Фасування: {unit_conversion.name}")
    print(f"   🤝 Постачальник: {supplier.name}")
    print(f"   👥 Клієнт: {customer.name}")
    print(f"   📄 Договорів: {Contract.objects.count()}")
    print(f"   💰 Ціноутворення: {price_doc.doc_number}")
    print(f"   💳 Рахунків: {Account.objects.count()}")

    print(f"\n✅ БАЗОВЕ НАЛАШТУВАННЯ СТВОРЕНО!")
    print(f"🚀 Тепер можете тестувати документи!")

    print(f"\n📝 ДЛЯ ТЕСТУВАННЯ:")
    print(f"   1. Створіть поступлення товару")
    print(f"   2. Проведіть поступлення")
    print(f"   3. Створіть продаж з автопідстановкою цін")
    print(f"   4. Перевірте FIFO та рентабельність")

    return {
        'company': company,
        'firm': firm,
        'warehouse': warehouse,
        'trade_point': trade_point,
        'product': product,
        'unit_conversion': unit_conversion,
        'supplier': supplier,
        'customer': customer,
        'supplier_contract': supplier_contract,
        'customer_contract': customer_contract,
        'price_doc': price_doc
    }


if __name__ == "__main__":
    create_simple_erp_setup()