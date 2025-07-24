from backend.models import ProductUnitConversion

def convert_to_base(product, from_unit, quantity):

    if from_unit == product.unit:
        return quantity

    # ✅ ПРЯМА КОНВЕРСІЯ: from_unit → product.unit
    direct = ProductUnitConversion.objects.filter(
        product=product,
        from_unit=from_unit,
        to_unit=product.unit
    ).first()
    if direct:
        return quantity * direct.factor

    # ✅ ЗВОРОТНА КОНВЕРСІЯ: product.unit → from_unit
    reverse = ProductUnitConversion.objects.filter(
        product=product,
        from_unit=product.unit,
        to_unit=from_unit
    ).first()
    if reverse and reverse.factor != 0:
        # ✅ ВИПРАВЛЕННЯ: правильна зворотна конверсія
        return quantity * reverse.factor  # НЕ ділити!

    return quantity