# report_vat_stock.py
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from backend.models import *
from backend.operations.stock import FIFOStockManager


def show_stock_and_vat():
    print("📊 ЗВІТ ПО ЗАЛИШКАХ І ПДВ")
    print("=" * 40)

    company = Company.objects.first()
    warehouse = Warehouse.objects.get(name='Центральний склад')

    firms = {
        'ФОП': Firm.objects.get(name='ФОП Тестовий'),
        'ТОВ': Firm.objects.get(name='ТОВ Тестовий')
    }

    products = Product.objects.filter(name__in=[
        'Фарш', 'Фарш в пакетику', 'Віскі', 'Віскі порція'
    ])

    for firm_type, firm in firms.items():
        print(f"\n🏢 Фірма: {firm.name} ({firm_type})")
        for product in products.filter(firm=firm):
            stock = FIFOStockManager.get_available_stock(product, warehouse, firm)
            if stock > 0:
                value = FIFOStockManager.get_stock_value(product, warehouse, firm)
                avg_cost = value / stock if stock > 0 else 0
                print(f"   📦 {product.name}: {stock} {product.unit.symbol}, вартість {value:.2f}, середня {avg_cost:.2f}")

    print("\n📑 Перевір ПДВ в таблиці DocumentItem (price, vat_amount, price_with_vat)")
    print("👉 Або вручну через адмінку або SQL")

if __name__ == "__main__":
    show_stock_and_vat()
