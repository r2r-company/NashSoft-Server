from collections import defaultdict
from decimal import Decimal

from backend.models import Product
from backend.operations.StockPricing import StockPricing


class TechCalculationService:
    def __init__(self, product_id: int, mode: str, weight: Decimal, warehouse=None, firm=None):
        self.product = Product.objects.get(id=product_id)
        self.mode = mode
        self.weight = Decimal(weight)
        self.warehouse = warehouse
        self.firm = firm
        self.result = []
        self.total_cost = Decimal("0.000")
        self.debug_info = []

    def get_current_calculation(self):
        return self.product.calculations.order_by('-date').first()

    def calculate(self):
        calculation = self.get_current_calculation()
        if not calculation:
            raise ValueError("Калькуляція відсутня для цього продукту")

        if self.mode == 'output':
            self._expand_items(calculation, multiplier=self.weight)
        elif self.mode == 'input':
            self._expand_items(calculation, multiplier=Decimal(1.0))
        else:
            raise ValueError("Невідомий режим: має бути 'input' або 'output'")

        total_per_ingredient = defaultdict(lambda: {"required_quantity": Decimal("0.000"), "unit": "", "name": ""})
        for item in self.result:
            pid = item["product_id"]
            total_per_ingredient[pid]["required_quantity"] += Decimal(item["required_quantity"])
            total_per_ingredient[pid]["unit"] = item["unit"]
            total_per_ingredient[pid]["name"] = item["name"]

        total_per_ingredient_list = []
        for pid, data in total_per_ingredient.items():
            product = Product.objects.get(id=pid)
            avg_price = StockPricing.avg_price(product, warehouse=self.warehouse, firm=self.firm)
            ingredient_cost = data["required_quantity"] * avg_price
            self.total_cost += ingredient_cost

            total_per_ingredient_list.append({
                "product_id": pid,
                "name": data["name"],
                "unit": data["unit"],
                "total_required_quantity": round(data["required_quantity"], 3),
                "avg_price": round(avg_price, 2),
                "ingredient_cost": round(ingredient_cost, 2)
            })

        response = {
            "product": self.product.name,
            "product_id": self.product.id,
            "mode": self.mode,
            "weight": float(self.weight),
            "ingredients": self.result,
            "total_per_ingredient": total_per_ingredient_list,
            "total_cost": round(self.total_cost, 2),
            "debug_info": self.debug_info
        }

        if self.mode == 'input':
            total_required = sum(d["total_required_quantity"] for d in total_per_ingredient_list)
            if total_required == 0:
                raise ValueError("Загальна вага інгредієнтів не може бути 0")
            calculated_output = self.weight / total_required
            response["calculated_output"] = round(calculated_output, 3)
            response["cost_per_unit"] = round(self.total_cost / calculated_output, 2)
        else:
            response["cost_per_unit"] = round(self.total_cost / self.weight, 2)

        return response

    def _expand_items(self, calculation, multiplier):
        for item in calculation.items.all():
            # ✅ ВРАХОВУЄМО ФАСУВАННЯ:
            base_quantity = self._get_base_quantity(item)
            display_info = self._get_display_info(item)

            loss_factor = (1 - item.loss_percent / 100) * (1 - item.cooking_loss_percent / 100)
            if loss_factor == 0:
                continue

            real_qty = base_quantity / loss_factor
            total_qty = real_qty * multiplier

            self.debug_info.append({
                "product_id": item.component.id,
                "name": item.component.name,
                "unit": item.component.unit.symbol or item.component.unit.name,
                # ✅ ДОДАЄМО ІНФОРМАЦІЮ ПРО ФАСУВАННЯ:
                "recipe_quantity": float(item.quantity),  # Кількість в рецепті
                "recipe_unit": display_info["unit_name"],  # Одиниця в рецепті
                "base_quantity": float(base_quantity),  # В базових одиницях
                "conversion_factor": float(display_info["conversion_factor"]),
                "loss_percent": float(item.loss_percent),
                "cooking_loss_percent": float(item.cooking_loss_percent),
                "adjusted_quantity": round(real_qty, 5),
                "multiplier": float(multiplier),
                "total_quantity": round(total_qty, 5),
            })

            if item.component.type == 'ingredient':
                self.result.append({
                    "product_id": item.component.id,
                    "name": item.component.name,
                    "unit": item.component.unit.symbol or item.component.unit.name,
                    "required_quantity": round(total_qty, 3),
                    "total_loss_percent": round((1 - loss_factor) * 100, 2),
                    # ✅ ДОДАЄМО ІНФОРМАЦІЮ ПРО ФАСУВАННЯ В РЕЗУЛЬТАТ:
                    "packaging_info": {
                        "recipe_quantity": float(item.quantity),
                        "recipe_unit": display_info["unit_name"],
                        "conversion_factor": float(display_info["conversion_factor"]),
                        "unit_conversion_id": display_info["unit_conversion_id"]
                    }
                })
            elif item.component.type == 'semi':
                sub_calc = item.component.calculations.order_by('-date').first()
                if sub_calc:
                    sub_service = TechCalculationService(
                        item.component.id, 'output', total_qty,
                        warehouse=self.warehouse, firm=self.firm
                    )
                    sub_result = sub_service.calculate()
                    self.result.extend(sub_result['ingredients'])
                    self.debug_info.extend(sub_service.debug_info)
                else:
                    raise ValueError(f"Немає калькуляції для напівфабрикату: {item.component.name}")
            else:
                continue

    def _get_base_quantity(self, calculation_item):
        """
        Отримати кількість в базових одиницях

        Якщо є unit_conversion - конвертуємо
        Якщо немає - використовуємо як є
        """
        if hasattr(calculation_item, 'unit_conversion') and calculation_item.unit_conversion:
            # Фасування: 2 мішки × 25 кг/мішок = 50 кг
            return calculation_item.quantity * calculation_item.unit_conversion.factor
        else:
            # Базова одиниця: 2 кг = 2 кг
            return calculation_item.quantity

    def _get_display_info(self, calculation_item):
        """
        Отримати інформацію для відображення
        """
        if hasattr(calculation_item, 'unit_conversion') and calculation_item.unit_conversion:
            return {
                "unit_name": calculation_item.unit_conversion.to_unit.name,
                "unit_symbol": calculation_item.unit_conversion.to_unit.symbol,
                "conversion_factor": calculation_item.unit_conversion.factor,
                "unit_conversion_id": calculation_item.unit_conversion.id
            }
        else:
            return {
                "unit_name": calculation_item.component.unit.name,
                "unit_symbol": calculation_item.component.unit.symbol,
                "conversion_factor": Decimal('1'),
                "unit_conversion_id": None
            }

    def get_packaging_summary(self):
        """
        Додатковий метод для отримання зведення по фасуваннях
        """
        packaging_summary = []

        for item in self.result:
            if 'packaging_info' in item and item['packaging_info']['unit_conversion_id']:
                packaging_summary.append({
                    'ingredient': item['name'],
                    'recipe_amount': f"{item['packaging_info']['recipe_quantity']} {item['packaging_info']['recipe_unit']}",
                    'base_amount': f"{item['required_quantity']} {item['unit']}",
                    'conversion': f"1 {item['packaging_info']['recipe_unit']} = {item['packaging_info']['conversion_factor']} {item['unit']}"
                })

        return packaging_summary