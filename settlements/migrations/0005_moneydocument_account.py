# Generated by Django 5.1.7 on 2025-05-02 15:57

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settlements', '0004_moneyoperation_document'),
    ]

    operations = [
        migrations.AddField(
            model_name='moneydocument',
            name='account',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='settlements.account', verbose_name='Рахунок'),
            preserve_default=False,
        ),
    ]
