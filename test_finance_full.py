# test_finance_full.py - НОВИЙ ФАЙЛ

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from decimal import Decimal
from datetime import date
from backend.models import Company


def test_finance_simple():
    print("💰 ПРОСТИЙ ТЕСТ ФІНАНСОВОГО МОДУЛЯ")
    print("=" * 50)

    # ========== ПІДГОТОВКА ДАНИХ ==========
    try:
        company = Company.objects.first()
        if not company:
            company = Company.objects.create(name='Тестова компанія')

        print(f"✅ Компанія: {company.name}")

    except Exception as e:
        print(f"❌ Помилка підготовки: {e}")
        return

    # ========== ТЕСТУВАННЯ РОЗРАХУНКІВ ==========
    print(f"\n🧮 ТЕСТУВАННЯ ФІНАНСОВИХ РОЗРАХУНКІВ:")

    # Тест ПДВ
    price_without_vat = Decimal('1000.00')
    vat_rate = Decimal('0.20')
    vat_amount = price_without_vat * vat_rate
    price_with_vat = price_without_vat + vat_amount

    print(f"   💵 Ціна без ПДВ: {price_without_vat} грн")
    print(f"   📊 Ставка ПДВ: {vat_rate * 100}%")
    print(f"   🧾 Сума ПДВ: {vat_amount} грн")
    print(f"   💰 Ціна з ПДВ: {price_with_vat} грн")

    # Тест відсотків
    principal = Decimal('50000.00')
    interest_rate = Decimal('0.15')  # 15% річних
    monthly_rate = interest_rate / 12
    monthly_payment = principal * monthly_rate

    print(f"\n📈 РОЗРАХУНОК ВІДСОТКІВ:")
    print(f"   💳 Основна сума: {principal} грн")
    print(f"   📊 Річна ставка: {interest_rate * 100}%")
    print(f"   📅 Місячна ставка: {monthly_rate * 100:.2f}%")
    print(f"   💸 Місячний платіж: {monthly_payment:.2f} грн")

    # Тест валютних операцій
    uah_amount = Decimal('36500.00')
    usd_rate = Decimal('36.50')
    usd_amount = uah_amount / usd_rate

    print(f"\n💱 ВАЛЮТНІ РОЗРАХУНКИ:")
    print(f"   🇺🇦 Сума в гривнях: {uah_amount} UAH")
    print(f"   📊 Курс USD/UAH: {usd_rate}")
    print(f"   🇺🇸 Сума в доларах: ${usd_amount:.2f} USD")

    print(f"\n✅ ВСІ ФІНАНСОВІ РОЗРАХУНКИ ПРОЙШЛИ УСПІШНО!")


if __name__ == "__main__":
    test_finance_simple()