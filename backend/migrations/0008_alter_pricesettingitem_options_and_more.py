# Generated by Django 5.1.7 on 2025-05-09 20:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0007_alter_departmentwarehouseaccess_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='pricesettingitem',
            options={'ordering': ['order']},
        ),
        migrations.AddField(
            model_name='pricesettingitem',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
