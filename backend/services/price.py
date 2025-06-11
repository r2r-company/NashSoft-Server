# services/price.py
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from backend.models import PriceSettingDocument, PriceSettingItem, PriceType, Product, TradePoint
from django.utils.timezone import now



def get_price_from_setting(product, firm, trade_point, price_type):
    today = now().date()

    docs = (
        PriceSettingDocument.objects
        .filter(status='approved', valid_from__lte=today, company=firm.company)
        .order_by('-valid_from')
    )

    # 1️⃣ Перевага: ціна для конкретної торгової точки + фірма
    if trade_point:
        for doc in docs.filter(trade_points=trade_point):
            item = PriceSettingItem.objects.filter(
                price_setting_document=doc,
                product=product,
                price_type=price_type,
                trade_point=trade_point,
                firm=firm
            ).first()
            if item:
                return item.price

    # 2️⃣ Фолбек: ціна по фірмі (на всі торгові точки)
    for doc in docs:
        item = PriceSettingItem.objects.filter(
            price_setting_document=doc,
            product=product,
            price_type=price_type,
            trade_point__isnull=True,  # 🔥 ключ: ціна для фірми
            firm=firm
        ).first()
        if item:
            return item.price

    return None





class PriceAutoFillService:
    def __init__(self, document):
        self.document = document

    def fill_items(self):
        base_type = self.document.base_type
        products = Product.objects.none()

        if base_type == 'product_group':
            products = Product.objects.filter(group=self.document.base_group)
        elif base_type == 'receipt':
            products = Product.objects.filter(
                id__in=self.document.base_receipt.items.values_list('product_id', flat=True)
            )
        elif base_type == 'price_type':
            products = Product.objects.filter(
                id__in=PriceSettingItem.objects
                .filter(price_type=self.document.base_price_type)
                .values_list('product', flat=True)
            )

        default_price_type = self.document.base_price_type or PriceType.objects.filter(is_default=True).first()
        if not default_price_type:
            raise Exception("❗️Немає дефолтного типу ціни")

        # ⬇️ ТТ: або вже вибрані, або беремо всі з фірми
        trade_points = self.document.trade_points.all()
        if not trade_points.exists() and self.document.firm:
            trade_points = TradePoint.objects.filter(firm=self.document.firm)

        # Якщо після цього все одно пусто — не створюємо нічого
        if not trade_points.exists():
            return

        items = []
        for product in products:
            for tp in trade_points:
                items.append(PriceSettingItem(
                    price_setting_document=self.document,
                    product=product,
                    price_type=default_price_type,
                    price=0,
                    trade_point=tp,
                    firm=tp.firm  # ⬅️ щоб був фільтр по фірмі в get_price_from_setting
                ))

        PriceSettingItem.objects.bulk_create(items)

