# apply_vat_logic.py - Виправлена версія
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from backend.models import *


def apply_vat_with_firm_logic(item, mode="from_price_without_vat"):
    """
    Застосовує ПДВ з урахуванням типу фірми
    ФОП - без ПДВ
    ТОВ/ТЗОВ/ПАТ - з ПДВ
    """
    from backend.models import AccountingSettings

    # Перевіряємо тип фірми
    firm = item.document.firm

    # ФОП не платить ПДВ
    if firm.vat_type == 'ФОП':
        item.vat_percent = 0
        item.vat_amount = 0
        item.price_without_vat = item.price
        item.price_with_vat = item.price
        item.save(update_fields=["price_with_vat", "price_without_vat", "vat_amount", "vat_percent"])
        print(f"      🚫 ФОП БЕЗ ПДВ: {firm.name}")
        return

    # ТОВ/ТЗОВ/ПАТ платять ПДВ
    if item.vat_percent is not None:
        vat = Decimal(item.vat_percent)
    else:
        try:
            settings = AccountingSettings.objects.get(company=item.document.company)
            vat = settings.default_vat_rate
            item.vat_percent = vat
        except AccountingSettings.DoesNotExist:
            vat = Decimal(20)
            item.vat_percent = vat

    price = Decimal(item.price)

    if mode == "from_price_with_vat":
        item.price_with_vat = price
        item.vat_amount = round(price * vat / (100 + vat), 2)
        item.price_without_vat = round(price - item.vat_amount, 2)
    else:
        item.price_without_vat = price
        item.vat_amount = round(price * vat / 100, 2)
        item.price_with_vat = round(price + item.vat_amount, 2)

    item.save(update_fields=["price_with_vat", "price_without_vat", "vat_amount", "vat_percent"])
    print(f"      💰 {firm.vat_type} З ПДВ: {firm.name} (ПДВ: {item.vat_amount})")


def test_complete_vat_system():
    """Повний тест системи ПДВ"""
    print("🧾 ПОВНИЙ ТЕСТ СИСТЕМИ ПДВ")
    print("=" * 50)

    # Показуємо всі фірми
    print(f"\n📋 СПИСОК ВСІХ ФІРМ:")
    all_firms = Firm.objects.all()
    for firm in all_firms:
        print(f"   {firm.id}. {firm.name} ({firm.vat_type})")

    # Створюємо тестові документи для різних фірм
    company = Company.objects.first()
    warehouse = Warehouse.objects.first()
    supplier = Supplier.objects.first()
    customer = Customer.objects.first()
    product = Product.objects.first()
    unit = Unit.objects.first()

    # Беремо конкретні фірми по назвах
    firms = {}
    try:
        firms['ТОВ'] = Firm.objects.get(name='ТОВ "Головна фірма"')
        print(f"   ✅ Знайдено ТОВ: {firms['ТОВ'].name}")
    except Firm.DoesNotExist:
        print(f"   ❌ ТОВ не знайдено")

    try:
        firms['ФОП'] = Firm.objects.get(name='ФОП Відділення')
        print(f"   ✅ Знайдено ФОП: {firms['ФОП'].name}")
    except Firm.DoesNotExist:
        print(f"   ❌ ФОП не знайдено")

    try:
        firms['ТЗОВ'] = Firm.objects.get(name='ТЗОВ Філія')
        print(f"   ✅ Знайдено ТЗОВ: {firms['ТЗОВ'].name}")
    except Firm.DoesNotExist:
        print(f"   ❌ ТЗОВ не знайдено")

    if not firms:
        print(f"❌ Жодної фірми не знайдено для тестування!")
        return

    results = {}

    for firm_type, firm in firms.items():
        print(f"\n💼 ТЕСТУВАННЯ ФІРМИ: {firm.name} ({firm_type})")

        # Поступлення
        receipt = Document.objects.create(
            doc_type='receipt',
            doc_number=f'TEST-{firm_type}-REC',
            company=company,
            firm=firm,
            warehouse=warehouse,
            supplier=supplier
        )

        item = DocumentItem.objects.create(
            document=receipt,
            product=product,
            quantity=10,
            unit=unit,
            price=100,
            vat_percent=20
        )

        apply_vat_with_firm_logic(item)
        item.refresh_from_db()

        results[firm_type] = {
            'firm_name': firm.name,
            'vat_type': firm.vat_type,
            'price': float(item.price),
            'price_without_vat': float(item.price_without_vat),
            'vat_amount': float(item.vat_amount),
            'price_with_vat': float(item.price_with_vat),
        }

        print(f"   📦 ПОСТУПЛЕННЯ:")
        print(f"      Ціна: {item.price}")
        print(f"      Без ПДВ: {item.price_without_vat}")
        print(f"      ПДВ: {item.vat_amount}")
        print(f"      З ПДВ: {item.price_with_vat}")

        # Продаж
        sale = Document.objects.create(
            doc_type='sale',
            doc_number=f'TEST-{firm_type}-SAL',
            company=company,
            firm=firm,
            warehouse=warehouse,
            customer=customer
        )

        sale_item = DocumentItem.objects.create(
            document=sale,
            product=product,
            quantity=5,
            unit=unit,
            price=150,
            vat_percent=20
        )

        apply_vat_with_firm_logic(sale_item)
        sale_item.refresh_from_db()

        print(f"   💰 ПРОДАЖ:")
        print(f"      Ціна: {sale_item.price}")
        print(f"      ПДВ: {sale_item.vat_amount}")

        # Очистка
        receipt.delete()
        sale.delete()

    # Підсумок
    print(f"\n📊 ПІДСУМОК ПДВ ПО ФІРМАХ:")
    print(f"   {'Тип':<6} {'Назва':<25} {'ПДВ (поступ.)':<12} {'ПДВ (продаж)'}")
    print(f"   {'-' * 6} {'-' * 25} {'-' * 12} {'-' * 12}")

    for firm_type, data in results.items():
        print(f"   {firm_type:<6} {data['firm_name']:<25} {data['vat_amount']:<12} грн")

    # Висновки
    print(f"\n🔍 ВИСНОВКИ:")
    fop_vat = results.get('ФОП', {}).get('vat_amount', 0)
    tov_vat = results.get('ТОВ', {}).get('vat_amount', 0)

    if fop_vat == 0:
        print(f"   ✅ ФОП правильно НЕ платить ПДВ")
    else:
        print(f"   ❌ ФОП неправильно платить ПДВ: {fop_vat}")

    if tov_vat > 0:
        print(f"   ✅ ТОВ правильно платить ПДВ: {tov_vat} грн")
    else:
        print(f"   ❌ ТОВ неправильно НЕ платить ПДВ")

    print(f"\n✅ ТЕСТ СИСТЕМИ ПДВ ЗАВЕРШЕНО!")


if __name__ == "__main__":
    test_complete_vat_system()