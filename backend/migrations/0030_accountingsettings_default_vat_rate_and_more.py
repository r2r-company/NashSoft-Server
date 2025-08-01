# Generated by Django 5.1.7 on 2025-07-19 15:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0029_documentsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingsettings',
            name='default_vat_rate',
            field=models.DecimalField(decimal_places=2, default=20.0, max_digits=5, verbose_name='Ставка ПДВ за замовчуванням (%)'),
        ),
        migrations.AddField(
            model_name='accountingsettings',
            name='reduced_vat_rate',
            field=models.DecimalField(decimal_places=2, default=7.0, max_digits=5, verbose_name='Знижена ставка ПДВ (%)'),
        ),
        migrations.AddField(
            model_name='accountingsettings',
            name='zero_vat_rate',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5, verbose_name='Нульова ставка ПДВ (%)'),
        ),
    ]
