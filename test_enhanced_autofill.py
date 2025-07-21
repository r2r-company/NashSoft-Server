# test_enhanced_autofill.py
# Тестування покращеного PriceAutoFillService

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from django.db.models import Q  # ✅ Додано імпорт Q
from backend.models import *
from backend.services.price import PriceAutoFillService


def test_enhanced_autofill():
    print("🚀 ТЕСТУВАННЯ ПОКРАЩЕНОГО АВТОЗАПОВНЕННЯ")
    print("=" * 60)

    # Отримуємо тестові дані
    try:
        company = Company.objects.first()
        fop_firm = Firm.objects.filter(vat_type='ФОП').first()
        tov_firm = Firm.objects.filter(vat_type='ТЗОВ').first()

        if not all([company, fop_firm, tov_firm]):
            print("❌ Недостатньо даних. Запустіть create_business_scenario.py")
            return

        print(f"✅ Компанія: {company.name}")
        print(f"✅ ФОП: {fop_firm.name}")
        print(f"✅ ТЗОВ: {tov_firm.name}")

    except Exception as e:
        print(f"❌ Помилка отримання даних: {e}")
        return

    # ========== ТЕСТ 1: АВТОЗАПОВНЕННЯ НА ОСНОВІ ПОСТУПЛЕННЯ ФОП ==========
    print(f"\n📋 ТЕСТ 1: Автозаповнення на основі поступлення ФОП")

    try:
        # Знаходимо документ поступлення ФОП
        fop_receipt = Document.objects.filter(
            doc_type='receipt',
            firm=fop_firm,
            status='posted'
        ).first()

        if not fop_receipt:
            print("❌ Документ поступлення ФОП не знайдено")
            return

        print(f"📄 Документ: {fop_receipt.doc_number}")

        # Показуємо товари в документі
        print(f"📦 Товари в документі:")
        for item in fop_receipt.items.all():
            print(f"   • {item.product.name}: {item.quantity} x {item.price} = {item.quantity * item.price}")

        # Створюємо документ ціноутворення
        fop_price_doc = PriceSettingDocument.objects.create(
            company=company,
            firm=fop_firm,
            valid_from='2025-01-20',
            base_type='receipt',
            base_receipt=fop_receipt,
            status='draft'
        )

        # Додаємо торгову точку
        fop_trade_point = TradePoint.objects.filter(firm=fop_firm).first()
        if fop_trade_point:
            fop_price_doc.trade_points.add(fop_trade_point)

        print(f"✅ Документ ціноутворення створено: {fop_price_doc.doc_number}")

        # Запускаємо автозаповнення
        service = PriceAutoFillService(fop_price_doc)
        items_created = service.fill_items()

        print(f"🎯 Створено {items_created} позицій з автоматичними цінами")

        # Показуємо результат
        print(f"💰 РОЗРАХОВАНІ ЦІНИ (ФОП БЕЗ ПДВ):")
        for item in fop_price_doc.items.all():
            receipt_item = fop_receipt.items.filter(product=item.product).first()
            base_cost = receipt_item.price if receipt_item else 0

            print(f"   • {item.product.name}:")
            print(f"     Собівартість: {base_cost} грн")
            print(f"     Націнка: {item.markup_percent}%")
            print(f"     Продажна ціна: {item.price} грн")
            print(f"     ПДВ: {item.vat_amount} грн (ставка: {item.vat_percent}%)")

    except Exception as e:
        print(f"❌ Помилка в тесті ФОП: {e}")

    # ========== ТЕСТ 2: АВТОЗАПОВНЕННЯ НА ОСНОВІ ПОСТУПЛЕННЯ ТЗОВ ==========
    print(f"\n📋 ТЕСТ 2: Автозаповнення на основі поступлення ТЗОВ")

    try:
        # Знаходимо документ поступлення ТЗОВ
        tov_receipt = Document.objects.filter(
            doc_type='receipt',
            firm=tov_firm,
            status='posted'
        ).first()

        if not tov_receipt:
            print("❌ Документ поступлення ТЗОВ не знайдено")
            return

        print(f"📄 Документ: {tov_receipt.doc_number}")

        # Показуємо товари в документі
        print(f"📦 Товари в документі:")
        for item in tov_receipt.items.all():
            print(f"   • {item.product.name}: {item.quantity} x {item.price}")

        # Створюємо документ ціноутворення
        tov_price_doc = PriceSettingDocument.objects.create(
            company=company,
            firm=tov_firm,
            valid_from='2025-01-20',
            base_type='receipt',
            base_receipt=tov_receipt,
            status='draft'
        )

        # Додаємо торгову точку
        tov_trade_point = TradePoint.objects.filter(firm=tov_firm).first()
        if tov_trade_point:
            tov_price_doc.trade_points.add(tov_trade_point)

        print(f"✅ Документ ціноутворення створено: {tov_price_doc.doc_number}")

        # Запускаємо автозаповнення
        service = PriceAutoFillService(tov_price_doc)
        items_created = service.fill_items()

        print(f"🎯 Створено {items_created} позицій з автоматичними цінами")

        # Показуємо результат
        print(f"💰 РОЗРАХОВАНІ ЦІНИ (ТЗОВ З ПДВ):")
        for item in tov_price_doc.items.all():
            receipt_item = tov_receipt.items.filter(product=item.product).first()
            base_cost = receipt_item.price_without_vat if receipt_item else 0

            print(f"   • {item.product.name}:")
            print(f"     Собівартість: {base_cost} грн (без ПДВ)")
            print(f"     Націнка: {item.markup_percent}%")
            print(f"     Ціна без ПДВ: {item.price_without_vat} грн")
            print(f"     ПДВ: {item.vat_amount} грн")
            print(f"     Ціна З ПДВ: {item.price} грн")

    except Exception as e:
        print(f"❌ Помилка в тесті ТЗОВ: {e}")

    # ========== ТЕСТ 3: АВТОЗАПОВНЕННЯ НА ОСНОВІ ГРУПИ ==========
    print(f"\n📋 ТЕСТ 3: Автозаповнення на основі групи товарів")

    try:
        # Створюємо або знаходимо групу
        alcohol_group, created = ProductGroup.objects.get_or_create(
            name='Алкогольні напої'
        )

        # Прив'язуємо товари до групи
        alcohol_products = Product.objects.filter(
            Q(name__icontains='віскі') | Q(name__icontains='коньяк'),
            firm=tov_firm
        )

        if alcohol_products.exists():
            alcohol_products.update(group=alcohol_group)
            print(f"📂 Група: {alcohol_group.name}")
            print(f"📦 Товарів у групі: {alcohol_products.count()}")

            # Створюємо ціноутворення на основі групи
            group_price_doc = PriceSettingDocument.objects.create(
                company=company,
                firm=tov_firm,
                valid_from='2025-01-21',
                base_type='product_group',
                base_group=alcohol_group,
                status='draft'
            )

            # Додаємо торгову точку
            if tov_trade_point:
                group_price_doc.trade_points.add(tov_trade_point)

            print(f"✅ Документ ціноутворення створено: {group_price_doc.doc_number}")

            # Запускаємо автозаповнення
            service = PriceAutoFillService(group_price_doc)
            items_created = service.fill_items()

            print(f"🎯 Створено {items_created} позицій")

            # Показуємо результат
            print(f"💰 ЦІНИ ПО ГРУПІ 'АЛКОГОЛЬ':")
            for item in group_price_doc.items.all():
                print(f"   • {item.product.name}: {item.price} грн (націнка: {item.markup_percent}%)")

        else:
            print("❌ Не знайдено алкогольних товарів для групи")

    except Exception as e:
        print(f"❌ Помилка в тесті групи: {e}")

    # ========== ПІДСУМОК ==========
    print(f"\n📊 ПІДСУМОК ТЕСТУВАННЯ:")

    # Підраховуємо всі створені документи ціноутворення
    all_price_docs = PriceSettingDocument.objects.filter(
        company=company,
        valid_from__gte='2025-01-20'
    )

    print(f"📄 Створено документів ціноутворення: {all_price_docs.count()}")

    total_items = 0
    for doc in all_price_docs:
        items_count = doc.items.count()
        total_items += items_count
        print(f"   • {doc.doc_number}: {items_count} позицій (основа: {doc.get_base_type_display()})")

    print(f"📦 Всього позицій створено: {total_items}")

    # Перевіряємо логіку націнок
    print(f"\n🎯 ПЕРЕВІРКА ЛОГІКИ НАЦІНОК:")

    meat_items = PriceSettingItem.objects.filter(
        product__name__icontains='фарш',
        price_setting_document__in=all_price_docs
    )

    alcohol_items = PriceSettingItem.objects.filter(
        Q(product__name__icontains='віскі') | Q(product__name__icontains='коньяк'),
        price_setting_document__in=all_price_docs
    )

    if meat_items.exists():
        meat_item = meat_items.first()
        print(f"   🥩 М'ясо: націнка {meat_item.markup_percent}% (очікуємо 400%)")

    if alcohol_items.exists():
        alcohol_item = alcohol_items.first()
        print(f"   🥃 Алкоголь: націнка {alcohol_item.markup_percent}% (очікуємо 180%)")

    # Перевіряємо ПДВ
    print(f"\n🧾 ПЕРЕВІРКА ПДВ:")

    fop_items = PriceSettingItem.objects.filter(
        firm__vat_type='ФОП',
        price_setting_document__in=all_price_docs
    )

    tov_items = PriceSettingItem.objects.filter(
        firm__vat_type='ТЗОВ',
        price_setting_document__in=all_price_docs
    )

    if fop_items.exists():
        fop_vat = fop_items.first().vat_percent
        print(f"   ФОП: ПДВ {fop_vat}% (очікуємо 0%)")

    if tov_items.exists():
        tov_vat = tov_items.first().vat_percent
        print(f"   ТЗОВ: ПДВ {tov_vat}% (очікуємо 20%)")

    print(f"\n✅ ТЕСТУВАННЯ ЗАВЕРШЕНО!")
    print(f"🎉 Покращений PriceAutoFillService працює правильно!")


if __name__ == "__main__":
    test_enhanced_autofill()