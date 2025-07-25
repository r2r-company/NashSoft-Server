# backend/test_finance.py - ПРОСТИЙ ТЕСТ

from django.test import TestCase
from decimal import Decimal
from .models import Company


class SimpleFinanceTestCase(TestCase):
    """Прості тести фінансового модуля"""

    def test_company_creation(self):
        """Тест створення компанії"""
        company = Company.objects.create(name='Тестова компанія')
        self.assertEqual(company.name, 'Тестова компанія')

    def test_decimal_calculations(self):
        """Тест розрахунків з Decimal"""
        amount1 = Decimal('1000.50')
        amount2 = Decimal('500.25')
        result = amount1 + amount2

        self.assertEqual(result, Decimal('1500.75'))

    def test_percentage_calculation(self):
        """Тест розрахунку відсотків"""
        principal = Decimal('10000.00')
        rate = Decimal('0.05')  # 5%
        result = principal * rate

        self.assertEqual(result, Decimal('500.00'))

    def test_vat_calculation(self):
        """Тест розрахунку ПДВ"""
        price_without_vat = Decimal('1000.00')
        vat_rate = Decimal('0.20')  # 20%
        vat_amount = price_without_vat * vat_rate
        price_with_vat = price_without_vat + vat_amount

        self.assertEqual(vat_amount, Decimal('200.00'))
        self.assertEqual(price_with_vat, Decimal('1200.00'))