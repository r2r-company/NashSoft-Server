# Generated by Django 5.1.7 on 2025-05-02 06:27

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('backend', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VchasnoCashier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cashier_id', models.CharField(max_length=100, verbose_name='ID касира (з Вчасно)')),
                ('name', models.CharField(max_length=100, verbose_name='Ім’я касира у Вчасно')),
                ('inn', models.CharField(max_length=20, verbose_name='ІПН')),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Користувач')),
            ],
            options={
                'verbose_name': 'Касир Вчасно',
                'verbose_name_plural': 'Касири Вчасно',
            },
        ),
        migrations.CreateModel(
            name='VchasnoDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Назва пристрою')),
                ('device_id', models.CharField(max_length=100, unique=True, verbose_name='ID пристрою (з Вчасно)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активний')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backend.company', verbose_name='Компанія')),
            ],
            options={
                'verbose_name': 'Пристрій Вчасно Каса',
                'verbose_name_plural': 'Пристрої Вчасно Каса',
            },
        ),
        migrations.CreateModel(
            name='VchasnoShift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shift_number', models.PositiveIntegerField()),
                ('opened_at', models.DateTimeField()),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('opened', 'Відкрита'), ('closed', 'Закрита')], default='opened', max_length=20)),
                ('cashier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vchasno_kasa.vchasnocashier')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vchasno_kasa.vchasnodevice')),
                ('trade_point', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='backend.tradepoint')),
            ],
            options={
                'verbose_name': 'Зміна Вчасно',
                'verbose_name_plural': 'Зміни Вчасно',
            },
        ),
    ]
