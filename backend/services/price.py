# services/price.py - ДОПОВНЕНИЙ PriceAutoFillService
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from backend.models import PriceSettingDocument, PriceSettingItem, PriceType, Product, TradePoint
from django.utils.timezone import now


def get_price_from_setting(product, firm, trade_point=None, price_type=None, unit_conversion=None):
    """
    ✅ ОНОВЛЕНА функція отримання ціни з урахуванням фасування

    Args:
        product: Товар
        firm: Фірма
        trade_point: Торгова точка (опціонально)
        price_type: Тип ціни (якщо не вказано - беремо дефолтний)
        unit_conversion: Конкретне фасування (опціонально)

    Returns:
        dict з інформацією про ціну або None
    """
    from backend.models import AccountingSettings

    today = now().date()

    # Якщо тип ціни не переданий, беремо з налаштувань
    if not price_type:
        try:
            settings = AccountingSettings.objects.get(company=firm.company)
            if settings.default_price_type:
                price_type = settings.default_price_type
            else:
                price_type = PriceType.objects.filter(is_default=True).first()
        except AccountingSettings.DoesNotExist:
            price_type = PriceType.objects.filter(is_default=True).first()

    if not price_type:
        return None

    # Отримуємо актуальні документи ціноутворення
    docs = (
        PriceSettingDocument.objects
        .filter(status='approved', valid_from__lte=today, firm=firm)
        .order_by('-valid_from')
    )

    # ✅ ПОШУК З УРАХУВАННЯМ ФАСУВАННЯ:
    base_query_filters = {
        'product': product,
        'price_type': price_type,
        'firm': firm
    }

    # 1️⃣ Якщо запитується конкретне фасування
    if unit_conversion:
        # Шукаємо точну ціну для цього фасування
        for doc in docs:
            if trade_point:
                # Спочатку для конкретної торгової точки
                item = PriceSettingItem.objects.filter(
                    price_setting_document=doc,
                    trade_point=trade_point,
                    unit_conversion=unit_conversion,
                    **base_query_filters
                ).first()
                if item:
                    return _build_price_result(item)

            # Потім для всіх торгових точок
            item = PriceSettingItem.objects.filter(
                price_setting_document=doc,
                trade_point__isnull=True,
                unit_conversion=unit_conversion,
                **base_query_filters
            ).first()
            if item:
                return _build_price_result(item)

    # 2️⃣ Пошук для торгової точки (будь-яке фасування)
    if trade_point:
        for doc in docs.filter(trade_points=trade_point):
            item = PriceSettingItem.objects.filter(
                price_setting_document=doc,
                trade_point=trade_point,
                **base_query_filters
            ).first()
            if item:
                return _build_price_result(item)

    # 3️⃣ Фолбек: ціна по фірмі (базова одиниця)
    for doc in docs:
        item = PriceSettingItem.objects.filter(
            price_setting_document=doc,
            trade_point__isnull=True,
            unit_conversion__isnull=True,  # Базова одиниця
            **base_query_filters
        ).first()
        if item:
            return _build_price_result(item)

    return None


def get_all_prices_for_product(product, firm, trade_point=None, price_type=None):
    """
    ✅ НОВА функція: отримати ВСІ доступні ціни для товару (всі фасування)

    Returns:
        list з усіма варіантами цін для товару
    """
    from backend.models import AccountingSettings

    today = now().date()

    # Визначаємо тип ціни
    if not price_type:
        try:
            settings = AccountingSettings.objects.get(company=firm.company)
            price_type = settings.default_price_type or PriceType.objects.filter(is_default=True).first()
        except AccountingSettings.DoesNotExist:
            price_type = PriceType.objects.filter(is_default=True).first()

    if not price_type:
        return []

    # Отримуємо актуальні документи
    docs = (
        PriceSettingDocument.objects
        .filter(status='approved', valid_from__lte=today, firm=firm)
        .order_by('-valid_from')
    )

    prices = []
    seen_conversions = set()  # Щоб не дублювати фасування

    base_query_filters = {
        'product': product,
        'price_type': price_type,
        'firm': firm
    }

    # Шукаємо всі ціни для цього товару
    for doc in docs:
        query = PriceSettingItem.objects.filter(
            price_setting_document=doc,
            **base_query_filters
        )

        if trade_point:
            query = query.filter(Q(trade_point=trade_point) | Q(trade_point__isnull=True))

        items = query.all()

        for item in items:
            # Унікальний ключ для фасування
            conversion_key = item.unit_conversion.id if item.unit_conversion else 'base'

            if conversion_key not in seen_conversions:
                prices.append(_build_price_result(item))
                seen_conversions.add(conversion_key)

    return prices


def _build_price_result(price_item):
    """
    ✅ Допоміжна функція: формує результат з інформацією про ціну
    """
    package_info = price_item.get_package_info()

    return {
        'price_item_id': price_item.id,
        'price': float(price_item.price),
        'price_without_vat': float(price_item.price_without_vat),
        'vat_amount': float(price_item.vat_amount),
        'vat_percent': float(price_item.vat_percent),
        'vat_included': price_item.vat_included,

        # ✅ Інформація про одиниці та фасування:
        'unit_id': price_item.unit.id,
        'unit_name': price_item.unit.name,
        'unit_symbol': price_item.unit.symbol,

        'unit_conversion_id': price_item.unit_conversion.id if price_item.unit_conversion else None,
        'unit_conversion_name': price_item.unit_conversion.name if price_item.unit_conversion else None,

        # ✅ Детальна інформація про фасування:
        'package_info': package_info,

        # ✅ Метадані:
        'trade_point_id': price_item.trade_point.id if price_item.trade_point else None,
        'price_type_id': price_item.price_type.id,
        'valid_from': price_item.price_setting_document.valid_from.isoformat(),
        'doc_number': price_item.price_setting_document.doc_number,
    }
class PriceAutoFillService:
    def __init__(self, document):
        self.document = document

    @transaction.atomic
    def fill_items(self):
        """ДОПОВНЕНА версія з автоматичним розрахунком цін"""

        # Очищуємо старі позиції перед створенням нових
        self.document.items.all().delete()

        base_type = self.document.base_type
        products = Product.objects.none()

        # 1. Отримуємо товари на основі типу
        if base_type == 'product_group':
            if not self.document.base_group:
                raise ValidationError("Не вказано групу товарів для автозаповнення")
            products = Product.objects.filter(
                group=self.document.base_group,
                firm=self.document.firm  # ✅ Додано фільтр по фірмі
            )

        elif base_type == 'receipt':
            if not self.document.base_receipt:
                raise ValidationError("Не вказано документ поступлення для автозаповнення")
            products = Product.objects.filter(
                id__in=self.document.base_receipt.items.values_list('product_id', flat=True),
                firm=self.document.firm  # ✅ Додано фільтр по фірмі
            )

        elif base_type == 'price_type':
            if not self.document.base_price_type:
                raise ValidationError("Не вказано базовий тип ціни для автозаповнення")
            products = Product.objects.filter(
                id__in=PriceSettingItem.objects
                .filter(price_type=self.document.base_price_type, firm=self.document.firm)
                .values_list('product', flat=True),
                firm=self.document.firm  # ✅ Додано фільтр по фірмі
            )

        if not products.exists():
            raise ValidationError(f"Не знайдено товарів для автозаповнення на основі '{base_type}'")

        # 2. Визначаємо тип ціни
        default_price_type = self.document.base_price_type or PriceType.objects.filter(is_default=True).first()
        if not default_price_type:
            raise ValidationError("❗️Немає дефолтного типу ціни")

        # 3. Отримуємо торгові точки
        trade_points = self.document.trade_points.all()
        if not trade_points.exists() and self.document.firm:
            trade_points = TradePoint.objects.filter(firm=self.document.firm)

        if not trade_points.exists():
            raise ValidationError("Не вказано торгові точки для автозаповнення")

        # 4. Створюємо позиції з розрахованими цінами
        items_to_create = []

        for product in products:
            for tp in trade_points:
                # ✅ НОВА ЛОГІКА: розраховуємо ціну автоматично
                price_data = self._calculate_smart_price(product, tp, base_type)

                items_to_create.append(PriceSettingItem(
                    price_setting_document=self.document,
                    product=product,
                    price_type=default_price_type,
                    trade_point=tp,
                    firm=self.document.firm,  # ✅ Використовуємо фірму з документа
                    **price_data  # ✅ Розраховані дані (ціна, ПДВ, одиниці)
                ))

        # 5. Масове створення
        if items_to_create:
            PriceSettingItem.objects.bulk_create(items_to_create)

        return len(items_to_create)  # ✅ Повертаємо кількість створених позицій

    def _calculate_smart_price(self, product, trade_point, base_type):
        """✅ НОВА ФУНКЦІЯ: розумний розрахунок ціни"""

        # 1. Отримуємо базову ціну (собівартість)
        base_price = self._get_base_cost_price(product, base_type)

        # 2. Визначаємо націнку
        markup_percent = self._get_markup_for_product(product, trade_point)

        # 3. Розраховуємо продажну ціну
        selling_price = base_price * (1 + markup_percent / 100)

        # 4. Визначаємо одиниці
        unit_data = self._get_unit_for_product(product)

        # 5. Розраховуємо ПДВ
        vat_data = self._calculate_vat_for_price(selling_price)

        return {
            'price': round(selling_price, 2),
            'markup_percent': markup_percent,
            'unit': unit_data['unit'],
            'unit_conversion': unit_data['conversion'],
            **vat_data
        }

    def _get_base_cost_price(self, product, base_type):
        """Отримуємо базову собівартість товару"""

        if base_type == 'receipt' and self.document.base_receipt:
            # Беремо ціну з документа поступлення (собівартість)
            receipt_item = self.document.base_receipt.items.filter(product=product).first()
            if receipt_item:
                return receipt_item.price_without_vat or receipt_item.price

        elif base_type == 'price_type' and self.document.base_price_type:
            # Беремо ціну з іншого типу цін
            existing_item = PriceSettingItem.objects.filter(
                product=product,
                price_type=self.document.base_price_type,
                firm=self.document.firm
            ).first()
            if existing_item:
                return existing_item.price_without_vat or existing_item.price

        # ✅ Фолбек: беремо останню собівартість з операцій
        from backend.operations.stock import FIFOStockManager
        try:
            # Спробуємо отримати середню собівартість
            avg_cost = FIFOStockManager.get_average_cost_price(
                product,
                self.document.firm.warehouse_set.first(),  # Перший склад фірми
                self.document.firm
            )
            if avg_cost > 0:
                return avg_cost
        except:
            pass

        # Якщо нічого не знайшли - мінімальна ціна
        return Decimal('10')

    def _get_markup_for_product(self, product, trade_point):
        """Визначаємо націнку для товару"""

        # ✅ Розумна логіка націнки на основі категорії товару
        product_name = product.name.lower()

        if 'фарш' in product_name or 'м\'ясо' in product_name:
            return Decimal('400')  # 400% на м'ясо (з 10грн → 50грн)

        elif any(word in product_name for word in ['віскі', 'коньяк', 'алкоголь']):
            return Decimal('180')  # 180% на алкоголь (з ~36грн → 100грн)

        elif product.group and 'преміум' in product.group.name.lower():
            return Decimal('150')  # 150% на преміум товари

        # За типом торгової точки
        if trade_point and 'бар' in trade_point.name.lower():
            return Decimal('200')  # 200% націнка в барах

        # Дефолтна націнка
        return Decimal('100')  # 100% за замовчуванням

    def _get_unit_for_product(self, product):
        """Визначаємо одиницю для ціноутворення"""

        # За замовчуванням - базова одиниця товару
        unit = product.unit
        conversion = None

        # ✅ Можна додати логіку автоматичного вибору одиниці продажу
        # Наприклад, якщо товар в кілограмах, але продається в пакетиках

        from backend.models import ProductUnitConversion

        # Шукаємо найпопулярнішу конверсію для цього товару
        popular_conversion = ProductUnitConversion.objects.filter(
            product=product
        ).first()

        if popular_conversion:
            unit = popular_conversion.to_unit
            conversion = popular_conversion

        return {
            'unit': unit,
            'conversion': conversion
        }

    def _calculate_vat_for_price(self, price):
        """Розраховуємо ПДВ для ціни"""

        vat_percent = Decimal('0')

        # Визначаємо ставку ПДВ на основі типу фірми
        if self.document.firm.is_vat_payer:
            vat_percent = Decimal('20')  # 20% для ТОВ/ТЗОВ

        if vat_percent > 0:
            # Ціна ВКЛЮЧАЄ ПДВ - розділяємо
            price_without_vat = price / (1 + vat_percent / 100)
            vat_amount = price - price_without_vat
        else:
            # ФОП без ПДВ
            price_without_vat = price
            vat_amount = Decimal('0')

        return {
            'vat_percent': vat_percent,
            'vat_amount': round(vat_amount, 2),
            'price_without_vat': round(price_without_vat, 2),
            'vat_included': vat_percent > 0
        }