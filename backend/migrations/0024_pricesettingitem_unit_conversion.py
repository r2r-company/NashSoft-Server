# Generated by Django 5.1.7 on 2025-05-13 08:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0023_alter_pricesettingitem_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricesettingitem',
            name='unit_conversion',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, to='backend.productunitconversion'),
            preserve_default=False,
        ),
    ]
