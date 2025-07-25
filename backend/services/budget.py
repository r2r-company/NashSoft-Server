from django.db.models import Sum
from decimal import Decimal
from datetime import date

from backend.models import AccountingEntry, BudgetPeriod, BudgetLine


class BudgetService:
    """Сервіс бюджетування"""

    @staticmethod
    def get_budget_execution(budget_period):
        """Виконання бюджету"""
        lines = budget_period.lines.all()
        execution_data = []

        for line in lines:
            # Фактичні витрати/доходи
            actual = AccountingEntry.objects.filter(
                debit_account=line.account,
                date__range=[budget_period.start_date, budget_period.end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            if line.account.account_type == 'revenue':
                actual = AccountingEntry.objects.filter(
                    credit_account=line.account,
                    date__range=[budget_period.start_date, budget_period.end_date]
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            total_budget = line.get_total_budget()
            variance = actual - total_budget
            variance_percent = (variance / total_budget * 100) if total_budget > 0 else 0

            execution_data.append({
                'account': {
                    'code': line.account.code,
                    'name': line.account.name,
                    'type': line.account.account_type
                },
                'cost_center': line.cost_center.name if line.cost_center else None,
                'budget': total_budget,
                'actual': actual,
                'variance': variance,
                'variance_percent': round(variance_percent, 2),
                'execution_percent': round((actual / total_budget * 100), 2) if total_budget > 0 else 0
            })

        return execution_data

    @staticmethod
    def get_monthly_execution(budget_period, month, year):
        """Виконання бюджету за місяць"""
        from calendar import monthrange

        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])

        lines = budget_period.lines.all()
        monthly_data = []

        for line in lines:
            month_budget = line.get_month_budget(month)

            # Фактичні витрати за місяць
            actual = AccountingEntry.objects.filter(
                debit_account=line.account,
                date__range=[start_date, end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            if line.account.account_type == 'revenue':
                actual = AccountingEntry.objects.filter(
                    credit_account=line.account,
                    date__range=[start_date, end_date]
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            variance = actual - month_budget

            monthly_data.append({
                'account': line.account.name,
                'budget': month_budget,
                'actual': actual,
                'variance': variance,
                'status': 'over' if variance > 0 else 'under' if variance < 0 else 'on_target'
            })

        return {
            'period': f"{month:02d}.{year}",
            'lines': monthly_data
        }

    @staticmethod
    def copy_budget_from_previous(current_period, adjustment_percent=0):
        """Копіювання бюджету з попереднього періоду"""
        # Знаходимо попередній період
        previous_period = BudgetPeriod.objects.filter(
            company=current_period.company,
            end_date__lt=current_period.start_date
        ).order_by('-end_date').first()

        if not previous_period:
            return False

        # Копіюємо статті з коригуванням
        for prev_line in previous_period.lines.all():
            adjustment = Decimal(1 + adjustment_percent / 100)

            BudgetLine.objects.create(
                budget_period=current_period,
                account=prev_line.account,
                cost_center=prev_line.cost_center,
                jan=prev_line.jan * adjustment,
                feb=prev_line.feb * adjustment,
                mar=prev_line.mar * adjustment,
                apr=prev_line.apr * adjustment,
                may=prev_line.may * adjustment,
                jun=prev_line.jun * adjustment,
                jul=prev_line.jul * adjustment,
                aug=prev_line.aug * adjustment,
                sep=prev_line.sep * adjustment,
                oct=prev_line.oct * adjustment,
                nov=prev_line.nov * adjustment,
                dec=prev_line.dec * adjustment,
                notes=f"Скопійовано з {previous_period.name} з коригуванням {adjustment_percent}%"
            )

        return True