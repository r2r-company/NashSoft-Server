# production/tests.py - СТВОРИ ФАЙЛ

from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal

from backend.models import Company, Firm, Warehouse
from .models import ProductionLine, MaintenanceType

User = get_user_model()


class ProductionTestCase(TestCase):
    """Тести виробничого модуля"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')
        self.company = Company.objects.create(name='Тестова компанія')
        self.firm = Firm.objects.create(name='Тестова фірма', company=self.company)
        self.warehouse = Warehouse.objects.create(name='Тестовий склад', company=self.company)

    def test_production_line_creation(self):
        """Тест створення виробничої лінії"""
        line = ProductionLine.objects.create(
            company=self.company,
            firm=self.firm,
            name='Тестова лінія',
            code='TEST001',
            capacity_per_hour=100,
            warehouse=self.warehouse
        )

        self.assertEqual(line.name, 'Тестова лінія')
        self.assertEqual(line.code, 'TEST001')
        self.assertTrue(line.is_active)

    def test_maintenance_type_creation(self):
        """Тест створення типу ТО"""
        maintenance_type = MaintenanceType.objects.create(
            name='Щомісячне ТО',
            frequency_type='days',
            frequency_value=30,
            duration_hours=Decimal('4.0')
        )

        self.assertEqual(maintenance_type.name, 'Щомісячне ТО')
        self.assertTrue(maintenance_type.is_active)