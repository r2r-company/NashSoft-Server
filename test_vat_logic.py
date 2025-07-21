# test_vat_logic.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from backend.models import *
from backend.services.document_services import *


def test_vat_logic():
    print("🧾 ТЕСТУВАННЯ ЛОГІКИ ПДВ")
    print("=" * 40)

    # Отримуємо фірми
    tov_firm = Firm.objects.get(name='ТОВ "Головна фірма"')
    fop_firm = Firm.objects.get(name='ФОП Відділення')

    company = Company.objects.first()
    warehouse = Warehouse.objects.first()
    supplier = Supplier.objects.first()
    product = Product.objects.first()
    unit = Unit.objects.first()

    print(f"📋 ФІРМИ ДЛЯ ТЕСТУВАННЯ:")
    print(f"   {tov_firm.name} ({tov_firm.vat_type})")
    print(f"   {fop_firm.name} ({fop_firm.vat_type})")

    # Тест 1: Поступлення для ТОВ (З ПДВ)
    print(f"\n💰 ТЕСТ 1: ПОСТУПЛЕННЯ ДЛЯ ТОВ")

    receipt_tov = Document.objects.create(
        doc_type='receipt',
        doc_number='TEST-TOV-001',
        company=company,
        firm=tov_firm,
        warehouse=warehouse,
        supplier=supplier
    )

    item_tov = DocumentItem.objects.create(
        document=receipt_tov,
        product=product,
        quantity=10,
        unit=unit,
        price=120,  # Ціна з ПДВ
        vat_percent=20
    )

    # Застосовуємо ПДВ логіку
    from backend.services.document_services import apply_vat
    apply_vat(item_tov)
    item_tov.refresh_from_db()

    print(f"   ТОВ - Ціна: {item_tov.price}")
    print(f"   ТОВ - Без ПДВ: {item_tov.price_without_vat}")
    print(f"   ТОВ - ПДВ: {item_tov.vat_amount}")
    print(f"   ТОВ - З ПДВ: {item_tov.price_with_vat}")

    # Тест 2: Поступлення для ФОП (БЕЗ ПДВ)
    print(f"\n💰 ТЕСТ 2: ПОСТУПЛЕННЯ ДЛЯ ФОП")

    receipt_fop = Document.objects.create(
        doc_type='receipt',
        doc_number='TEST-FOP-001',
        company=company,
        firm=fop_firm,
        warehouse=warehouse,
        supplier=supplier
    )

    item_fop = DocumentItem.objects.create(
        document=receipt_fop,
        product=product,
        quantity=10,
        unit=unit,
        price=120,  # Ціна без ПДВ
        vat_percent=20  # Буде перезаписано на 0
    )

    apply_vat(item_fop)
    item_fop.refresh_from_db()

    print(f"   ФОП - Ціна: {item_fop.price}")
    print(f"   ФОП - Без ПДВ: {item_fop.price_without_vat}")
    print(f"   ФОП - ПДВ: {item_fop.vat_amount}")
    print(f"   ФОП - З ПДВ: {item_fop.price_with_vat}")

    # Порівняння
    print(f"\n📊 ПОРІВНЯННЯ:")
    print(f"   ТОВ сплачує ПДВ: {item_tov.vat_amount} грн")
    print(f"   ФОП сплачує ПДВ: {item_fop.vat_amount} грн")
    print(f"   Різниця в ПДВ: {item_tov.vat_amount - item_fop.vat_amount} грн")

    # Очищення тестових даних
    receipt_tov.delete()
    receipt_fop.delete()

    print(f"\n✅ ТЕСТ ЗАВЕРШЕНО!")


if __name__ == "__main__":
    test_vat_logic()