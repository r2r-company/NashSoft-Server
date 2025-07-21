# test_trade_points_pricing.py
# Тестування ціноутворення по різних торгових точках

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from django.db.models import Q
from backend.models import *  # ✅ Імпорт ПІСЛЯ django.setup()
from backend.services.price import PriceAutoFillService, get_price_from_setting


def test_trade_points_pricing():
    print("🏪 ТЕСТУВАННЯ ЦІНОУТВОРЕННЯ ПО ТОРГОВИМ ТОЧКАМ")
    print("=" * 70)

    # Отримуємо дані
    try:
        company = Company.objects.first()
        tov_firm = Firm.objects.filter(vat_type='ТЗОВ').first()

        if not all([company, tov_firm]):
            print("❌ Недостатньо даних")
            return

        print(f"✅ Фірма: {tov_firm.name}")

    except Exception as e:
        print(f"❌ Помилка: {e}")
        return

    # ========== СТВОРЮЄМО РІЗНІ ТОРГОВІ ТОЧКИ ==========
    print(f"\n🏪 СТВОРЕННЯ ТОРГОВИХ ТОЧОК:")

    # Очищуємо старі точки для чистого тесту
    TradePoint.objects.filter(firm=tov_firm).delete()

    # Створюємо різні типи торгових точок
    trade_points = []

    bar_elite = TradePoint.objects.create(
        name='Елітний бар (центр)',
        firm=tov_firm
    )
    trade_points.append(bar_elite)
    print(f"   🍸 {bar_elite.name}")

    bar_district = TradePoint.objects.create(
        name='Районний бар',
        firm=tov_firm
    )
    trade_points.append(bar_district)
    print(f"   🍺 {bar_district.name}")

    shop_wholesale = TradePoint.objects.create(
        name='Оптовий склад',
        firm=tov_firm
    )
    trade_points.append(shop_wholesale)
    print(f"   📦 {shop_wholesale.name}")

    shop_retail = TradePoint.objects.create(
        name='Роздрібний магазин',
        firm=tov_firm
    )
    trade_points.append(shop_retail)
    print(f"   🛒 {shop_retail.name}")

    print(f"✅ Створено {len(trade_points)} торгових точок")

    # ========== ЗНАХОДИМО ТОВАР ДЛЯ ТЕСТУВАННЯ ==========
    print(f"\n🥃 ВИБІР ТОВАРУ:")

    whiskey_product = Product.objects.filter(
        name__icontains='віскі',
        firm=tov_firm
    ).first()

    if not whiskey_product:
        print("❌ Товар віскі не знайдено")
        return

    print(f"✅ Товар: {whiskey_product.name}")

    # ========== СТВОРЮЄМО ЦІНОУТВОРЕННЯ З РІЗНИМИ ЦІНАМИ ==========
    print(f"\n💰 СТВОРЕННЯ ПРАЙСУ З РІЗНИМИ ЦІНАМИ:")

    # Документ ціноутворення
    price_doc = PriceSettingDocument.objects.create(
        company=company,
        firm=tov_firm,
        valid_from='2025-01-22',
        status='draft',
        comment='Тестування різних цін по торговим точкам'
    )

    # Додаємо всі торгові точки до документа
    price_doc.trade_points.set(trade_points)

    print(f"✅ Документ ціноутворення створено: {price_doc.doc_number}")

    # Отримуємо тип ціни
    price_type = PriceType.objects.filter(is_default=True).first()
    if not price_type:
        price_type = PriceType.objects.create(name='Роздрібна', is_default=True)

    # ========== СТВОРЮЄМО РІЗНІ ЦІНИ ВРУЧНУ ==========
    print(f"\n📊 ВСТАНОВЛЕННЯ ЦІН ПО ТОЧКАМ:")

    # Очищуємо старі позиції
    price_doc.items.all().delete()

    # Різні ціни для різних торгових точок
    pricing_strategy = {
        bar_elite: {
            'price': Decimal('150.00'),  # Преміум ціна в елітному барі
            'comment': 'Елітний бар - преміум ціна'
        },
        bar_district: {
            'price': Decimal('100.00'),  # Стандартна ціна в районному барі
            'comment': 'Районний бар - стандартна ціна'
        },
        shop_wholesale: {
            'price': Decimal('70.00'),  # Оптова ціна
            'comment': 'Оптовий склад - знижена ціна'
        },
        shop_retail: {
            'price': Decimal('120.00'),  # Роздрібна ціна
            'comment': 'Роздрібний магазин - підвищена ціна'
        }
    }

    # Створюємо позиції з різними цінами
    for trade_point, price_info in pricing_strategy.items():
        # Розраховуємо ПДВ для ТЗОВ (20%)
        price_with_vat = price_info['price']
        price_without_vat = price_with_vat / Decimal('1.2')  # Діли на 1.2 для 20% ПДВ
        vat_amount = price_with_vat - price_without_vat

        item = PriceSettingItem.objects.create(
            price_setting_document=price_doc,
            product=whiskey_product,
            price_type=price_type,
            trade_point=trade_point,
            firm=tov_firm,
            price=price_with_vat,
            price_without_vat=price_without_vat,
            vat_amount=vat_amount,
            vat_percent=Decimal('20'),
            vat_included=True
        )

        print(f"   🏪 {trade_point.name}:")
        print(f"      💰 Ціна З ПДВ: {price_with_vat} грн")
        print(f"      💵 Ціна БЕЗ ПДВ: {price_without_vat:.2f} грн")
        print(f"      🧾 ПДВ: {vat_amount:.2f} грн")
        print(f"      📝 {price_info['comment']}")

    # Затверджуємо прайс
    price_doc.status = 'approved'
    price_doc.save()

    print(f"✅ Прайс затверджено з {price_doc.items.count()} позиціями")

    # ========== ТЕСТУЄМО ОТРИМАННЯ ЦІН ==========
    print(f"\n🔍 ТЕСТУВАННЯ ОТРИМАННЯ ЦІН:")

    for trade_point in trade_points:
        price = get_price_from_setting(
            product=whiskey_product,
            firm=tov_firm,
            trade_point=trade_point,
            price_type=price_type
        )

        expected_price = pricing_strategy[trade_point]['price']
        status = "✅" if price == expected_price else "❌"

        print(f"   {status} {trade_point.name}: {price} грн (очікуємо: {expected_price} грн)")

    # ========== ТЕСТУЄМО БЕЗ ТОРГОВОЇ ТОЧКИ ==========
    print(f"\n🔍 ТЕСТ БЕЗ ВКАЗАННЯ ТОРГОВОЇ ТОЧКИ:")

    price_without_tp = get_price_from_setting(
        product=whiskey_product,
        firm=tov_firm,
        trade_point=None,  # Не вказуємо торгову точку
        price_type=price_type
    )

    print(f"   🤷 Ціна без торгової точки: {price_without_tp}")
    if price_without_tp is None:
        print("   ℹ️  Правильно - без торгової точки ціна не знайдена")

    # ========== ТЕСТУЄМО АВТОЗАПОВНЕННЯ З ТОРГОВИМИ ТОЧКАМИ ==========
    print(f"\n🤖 ТЕСТ АВТОЗАПОВНЕННЯ З ТОРГОВИМИ ТОЧКАМИ:")

    # Знаходимо документ поступлення
    receipt_doc = Document.objects.filter(
        doc_type='receipt',
        firm=tov_firm,
        status='posted'
    ).first()

    if receipt_doc:
        # Створюємо новий документ ціноутворення з автозаповненням
        auto_price_doc = PriceSettingDocument.objects.create(
            company=company,
            firm=tov_firm,
            valid_from='2025-01-23',
            base_type='receipt',
            base_receipt=receipt_doc,
            status='draft'
        )

        # Додаємо тільки 2 торгові точки для тесту
        auto_price_doc.trade_points.set([bar_elite, shop_retail])

        print(f"✅ Документ автозаповнення створено: {auto_price_doc.doc_number}")
        print(f"🏪 Торгових точок: {auto_price_doc.trade_points.count()}")

        # Запускаємо автозаповнення
        service = PriceAutoFillService(auto_price_doc)
        items_created = service.fill_items()

        print(f"🎯 Автоматично створено: {items_created} позицій")

        # Показуємо результат
        print(f"📊 РЕЗУЛЬТАТ АВТОЗАПОВНЕННЯ:")
        for item in auto_price_doc.items.all():
            print(f"   🏪 {item.trade_point.name}:")
            print(f"      📦 {item.product.name}")
            print(f"      💰 {item.price} грн")

    # ========== ПІДСУМОК ==========
    print(f"\n📊 ПІДСУМОК ТЕСТУВАННЯ ТОРГОВИХ ТОЧОК:")

    # Підраховуємо позиції по торговим точкам
    total_items = PriceSettingItem.objects.filter(
        price_setting_document__firm=tov_firm,
        price_setting_document__valid_from__gte='2025-01-22'
    )

    print(f"📦 Всього позицій створено: {total_items.count()}")

    by_trade_point = {}
    for item in total_items:
        tp_name = item.trade_point.name
        if tp_name not in by_trade_point:
            by_trade_point[tp_name] = []
        by_trade_point[tp_name].append(item)

    print(f"🏪 Розподіл по торговим точкам:")
    for tp_name, items in by_trade_point.items():
        prices = [float(item.price) for item in items]
        avg_price = sum(prices) / len(prices) if prices else 0
        print(f"   • {tp_name}: {len(items)} позицій, середня ціна: {avg_price:.2f} грн")

    # Перевіряємо унікальність цін
    print(f"\n🎯 ПЕРЕВІРКА РІЗНИХ ЦІН:")
    unique_prices = set(float(item.price) for item in total_items if item.product == whiskey_product)
    print(f"   Унікальних цін для віскі: {len(unique_prices)}")
    print(f"   Ціни: {sorted(unique_prices)} грн")

    if len(unique_prices) > 1:
        print(f"   ✅ Різні ціни по торговим точкам працюють!")
    else:
        print(f"   ⚠️  Ціни однакові - можливо помилка")

    print(f"\n✅ ТЕСТУВАННЯ ТОРГОВИХ ТОЧОК ЗАВЕРШЕНО!")


if __name__ == "__main__":
    test_trade_points_pricing()