# Generated by Django 5.1.7 on 2025-05-02 13:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('settlements', '0002_alter_moneyoperation_account'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='moneyoperation',
            name='document',
        ),
    ]
