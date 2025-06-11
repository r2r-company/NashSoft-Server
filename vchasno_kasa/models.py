from django.db import models
from django.utils.translation import gettext_lazy as _
from backend.models import Company, TradePoint
from django.contrib.auth import get_user_model

User = get_user_model()

class VchasnoDevice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія")
    name = models.CharField(max_length=100, verbose_name="Назва пристрою")
    device_id = models.CharField(max_length=100, unique=True, verbose_name="ID пристрою (з Вчасно)")
    is_active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Пристрій Вчасно Каса"
        verbose_name_plural = "Пристрої Вчасно Каса"

    def __str__(self):
        return f"{self.name} ({self.device_id})"


class VchasnoCashier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Користувач")
    cashier_id = models.CharField(max_length=100, verbose_name="ID касира (з Вчасно)")
    name = models.CharField(max_length=100, verbose_name="Ім’я касира у Вчасно")
    inn = models.CharField(max_length=20, verbose_name="ІПН")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Касир Вчасно"
        verbose_name_plural = "Касири Вчасно"

    def __str__(self):
        return f"{self.name} ({self.inn})"


class VchasnoShift(models.Model):
    device = models.ForeignKey(VchasnoDevice, on_delete=models.CASCADE)
    cashier = models.ForeignKey(VchasnoCashier, on_delete=models.CASCADE)
    trade_point = models.ForeignKey(TradePoint, on_delete=models.CASCADE, null=True, blank=True)
    shift_number = models.PositiveIntegerField()
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('opened', 'Відкрита'), ('closed', 'Закрита')], default='opened')

    class Meta:
        verbose_name = "Зміна Вчасно"
        verbose_name_plural = "Зміни Вчасно"

    def __str__(self):
        return f"Зміна #{self.shift_number} ({self.device.name})"
