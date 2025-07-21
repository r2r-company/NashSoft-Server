# run_full_vat_simulation.py
import os
import django
from time import sleep

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from backend.models import *
from backend.services.document_services import *


def wait(msg="↩️  Натисни Enter для продовження..."):
    input(f"\n{msg}")


def print_step(title):
    print(f"\n🔹 {title}")
    print("   " + "-" * len(title))


def main():
    print("🚀 СИМУЛЯЦІЯ ФАСУВАННЯ ТА ПДВ")
    print("=" * 40)

    company = Company.objects.first()
    fop_firm = Firm.objects.get(name="ФОП Тестовий")
    tov_firm = Firm.objects.get(name="ТОВ Тестовий")
    warehouse = Warehouse.objects.get(name="Центральний склад")
    supplier = Supplier.objects.first()
    customer = Customer.objects.first()
    unit_kg = Unit.objects.get(symbol='кг')
    unit_sht = Unit.objects.get(symbol='шт')
    unit_g = Unit.objects.get_or_create(name='грам', symbol='г')[0]

    # Товари
    фарш, _ = Product.objects.get_or_create(name="Фарш", firm=fop_firm, defaults={'unit': unit_kg, 'type': 'product'})
    фарш_пакетик, _ = Product.objects.get_or_create(name="Фарш в пакетику", firm=fop_firm, defaults={'unit': unit_sht, 'type': 'semi'})
    віскі, _ = Product.objects.get_or_create(name="Віскі", firm=tov_firm, defaults={'unit': unit_sht, 'type': 'product'})
    віскі_порція, _ = Product.objects.get_or_create(name="Віскі порція", firm=tov_firm, defaults={'unit': unit_g, 'type': 'semi'})

    print_step("КРОК 1: Закупівля фаршу ФОП")
    receipt1 = Document.objects.create(
        doc_type='receipt',
        doc_number='FOP-REC-001',
        company=company,
        firm=fop_firm,
        warehouse=warehouse,
        supplier=supplier
    )
    DocumentItem.objects.create(
        document=receipt1,
        product=фарш,
        quantity=1,
        unit=unit_kg,
        price=100,
        vat_percent=20
    )
    ReceiptService(receipt1).post()
    print("✅ Закуплено 1 кг фаршу по 100 грн для ФОП")

    wait("↩️ Тисни Enter щоб продовжити до фасування фаршу...")

    print_step("КРОК 2: Фасування фаршу")
    cnv1 = Document.objects.create(
        doc_type='conversion',
        doc_number='FOP-CNV-001',
        company=company,
        firm=fop_firm,
        warehouse=warehouse
    )
    DocumentItem.objects.create(
        document=cnv1,
        product=фарш,
        quantity=1,
        unit=unit_kg,
        price=100,
        role='source',
        vat_percent=20
    )
    DocumentItem.objects.create(
        document=cnv1,
        product=фарш_пакетик,
        quantity=4,
        unit=unit_sht,
        price=0,
        role='target',
        vat_percent=20
    )
    ConversionDocumentService(cnv1).post()
    print("✅ 1 кг фаршу → 4 пакетики по 250г")

    wait("↩️ Тисни Enter щоб продовжити до закупівлі віскі...")

    print_step("КРОК 3: Закупівля віскі для ТОВ")
    receipt2 = Document.objects.create(
        doc_type='receipt',
        doc_number='TOV-REC-001',
        company=company,
        firm=tov_firm,
        warehouse=warehouse,
        supplier=supplier
    )
    DocumentItem.objects.create(
        document=receipt2,
        product=віскі,
        quantity=1,
        unit=unit_sht,
        price=500,
        vat_percent=20
    )
    ReceiptService(receipt2).post()
    print("✅ Закуплено 1 пляшка віскі по 500 грн для ТОВ")

    wait("↩️ Тисни Enter щоб продовжити до фасування віскі...")

    print_step("КРОК 4: Фасування віскі")
    cnv2 = Document.objects.create(
        doc_type='conversion',
        doc_number='TOV-CNV-001',
        company=company,
        firm=tov_firm,
        warehouse=warehouse
    )
    DocumentItem.objects.create(
        document=cnv2,
        product=віскі,
        quantity=1,
        unit=unit_sht,
        price=500,
        role='source',
        vat_percent=20
    )
    DocumentItem.objects.create(
        document=cnv2,
        product=віскі_порція,
        quantity=20,
        unit=unit_g,
        price=0,
        role='target',
        vat_percent=20
    )
    ConversionDocumentService(cnv2).post()
    print("✅ 1 пляшка віскі → 20 порцій по 50г")

    wait("↩️ Тисни Enter щоб створити ціни на фасовані товари...")

    print_step("КРОК 5: Ціноутворення")
    price_type, _ = PriceType.objects.get_or_create(name="Роздрібна", is_default=True)
    price_doc = PriceSettingDocument.objects.create(
        doc_number='PRICE-001',
        company=company,
        firm=fop_firm,
        valid_from='2025-01-01',
        status='approved'
    )
    PriceSettingItem.objects.create(
        price_setting_document=price_doc,
        product=фарш_пакетик,
        price_type=price_type,
        price=50,
        unit=unit_sht,
        vat_percent=0,
        firm=fop_firm
    )
    price_doc2 = PriceSettingDocument.objects.create(
        doc_number='PRICE-002',
        company=company,
        firm=tov_firm,
        valid_from='2025-01-01',
        status='approved'
    )
    PriceSettingItem.objects.create(
        price_setting_document=price_doc2,
        product=віскі_порція,
        price_type=price_type,
        price=100,
        unit=unit_g,
        vat_percent=20,
        firm=tov_firm
    )
    print("✅ Створено ціни: фарш 50 грн, віскі 100 грн")

    wait("↩️ Тисни Enter щоб перейти до реалізації фаршу...")

    print_step("КРОК 6: Продаж фаршу в пакетику")
    sale1 = Document.objects.create(
        doc_type='sale',
        doc_number='FOP-SAL-001',
        company=company,
        firm=fop_firm,
        warehouse=warehouse,
        customer=customer
    )
    DocumentItem.objects.create(
        document=sale1,
        product=фарш_пакетик,
        quantity=2,
        unit=unit_sht,
        price=50,
        vat_percent=0
    )
    SaleService(sale1).post()
    print("✅ Продано 2 пакетики фаршу по 50 грн (ФОП, без ПДВ)")

    wait("↩️ Тисни Enter щоб перейти до реалізації віскі...")

    print_step("КРОК 7: Продаж порцій віскі")
    sale2 = Document.objects.create(
        doc_type='sale',
        doc_number='TOV-SAL-001',
        company=company,
        firm=tov_firm,
        warehouse=warehouse,
        customer=customer
    )
    DocumentItem.objects.create(
        document=sale2,
        product=віскі_порція,
        quantity=3,
        unit=unit_g,
        price=100,
        vat_percent=20
    )
    SaleService(sale2).post()
    print("✅ Продано 3 порції віскі по 100 грн (ТОВ, з ПДВ)")

    print("\n🎉 СИМУЛЯЦІЯ ЗАВЕРШЕНА")
    print("👉 Відкрий `report_vat_stock.py` для перегляду залишків і ПДВ")

if __name__ == "__main__":
    main()
