from decimal import Decimal, ROUND_HALF_UP
from backend.models import PriceSettingDocument, PriceSettingItem, PriceType, Product


class PriceCalculatorService:
    def __init__(self, product: Product, company, date, price_type_name='Роздріб', mode='from_price_with_vat'):
        self.product = product
        self.company = company
        self.date = date
        self.price_type_name = price_type_name
        self.mode = mode
        self.vat_percent = Decimal(product.vat_rate or 0)

    def get_price_item(self):
        price_type = PriceType.objects.filter(name=self.price_type_name).first()
        if not price_type:
            return None

        doc = (
            PriceSettingDocument.objects
            .filter(company=self.company, status='approved', valid_from__lte=self.date)
            .order_by('-valid_from')
            .first()
        )
        if not doc:
            return None

        return PriceSettingItem.objects.filter(
            price_setting_document=doc,
            product=self.product,
            price_type=price_type
        ).first()

    def calculate(self):
        item = self.get_price_item()
        if not item:
            return None

        price = Decimal(item.price or 0)
        vat = self.vat_percent

        if self.mode == 'from_price_with_vat':
            price_with_vat = price
            vat_amount = (price_with_vat * vat / (100 + vat)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            price_without_vat = price_with_vat - vat_amount
        else:  # mode == 'from_price_without_vat'
            price_without_vat = price
            vat_amount = (price_without_vat * vat / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            price_with_vat = price_without_vat + vat_amount

        return {
            "price_with_vat": round(price_with_vat, 2),
            "price_without_vat": round(price_without_vat, 2),
            "vat_amount": round(vat_amount, 2),
            "vat_percent": vat
        }
