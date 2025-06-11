from django import forms
from django.core.exceptions import ValidationError
from backend.models import ProductUnitConversion, Unit, PriceSettingItem



class PriceSettingItemForm(forms.ModelForm):
    class Meta:
        model = PriceSettingItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        product = self.initial.get('product') or self.data.get('product')
        if product:
            self.fields['unit'].queryset = Unit.objects.filter(
                id__in=ProductUnitConversion.objects.filter(product_id=product).values_list('to_unit', flat=True)
            )
        else:
            self.fields['unit'].queryset = Unit.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("unit_conversion"):
            raise ValidationError("Фасування (unit_conversion) обов’язкове.")
        return cleaned_data
