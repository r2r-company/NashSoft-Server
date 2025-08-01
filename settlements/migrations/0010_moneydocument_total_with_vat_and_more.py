# Generated by Django 5.1.7 on 2025-05-08 22:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settlements', '0009_moneydocument_customer'),
    ]

    operations = [
        migrations.AddField(
            model_name='moneydocument',
            name='total_with_vat',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='moneydocument',
            name='total_without_vat',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='moneydocument',
            name='vat_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
