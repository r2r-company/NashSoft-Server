# fix_duplicates.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from backend.models import Unit


def fix_unit_duplicates():
    print("🔧 ВИПРАВЛЕННЯ ДУБЛІКАТІВ ОДИНИЦЬ ВИМІРУ")

    # Знаходимо дублікати
    symbols = ['шт', 'кг', 'л', 'м', 'упак']

    for symbol in symbols:
        units = Unit.objects.filter(symbol=symbol)
        if units.count() > 1:
            print(f"   ⚠️ Знайдено {units.count()} одиниць з символом '{symbol}'")

            # Залишаємо першу, видаляємо інші
            first_unit = units.first()
            duplicates = units.exclude(id=first_unit.id)

            for dup in duplicates:
                print(f"      🗑️ Видаляємо дублікат: {dup.name} ({dup.symbol})")
                dup.delete()

            print(f"   ✅ Залишилась: {first_unit.name} ({first_unit.symbol})")
        else:
            print(f"   ✅ Одиниця '{symbol}' унікальна")

    print("\n📋 ФІНАЛЬНИЙ СПИСОК ОДИНИЦЬ:")
    for unit in Unit.objects.all().order_by('symbol'):
        print(f"   {unit.symbol} - {unit.name}")


if __name__ == "__main__":
    fix_unit_duplicates()