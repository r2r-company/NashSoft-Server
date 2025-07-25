# backend/services/cost_center.py - НОВИЙ ФАЙЛ

from django.db.models import Sum
from decimal import Decimal

from backend.models import CostCenter


class CostCenterService:
    """Сервіс управління центрами витрат"""

    @staticmethod
    def get_cost_analysis(company, date_from, date_to):
        """Аналіз витрат по центрах"""
        cost_centers = CostCenter.objects.filter(company=company, is_active=True)

        analysis = []
        total_actual = Decimal('0')
        total_budget = Decimal('0')

        for cc in cost_centers:
            actual_costs = cc.get_actual_costs(date_from, date_to)

            # Розрахунок бюджету за період
            months = (date_to.year - date_from.year) * 12 + (date_to.month - date_from.month) + 1
            period_budget = cc.monthly_budget * months

            variance = actual_costs - period_budget
            variance_percent = (variance / period_budget * 100) if period_budget > 0 else 0

            analysis.append({
                'cost_center': {
                    'code': cc.code,
                    'name': cc.name,
                    'type': cc.center_type,
                    'manager': cc.manager.username if cc.manager else None
                },
                'budget': period_budget,
                'actual': actual_costs,
                'variance': variance,
                'variance_percent': round(variance_percent, 2),
                'status': 'over_budget' if variance > 0 else 'under_budget'
            })

            total_actual += actual_costs
            total_budget += period_budget

        return {
            'period': {'from': date_from, 'to': date_to},
            'cost_centers': analysis,
            'totals': {
                'budget': total_budget,
                'actual': total_actual,
                'variance': total_actual - total_budget
            }
        }

    @staticmethod
    def allocate_expense(amount, description, expense_account, cost_centers_allocation):
        """Розподіл витрат по центрах"""
        # cost_centers_allocation = [{'cost_center': cc_id, 'percentage': 30}, ...]

        total_percentage = sum(item['percentage'] for item in cost_centers_allocation)
        if total_percentage != 100:
            raise ValueError("Сума відсотків повинна дорівнювати 100%")

        entries = []
        for allocation in cost_centers_allocation:
            cc = CostCenter.objects.get(id=allocation['cost_center'])
            allocated_amount = amount * Decimal(allocation['percentage']) / 100

            # Тут створюємо проводку з прив'язкою до центру витрат
            # entry = AccountingEntry.objects.create(...)
            # entry.cost_center = cc
            # entries.append(entry)

        return entries