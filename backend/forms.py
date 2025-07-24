# backend/forms.py - СТВОРИТИ АБО ДОПОВНИТИ

from django import forms
from backend.models import PriceSettingItem, ProductUnitConversion


class PriceSettingItemForm(forms.ModelForm):
    """Форма для позицій ціноутворення"""

    class Meta:
        model = PriceSettingItem
        fields = [
            'product', 'price_type', 'price',
            'vat_percent', 'vat_included', 'markup_percent',
            'unit_conversion', 'firm'
        ]
        # ✅ ВИКЛЮЧАЄМО поле 'unit' - воно автоматичне

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ ПОКАЗУЄМО ВСІ ФАСУВАННЯ (користувач сам оберіть правильне)
        self.fields['unit_conversion'].queryset = ProductUnitConversion.objects.all()
        self.fields['unit_conversion'].required = False  # ✅ НЕ ОБОВ'ЯЗКОВЕ

        # Додаємо підказку
        self.fields['unit_conversion'].help_text = "Залиште порожнім для базової одиниці товару"

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        unit_conversion = cleaned_data.get('unit_conversion')

        # ✅ ПЕРЕВІРЯЄМО ЧИ ФАСУВАННЯ НАЛЕЖИТЬ ТОВАРУ
        if unit_conversion and product and unit_conversion.product != product:
            raise forms.ValidationError(
                f"Фасування '{unit_conversion.name}' не належить товару '{product.name}'"
            )

        return cleaned_data