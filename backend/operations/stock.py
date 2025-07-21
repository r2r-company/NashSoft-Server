# operations/stock.py
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal
from backend.models import Operation


class FIFOStockManager:

    @staticmethod
    def get_available_stock(product, warehouse, firm):
        """Отримати доступний залишок товару"""
        incoming = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            visible=True,
            direction='in'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        outgoing = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            visible=True,
            direction='out'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return incoming - outgoing

    @staticmethod
    def get_cost_price_for_quantity(product, warehouse, firm, needed_quantity):
        """
        Розрахувати середньозважену собівартість для вказаної кількості товару
        за методом FIFO
        """
        fifo_sources = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            direction='in',
            visible=True
        ).order_by('created_at')

        total_cost = Decimal('0')
        qty_collected = Decimal('0')
        needed = Decimal(str(needed_quantity))

        for source in fifo_sources:
            if qty_collected >= needed:
                break

            # Скільки вже використано з цієї партії
            used = Operation.objects.filter(
                source_operation=source,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            available_from_source = source.quantity - used

            if available_from_source <= 0:
                continue

            # Скільки візьмемо з цієї партії
            qty_to_take = min(available_from_source, needed - qty_collected)

            # Собівартість цієї частини
            cost_for_this_part = qty_to_take * source.cost_price
            total_cost += cost_for_this_part
            qty_collected += qty_to_take

        if qty_collected < needed:
            raise ValidationError(
                f"Недостатньо залишку для товару '{product.name}'. "
                f"Є: {qty_collected}, потрібно: {needed}"
            )

        # Середньозважена собівартість
        return total_cost / qty_collected if qty_collected > 0 else Decimal('0')

    @staticmethod
    def sell_fifo(document, product, warehouse, quantity, sale_price=None):
        """
        Продати товар за методом FIFO
        quantity - кількість для продажу
        sale_price - ціна продажу (опціонально)
        """
        firm = document.firm
        available_stock = FIFOStockManager.get_available_stock(product, warehouse, firm)

        if available_stock < quantity:
            raise ValidationError(
                f"Недостатньо залишку для товару '{product.name}'. "
                f"Є: {available_stock}, потрібно: {quantity}"
            )

        fifo_sources = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            direction='in',
            visible=True
        ).order_by('created_at')

        qty_needed = Decimal(str(quantity))
        total_cost = Decimal('0')

        for source in fifo_sources:
            if qty_needed <= 0:
                break

            # Скільки вже використано з цієї партії
            used = Operation.objects.filter(
                source_operation=source,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            available_from_source = source.quantity - used

            if available_from_source <= 0:
                continue

            # Скільки візьмемо з цієї партії
            qty_to_deduct = min(available_from_source, qty_needed)

            # Собівартість цієї частини
            cost_for_this_part = qty_to_deduct * source.cost_price
            total_cost += cost_for_this_part

            # Створюємо операцію списання
            Operation.objects.create(
                document=document,
                product=product,
                quantity=qty_to_deduct,
                cost_price=source.cost_price,  # ⬅️ Собівартість з партії
                sale_price=sale_price,  # ⬅️ Ціна продажу
                warehouse=warehouse,
                direction='out',
                visible=True,
                source_operation=source
            )

            qty_needed -= qty_to_deduct

        return total_cost  # Повертаємо загальну собівартість

    @staticmethod
    def get_average_cost_price(product, warehouse, firm):
        """
        Отримати середню собівартість товару на складі
        """
        # Всі операції надходження
        incoming_ops = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            direction='in',
            visible=True
        )

        if not incoming_ops.exists():
            return Decimal('0')

        total_cost = Decimal('0')
        total_quantity = Decimal('0')

        for op in incoming_ops:
            # Скільки з цієї партії ще залишилось
            used = Operation.objects.filter(
                source_operation=op,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            remaining_qty = op.quantity - used

            if remaining_qty > 0:
                total_cost += remaining_qty * op.cost_price
                total_quantity += remaining_qty

        return total_cost / total_quantity if total_quantity > 0 else Decimal('0')

    @staticmethod
    def get_stock_value(product, warehouse, firm):
        """
        Отримати вартість залишків товару на складі
        """
        incoming_ops = Operation.objects.filter(
            product=product,
            warehouse=warehouse,
            document__firm=firm,
            direction='in',
            visible=True
        )

        total_value = Decimal('0')

        for op in incoming_ops:
            # Скільки з цієї партії ще залишилось
            used = Operation.objects.filter(
                source_operation=op,
                direction='out',
                visible=True
            ).aggregate(total=Sum('quantity'))['total'] or 0

            remaining_qty = op.quantity - used

            if remaining_qty > 0:
                total_value += remaining_qty * op.cost_price

        return total_value