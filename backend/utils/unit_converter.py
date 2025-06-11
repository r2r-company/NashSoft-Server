from backend.models import ProductUnitConversion

def convert_to_base(product, from_unit, quantity):
    """
    Конвертує quantity з from_unit у базову одиницю товару (product.unit).
    Якщо конверсія відсутня — повертає quantity як є (вважає, що одиниці збігаються).
    """
    if from_unit == product.unit:
        return quantity  # Одиниці однакові — не треба нічого рахувати

    # Спроба прямої конверсії
    direct = ProductUnitConversion.objects.filter(
        product=product,
        from_unit=from_unit,
        to_unit=product.unit
    ).first()
    if direct:
        return quantity * direct.factor

    # Спроба зворотної конверсії
    reverse = ProductUnitConversion.objects.filter(
        product=product,
        from_unit=product.unit,
        to_unit=from_unit
    ).first()
    if reverse and reverse.factor != 0:
        return quantity / reverse.factor

    # 🚨 Якщо не знайдено конверсію — просто беремо як є
    return quantity
