# add_vat_logic.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from django.db import migrations, models

# Додаємо поле в модель через код
from backend.models import Firm


def add_vat_logic():
    print("🧾 ДОДАЄМО ЛОГІКУ ПДВ ДО ФІРМ")
    print("=" * 40)

    # Оновлюємо існуючі фірми
    firms = Firm.objects.all()

    for firm in firms:
        if firm.vat_type == 'ФОП':
            firm.is_vat_payer = False
            status = "БЕЗ ПДВ"
        else:
            firm.is_vat_payer = True
            status = "З ПДВ"

        print(f"   ✅ {firm.name} ({firm.vat_type}): {status}")
        # firm.save()  # Розкоментуйте після додавання поля

    print(f"\n📊 ОНОВЛЕНО ФІРМ: {firms.count()}")


if __name__ == "__main__":
    add_vat_logic()