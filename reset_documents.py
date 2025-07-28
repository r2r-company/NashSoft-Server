# clear_documents_smart.py - розумне очищення з обробкою помилок
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nashsoft.settings')
django.setup()

from django.db import connection, transaction
from django.db.models.signals import pre_delete, post_delete
from backend.models import *
from settlements.models import *


def disable_all_signals():
    """Відключає всі захисні сигнали"""
    from backend import signals

    disabled_signals = []

    # Відключаємо сигнали операцій
    try:
        pre_delete.disconnect(signals.prevent_delete_operation_if_used, sender=Operation)
        disabled_signals.append(('operation_protection', signals.prevent_delete_operation_if_used, Operation))
        print("   ✅ Відключено захист операцій")
    except Exception:
        pass

    # Відключаємо сигнали документів
    try:
        pre_delete.disconnect(signals.prevent_delete_posted_document, sender=Document)
        disabled_signals.append(('document_protection', signals.prevent_delete_posted_document, Document))
        print("   ✅ Відключено захист документів")
    except Exception:
        pass

    # Відключаємо сигнали грошових документів
    try:
        pre_delete.disconnect(signals.prevent_delete_posted_document, sender=MoneyDocument)
        disabled_signals.append(('money_document_protection', signals.prevent_delete_posted_document, MoneyDocument))
        print("   ✅ Відключено захист грошових документів")
    except Exception:
        pass

    return disabled_signals


def restore_signals(disabled_signals):
    """Відновлює всі відключені сигнали"""
    for signal_name, signal_func, sender_model in disabled_signals:
        try:
            pre_delete.connect(signal_func, sender=sender_model)
            print(f"   ✅ Відновлено {signal_name}")
        except Exception as e:
            print(f"   ⚠️ Помилка відновлення {signal_name}: {e}")


def clear_table_safe(model_class, description):
    """Безпечне очищення таблиці через Django ORM"""
    try:
        count = model_class.objects.count()
        if count > 0:
            print(f"🗑️ {description}...")

            # Спочатку знімаємо проведення якщо є поле is_posted
            if hasattr(model_class._meta.get_field('is_posted'), 'name'):
                posted_count = model_class.objects.filter(is_posted=True).count()
                if posted_count > 0:
                    model_class.objects.filter(is_posted=True).update(is_posted=False)
                    print(f"   📋 Знято проведення з {posted_count} записів")

            # Видаляємо всі записи
            model_class.objects.all().delete()
            print(f"   ✅ Видалено {description}: {count}")
            return count
        else:
            print(f"   ℹ️ {description}: відсутні")
            return 0
    except Exception as e:
        print(f"   ❌ Помилка при видаленні {description}: {e}")
        return 0


def clear_documents_smart():
    print("🧹 РОЗУМНЕ ОЧИЩЕННЯ ДОКУМЕНТІВ")
    print("🔧 З відключенням сигналів та обробкою помилок")
    print("📋 Довідники залишаються без змін")
    print("=" * 50)

    # Відключаємо сигнали
    print("🔧 Відключаємо захисні сигнали...")
    disabled_signals = disable_all_signals()

    total_deleted = 0

    try:
        # Очищення в правильному порядку (від залежних до основних)

        # 1️⃣ АУДИТ ЛОГИ
        try:
            deleted = clear_table_safe(AuditLog, "Аудит логи")
            total_deleted += deleted
        except Exception as e:
            print(f"   ⚠️ Таблиця AuditLog не існує: {e}")

        # 2️⃣ FIFO ЗВ'ЯЗКИ (якщо є)
        try:
            # Спробуємо знайти модель FIFOConnection
            for model_name in dir():
                if 'fifo' in model_name.lower() and hasattr(globals()[model_name], '_meta'):
                    model_class = globals()[model_name]
                    deleted = clear_table_safe(model_class, f"FIFO {model_name}")
                    total_deleted += deleted
        except Exception as e:
            print(f"   ℹ️ FIFO моделі не знайдені: {e}")

        # 3️⃣ БУХГАЛТЕРСЬКІ ПРОВОДКИ
        try:
            # Шукаємо AccountingEntry в різних місцях
            try:
                from backend.models import AccountingEntry
                deleted = clear_table_safe(AccountingEntry, "Бухгалтерські проводки (backend)")
                total_deleted += deleted
            except ImportError:
                pass

            try:
                from settlements.models import AccountingEntry as SettlementsAccountingEntry
                deleted = clear_table_safe(SettlementsAccountingEntry, "Бухгалтерські проводки (settlements)")
                total_deleted += deleted
            except ImportError:
                pass
        except Exception as e:
            print(f"   ℹ️ Бухгалтерські проводки не знайдені: {e}")

        # 4️⃣ ПОЗИЦІЇ ЦІНОУТВОРЕННЯ
        deleted = clear_table_safe(PriceSettingItem, "Позиції ціноутворення")
        total_deleted += deleted

        # 5️⃣ ДОКУМЕНТИ ЦІНОУТВОРЕННЯ
        deleted = clear_table_safe(PriceSettingDocument, "Документи ціноутворення")
        total_deleted += deleted

        # 6️⃣ ГРОШОВІ ОПЕРАЦІЇ
        try:
            deleted = clear_table_safe(MoneyOperation, "Грошові операції")
            total_deleted += deleted
        except Exception as e:
            print(f"   ℹ️ MoneyOperation не існує: {e}")

        # 7️⃣ ГРОШОВІ ДОКУМЕНТИ
        try:
            deleted = clear_table_safe(MoneyDocument, "Грошові документи")
            total_deleted += deleted
        except Exception as e:
            print(f"   ℹ️ MoneyDocument не існує: {e}")

        # 8️⃣ СКЛАДСЬКІ ОПЕРАЦІЇ
        deleted = clear_table_safe(Operation, "Складські операції")
        total_deleted += deleted

        # 9️⃣ ПОЗИЦІЇ ДОКУМЕНТІВ
        deleted = clear_table_safe(DocumentItem, "Позиції документів")
        total_deleted += deleted

        # 🔟 ДОКУМЕНТИ (останніми)
        deleted = clear_table_safe(Document, "Документи")
        total_deleted += deleted

        # СКИДАННЯ ЛІЧИЛЬНИКІВ
        print("🔢 Скидання автоінкрементів...")
        try:
            with connection.cursor() as cursor:
                # Для PostgreSQL скидаємо sequences
                sequences_to_reset = [
                    'backend_document_id_seq',
                    'backend_documentitem_id_seq',
                    'backend_operation_id_seq',
                    'settlements_moneydocument_id_seq',
                    'settlements_moneyoperation_id_seq',
                    'backend_pricesettingdocument_id_seq',
                    'backend_pricesettingitem_id_seq',
                    'backend_auditlog_id_seq'
                ]

                reset_count = 0
                for sequence_name in sequences_to_reset:
                    try:
                        # Перевіряємо чи існує sequence
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT 1 FROM pg_class 
                                WHERE relkind = 'S' AND relname = %s
                            )
                        """, [sequence_name])

                        if cursor.fetchone()[0]:
                            cursor.execute(f"ALTER SEQUENCE {sequence_name} RESTART WITH 1")
                            reset_count += 1

                    except Exception as e:
                        # Sequence може не існувати - це нормально
                        pass

                print(f"   ✅ Скинуто sequences: {reset_count}")

        except Exception as e:
            print(f"   ⚠️ Помилка при скиданні sequences: {e}")

    finally:
        # Відновлюємо сигнали
        print("🔧 Відновлюємо захисні сигнали...")
        restore_signals(disabled_signals)

    print(f"\n🎉 РОЗУМНЕ ОЧИЩЕННЯ ЗАВЕРШЕНО!")
    print(f"   📊 Всього видалено записів: {total_deleted}")

    # Перевіряємо результати
    print(f"\n🔍 ПЕРЕВІРКА РЕЗУЛЬТАТІВ:")

    verification_models = [
        (Document, "📄 Документи"),
        (DocumentItem, "📋 Позиції документів"),
        (Operation, "📦 Складські операції"),
        (PriceSettingDocument, "💰 Документи ціноутворення"),
        (PriceSettingItem, "💰 Позиції ціноутворення")
    ]

    # Додаємо опціональні моделі
    optional_models = [
        (MoneyDocument, "💵 Грошові документи"),
        (MoneyOperation, "💵 Грошові операції"),
        (AuditLog, "📝 Аудит логи")
    ]

    for model_class, description in optional_models:
        try:
            verification_models.append((model_class, description))
        except:
            pass

    all_clean = True
    for model_class, description in verification_models:
        try:
            count = model_class.objects.count()
            if count == 0:
                print(f"   ✅ {description}: {count}")
            else:
                print(f"   ❌ {description}: {count} (залишились!)")
                all_clean = False
        except Exception as e:
            print(f"   ⚠️ {description}: помилка - {e}")

    # Показуємо довідники що залишились
    print(f"\n✅ ДОВІДНИКИ ЗБЕРЕЖЕНІ:")
    reference_models = [
        (Company, "🏢 Компанії"),
        (Firm, "🏭 Фірми"),
        (Warehouse, "📦 Склади"),
        (Product, "🛍️ Товари"),
        (ProductGroup, "📂 Групи товарів"),
        (Customer, "👥 Клієнти"),
        (Supplier, "🚚 Постачальники"),
        (Unit, "📏 Одиниці виміру"),
        (TradePoint, "🏪 Торгові точки"),
        (PaymentType, "💳 Типи оплат"),
        (CustomerType, "🏷️ Типи клієнтів"),
        (PriceType, "💰 Типи цін"),
        (ProductUnitConversion, "📊 Фасування")
    ]

    for model_class, description in reference_models:
        try:
            count = model_class.objects.count()
            print(f"   {description}: {count}")
        except Exception as e:
            print(f"   {description}: помилка - {e}")

    if all_clean:
        print(f"\n🚀 СИСТЕМА ГОТОВА ДО РОБОТИ!")
        print(f"   ✅ Всі документи очищені")
        print(f"   ✅ Довідники збережені")
        print(f"   ✅ Лічильники скинуті")
    else:
        print(f"\n⚠️ УВАГА: Не все очищено")
        print(f"   🔧 Перегляньте помилки вище")

    print(f"\n💼 РЕКОМЕНДАЦІЇ ДЛЯ ERP:")
    print(f"   1️⃣ Перевірити базові налаштування системи")
    print(f"   2️⃣ Встановити ціни на товари")
    print(f"   3️⃣ Оформити тестове поступлення")
    print(f"   4️⃣ Провести документ і перевірити залишки")
    print(f"   5️⃣ Налаштувати права користувачів")
    print(f"   6️⃣ Перевірити звіти та аналітику")

    return all_clean


if __name__ == "__main__":
    print("🚨 УВАГА! Очищення всіх документів та операцій!")
    print("📋 Довідники залишаться, документообіг буде скинутий")

    confirm = input("\n❓ Продовжити? Введіть 'ТАК': ")

    if confirm.upper() == 'ТАК':
        success = clear_documents_smart()
        if success:
            print("\n🎊 ГОТОВО! Система очищена і готова до роботи!")
        else:
            print("\n⚠️ Очищення завершено з помилками. Перевірте результати.")
    else:
        print("❌ Операція скасована.")