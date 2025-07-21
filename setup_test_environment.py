# setup_test_environment.py
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from backend.models import *

def main():
    print("🛠️ СТВОРЕННЯ СТРУКТУРИ ДЛЯ ТЕСТУ")
    print("=" * 40)

    # Юніти
    unit_kg, _ = Unit.objects.get_or_create(name="кілограм", symbol="кг")
    unit_sht, _ = Unit.objects.get_or_create(name="штука", symbol="шт")
    unit_g, _ = Unit.objects.get_or_create(name="грам", symbol="г")

    print("✅ Створено одиниці виміру")

    # Компанія
    company, _ = Company.objects.get_or_create(name="ТОВ 'Тестова Компанія'", tax_id="12345678")
    print(f"✅ Компанія: {company.name}")

    # Налаштування обліку
    AccountingSettings.objects.get_or_create(
        company=company,
        defaults=dict(
            stock_account='281',
            supplier_account='631',
            vat_input_account='644',
            client_account='361',
            revenue_account='701',
            vat_output_account='641',
            default_vat_rate=Decimal('20.00'),
            default_price_type=None
        )
    )

    # Фірми
    fop, _ = Firm.objects.get_or_create(name="ФОП Тестовий", company=company, vat_type='ФОП')
    tov, _ = Firm.objects.get_or_create(name="ТОВ Тестовий", company=company, vat_type='ТОВ')

    print(f"✅ Фірми: {fop.name}, {tov.name}")

    # Склад
    warehouse, _ = Warehouse.objects.get_or_create(name="Центральний склад", company=company)
    print(f"✅ Склад: {warehouse.name}")

    # Постачальник
    supplier, _ = Supplier.objects.get_or_create(name="ТОВ Постачальник", tax_id="11111111")
    print(f"✅ Постачальник: {supplier.name}")

    # Клієнт
    customer_type, _ = CustomerType.objects.get_or_create(name="Роздрібний")
    customer, _ = Customer.objects.get_or_create(name="Клієнт Тестовий", defaults={"type": customer_type})
    print(f"✅ Клієнт: {customer.name}")

    print("\n🎉 СТРУКТУРА ГОТОВА ДО СИМУЛЯЦІЇ")

if __name__ == "__main__":
    main()
