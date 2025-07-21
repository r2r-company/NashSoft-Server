# full_clear.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from django.db import connection, transaction
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from backend.models import *
from settlements.models import *


def full_clear():
    print("🧹 ПОВНЕ ОЧИЩЕННЯ БАЗИ ДАНИХ")
    print("=" * 50)

    with transaction.atomic():
        with connection.cursor() as cursor:
            # Вимикаємо перевірки
            cursor.execute("SET session_replication_role = replica;")

            # Таблиці для очищення в правильному порядку
            tables_to_clear = [
                # Операційні дані
                'backend_auditlog',
                'settlements_moneyoperation',
                'settlements_moneydocument',
                'settlements_moneyledgerentry',
                'backend_operation',
                'backend_documentitem',
                'backend_document',
                'backend_pricesettingitem',
                'backend_pricesettingdocument',

                # Довідники
                'backend_productunitconversion',
                'backend_productcalculationitem',
                'backend_productcalculation',
                'settlements_contract',
                'backend_appuser_interfaces',
                'backend_appuser',
                'backend_departmentwarehouseaccess',
                'backend_department',
                'backend_tradepoint',
                'backend_product',
                'backend_productgroup',
                'backend_warehouse',
                'backend_firm',
                'backend_customer',
                'backend_supplier',
                'backend_company',

                # Налаштування
                'backend_accountingsettings',
                'backend_documentsettings',
                'backend_pricetype',
                'backend_customertype',
                'backend_paymenttype',
                'backend_unit',
                'backend_interface',
                'settlements_account',

                # Система прав
                'auth_group_permissions',
                'auth_user_groups',
                'auth_user_user_permissions',
                'auth_group',

                # Django системні
                'django_session',
                'django_admin_log',
            ]

            for table in tables_to_clear:
                try:
                    cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
                    print(f"   ✅ Очищено: {table}")
                except Exception as e:
                    print(f"   ⚠️ Помилка очищення {table}: {e}")

            # Видаляємо звичайних користувачів (залишаємо адмінів)
            try:
                deleted_users = User.objects.filter(is_superuser=False).count()
                User.objects.filter(is_superuser=False).delete()
                print(f"   ✅ Видалено користувачів: {deleted_users}")
            except Exception as e:
                print(f"   ⚠️ Помилка видалення користувачів: {e}")

            # Відновлюємо перевірки
            cursor.execute("SET session_replication_role = DEFAULT;")

    # Перевіряємо результат
    print(f"\n📊 РЕЗУЛЬТАТ ОЧИЩЕННЯ:")

    tables_to_check = [
        ('Компанії', Company),
        ('Фірми', Firm),
        ('Склади', Warehouse),
        ('Товари', Product),
        ('Документи', Document),
        ('Операції', Operation),
        ('Користувачі', User),
    ]

    for name, model in tables_to_check:
        try:
            count = model.objects.count()
            status = "✅" if count == 0 or (name == "Користувачі" and count <= 1) else "⚠️"
            print(f"   {status} {name}: {count}")
        except Exception as e:
            print(f"   ❌ {name}: помилка підрахунку")

    print(f"\n🎯 БАЗА ГОТОВА ДО СТВОРЕННЯ ТЕСТОВИХ ДАНИХ!")


if __name__ == "__main__":
    full_clear()