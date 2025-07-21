# create_test_system.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from backend.models import *
from backend.services.document_services import *
from settlements.models import *
import time


def step(message):
    """Красивий вивід кроків"""
    print(f"\n🔄 {message}")
    print("   " + "─" * (len(message) + 2))


def success(message):
    """Успішний результат"""
    print(f"   ✅ {message}")


def create_test_system():
    print("🚀 СТВОРЕННЯ ПОВНОЇ ТЕСТОВОЇ СИСТЕМИ")
    print("=" * 60)

    # ========== КРОК 1: БАЗОВІ НАЛАШТУВАННЯ ==========
    step("СТВОРЕННЯ БАЗОВИХ НАЛАШТУВАНЬ")

    # Одиниці виміру
    units_data = [
        {'name': 'штука', 'symbol': 'шт'},
        {'name': 'кілограм', 'symbol': 'кг'},
        {'name': 'літр', 'symbol': 'л'},
        {'name': 'метр', 'symbol': 'м'},
        {'name': 'упаковка', 'symbol': 'упак'},
    ]

    units = {}
    for unit_data in units_data:
        unit = Unit.objects.create(**unit_data)
        units[unit_data['symbol']] = unit
        success(f"Одиниця виміру: {unit.name}")

    # Типи клієнтів
    customer_types_data = ['Роздрібний', 'Оптовий', 'VIP-клієнт', 'Дистриб\'ютор']
    customer_types = {}
    for ct_name in customer_types_data:
        ct = CustomerType.objects.create(name=ct_name)
        customer_types[ct_name] = ct
        success(f"Тип клієнта: {ct_name}")

    # Типи оплати
    payment_types_data = ['Готівка', 'Безготівка', 'Карта', 'Змішана']
    payment_types = {}
    for pt_name in payment_types_data:
        pt = PaymentType.objects.create(name=pt_name)
        payment_types[pt_name] = pt
        success(f"Тип оплати: {pt_name}")

    # Типи цін
    price_types_data = [
        {'name': 'Роздрібна', 'is_default': True},
        {'name': 'Оптова', 'is_default': False},
        {'name': 'VIP', 'is_default': False},
        {'name': 'Акційна', 'is_default': False},
    ]
    price_types = {}
    for pt_data in price_types_data:
        pt = PriceType.objects.create(**pt_data)
        price_types[pt_data['name']] = pt
        success(f"Тип ціни: {pt_data['name']}")

    # ========== КРОК 2: КОМПАНІЇ ТА СТРУКТУРА ==========
    step("СТВОРЕННЯ КОМПАНІЙ ТА СТРУКТУРИ")

    # Компанії
    companies_data = [
        {'name': 'ТОВ "Тестова Торгівля"', 'tax_id': '12345678'},
        {'name': 'ФОП Іваненко І.І.', 'tax_id': '87654321'},
    ]

    companies = {}
    for comp_data in companies_data:
        company = Company.objects.create(**comp_data)
        companies[comp_data['name']] = company
        success(f"Компанія: {company.name}")

        # Налаштування обліку для кожної компанії
        AccountingSettings.objects.create(
            company=company,
            stock_account='281',
            supplier_account='631',
            vat_input_account='644',
            client_account='361',
            revenue_account='701',
            vat_output_account='641',
            default_vat_rate=Decimal('20.00'),
            default_price_type=price_types['Роздрібна']
        )
        success(f"Налаштування обліку для {company.name}")

        # Налаштування документів
        DocumentSettings.objects.create(
            company=company,
            receipt_prefix='REC',
            sale_prefix='SAL',
            return_to_supplier_prefix='RTS',
            return_from_client_prefix='RFC',
            transfer_prefix='TRF',
            inventory_prefix='INV',
            stock_in_prefix='STI',
            conversion_prefix='CNV'
        )
        success(f"Налаштування документів для {company.name}")

    # Фірми
    main_company = companies['ТОВ "Тестова Торгівля"']
    firms_data = [
        {'name': 'ТОВ "Головна фірма"', 'company': main_company, 'vat_type': 'ТОВ'},
        {'name': 'ФОП Відділення', 'company': main_company, 'vat_type': 'ФОП'},
        {'name': 'ТЗОВ Філія', 'company': main_company, 'vat_type': 'ТЗОВ'},
    ]

    firms = {}
    for firm_data in firms_data:
        firm = Firm.objects.create(**firm_data)
        firms[firm_data['name']] = firm
        success(f"Фірма: {firm.name}")

    # Склади
    warehouses_data = [
        {'name': 'Центральний склад', 'company': main_company},
        {'name': 'Роздрібний склад', 'company': main_company},
        {'name': 'Склад готової продукції', 'company': main_company},
        {'name': 'Склад браку', 'company': main_company},
    ]

    warehouses = {}
    for wh_data in warehouses_data:
        warehouse = Warehouse.objects.create(**wh_data)
        warehouses[wh_data['name']] = warehouse
        success(f"Склад: {warehouse.name}")

    # Торгові точки
    main_firm = firms['ТОВ "Головна фірма"']
    trade_points_data = [
        {'name': 'Магазин №1 (Центр)', 'firm': main_firm},
        {'name': 'Магазин №2 (Спальний район)', 'firm': main_firm},
        {'name': 'Інтернет-магазин', 'firm': main_firm},
        {'name': 'Оптовий відділ', 'firm': main_firm},
    ]

    trade_points = {}
    for tp_data in trade_points_data:
        tp = TradePoint.objects.create(**tp_data)
        trade_points[tp_data['name']] = tp
        success(f"Торгова точка: {tp.name}")

    # ========== КРОК 3: КОНТРАГЕНТИ ==========
    step("СТВОРЕННЯ КОНТРАГЕНТІВ")

    # Постачальники
    suppliers_data = [
        {'name': 'ТОВ "Продукти України"', 'tax_id': '11111111'},
        {'name': 'ФОП Козаченко М.М.', 'tax_id': '22222222'},
        {'name': 'ТОВ "М\'ясокомбінат"', 'tax_id': '33333333'},
        {'name': 'Хлібзавод №1', 'tax_id': '44444444'},
    ]

    suppliers = {}
    for supp_data in suppliers_data:
        supplier = Supplier.objects.create(**supp_data)
        suppliers[supp_data['name']] = supplier
        success(f"Постачальник: {supplier.name}")

    # Клієнти
    customers_data = [
        {'name': 'Іванов Іван Іванович', 'type': customer_types['Роздрібний']},
        {'name': 'ТОВ "Великий Оптовик"', 'type': customer_types['Оптовий']},
        {'name': 'Петренко П.П. (VIP)', 'type': customer_types['VIP-клієнт']},
        {'name': 'ТОВ "Мережа магазинів"', 'type': customer_types['Дистриб\'ютор']},
        {'name': 'Сидоренко С.С.', 'type': customer_types['Роздрібний']},
    ]

    customers = {}
    for cust_data in customers_data:
        customer = Customer.objects.create(**cust_data)
        customers[cust_data['name']] = customer
        success(f"Клієнт: {customer.name}")

    # ========== КРОК 4: НОМЕНКЛАТУРА ==========
    step("СТВОРЕННЯ НОМЕНКЛАТУРИ")

    # Групи товарів
    groups_data = [
        {'name': 'М\'ясні продукти', 'parent': None},
        {'name': 'Молочні продукти', 'parent': None},
        {'name': 'Хлібобулочні вироби', 'parent': None},
        {'name': 'Напої', 'parent': None},
        {'name': 'Свинина', 'parent': None},  # Буде дочірня до М'ясних
        {'name': 'Яловичина', 'parent': None},  # Буде дочірня до М'ясних
    ]

    groups = {}
    for group_data in groups_data:
        group = ProductGroup.objects.create(**group_data)
        groups[group_data['name']] = group
        success(f"Група товарів: {group.name}")

    # Встановлюємо батьків для дочірніх груп
    groups['Свинина'].parent = groups['М\'ясні продукти']
    groups['Свинина'].save()
    groups['Яловичина'].parent = groups['М\'ясні продукти']
    groups['Яловичина'].save()
    success("Налаштовано ієрархію груп товарів")

    # Товари
    products_data = [
        {'name': 'Фарш свинячий', 'group': groups['Свинина'], 'unit': units['кг'], 'type': 'product'},
        {'name': 'Окорок свинячий', 'group': groups['Свинина'], 'unit': units['кг'], 'type': 'product'},
        {'name': 'Молоко 2.5%', 'group': groups['Молочні продукти'], 'unit': units['л'], 'type': 'product'},
        {'name': 'Сир твердий', 'group': groups['Молочні продукти'], 'unit': units['кг'], 'type': 'product'},
        {'name': 'Хліб білий', 'group': groups['Хлібобулочні вироби'], 'unit': units['шт'], 'type': 'product'},
        {'name': 'Булочка з маком', 'group': groups['Хлібобулочні вироби'], 'unit': units['шт'], 'type': 'product'},
        {'name': 'Вода мінеральна', 'group': groups['Напої'], 'unit': units['л'], 'type': 'product'},
        {'name': 'Сік апельсиновий', 'group': groups['Напої'], 'unit': units['л'], 'type': 'product'},
        {'name': 'Котлета домашня', 'group': groups['М\'ясні продукти'], 'unit': units['шт'], 'type': 'semi'},
        {'name': 'Сік свіжовичавлений', 'group': groups['Напої'], 'unit': units['л'], 'type': 'semi'},
    ]

    products = {}
    for prod_data in products_data:
        prod_data['firm'] = main_firm
        product = Product.objects.create(**prod_data)
        products[prod_data['name']] = product
        success(f"Товар: {product.name} ({product.get_type_display()})")

    # Конверсії одиниць (приклади)
    conversions_data = [
        {'product': products['Молоко 2.5%'], 'from_unit': units['л'], 'to_unit': units['шт'], 'factor': Decimal('1.0')},
        # 1л = 1 пакет
        {'product': products['Сир твердий'], 'from_unit': units['кг'], 'to_unit': units['упак'],
         'factor': Decimal('0.5')},  # 1кг = 0.5 упак
    ]

    for conv_data in conversions_data:
        ProductUnitConversion.objects.create(**conv_data)
        success(
            f"Конверсія: {conv_data['product'].name} ({conv_data['from_unit'].symbol} → {conv_data['to_unit'].symbol})")

    print(f"\n📊 РЕЗУЛЬТАТ СТВОРЕННЯ СТРУКТУРИ:")
    print(f"   🏢 Компаній: {Company.objects.count()}")
    print(f"   🏭 Фірм: {Firm.objects.count()}")
    print(f"   📦 Складів: {Warehouse.objects.count()}")
    print(f"   🏪 Торгових точок: {TradePoint.objects.count()}")
    print(f"   🤝 Постачальників: {Supplier.objects.count()}")
    print(f"   👥 Клієнтів: {Customer.objects.count()}")
    print(f"   📋 Товарів: {Product.objects.count()}")

    # Зберігаємо ID для наступних кроків
    return {
        'main_company': main_company,
        'main_firm': main_firm,
        'main_warehouse': warehouses['Центральний склад'],
        'retail_warehouse': warehouses['Роздрібний склад'],
        'main_supplier': suppliers['ТОВ "Продукти України"'],
        'retail_customer': customers['Іванов Іван Іванович'],
        'wholesale_customer': customers['ТОВ "Великий Оптовик"'],
        'products': products,
        'units': units,
        'price_types': price_types,
        'trade_points': trade_points,
    }


if __name__ == "__main__":
    create_test_system()