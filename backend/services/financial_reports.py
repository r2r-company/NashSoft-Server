# backend/services/financial_reports.py - НОВИЙ ФАЙЛ

from django.db.models import Sum, Q
from decimal import Decimal
from datetime import date

from backend.models import ChartOfAccounts, AccountingEntry


class FinancialReportsService:
    """Сервіс фінансових звітів"""

    @staticmethod
    def get_trial_balance(company, date_to=None):
        """Оборотно-сальдова відомість"""
        if not date_to:
            date_to = date.today()

        accounts = ChartOfAccounts.objects.filter(is_active=True).order_by('code')
        balance_data = []

        for account in accounts:
            # Обороти по дебету
            debit_turnover = AccountingEntry.objects.filter(
                debit_account=account,
                date__lte=date_to
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            # Обороти по кредиту
            credit_turnover = AccountingEntry.objects.filter(
                credit_account=account,
                date__lte=date_to
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            # Сальдо
            balance = debit_turnover - credit_turnover

            if debit_turnover > 0 or credit_turnover > 0 or balance != 0:
                balance_data.append({
                    'account_code': account.code,
                    'account_name': account.name,
                    'account_type': account.account_type,
                    'debit_turnover': debit_turnover,
                    'credit_turnover': credit_turnover,
                    'balance': balance,
                    'debit_balance': balance if balance > 0 else Decimal('0'),
                    'credit_balance': abs(balance) if balance < 0 else Decimal('0')
                })

        return balance_data

    @staticmethod
    def get_balance_sheet(company, date_to=None):
        """Баланс підприємства"""
        if not date_to:
            date_to = date.today()

        trial_balance = FinancialReportsService.get_trial_balance(company, date_to)

        assets = []
        liabilities = []
        equity = []

        for item in trial_balance:
            account_type = item['account_type']

            if account_type == 'asset':
                assets.append(item)
            elif account_type == 'liability':
                liabilities.append(item)
            elif account_type == 'equity':
                equity.append(item)

        total_assets = sum(item['debit_balance'] for item in assets)
        total_liabilities = sum(item['credit_balance'] for item in liabilities)
        total_equity = sum(item['credit_balance'] for item in equity)

        return {
            'date': date_to,
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'balance_check': total_assets == (total_liabilities + total_equity)
        }

    @staticmethod
    def get_profit_loss(company, date_from, date_to):
        """Звіт про прибутки та збитки"""
        revenue_accounts = ChartOfAccounts.objects.filter(account_type='revenue')
        expense_accounts = ChartOfAccounts.objects.filter(account_type='expense')

        revenues = []
        expenses = []

        for account in revenue_accounts:
            credit_sum = AccountingEntry.objects.filter(
                credit_account=account,
                date__range=[date_from, date_to]
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            debit_sum = AccountingEntry.objects.filter(
                debit_account=account,
                date__range=[date_from, date_to]
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            net_revenue = credit_sum - debit_sum

            if net_revenue != 0:
                revenues.append({
                    'account_code': account.code,
                    'account_name': account.name,
                    'amount': net_revenue
                })

        for account in expense_accounts:
            debit_sum = AccountingEntry.objects.filter(
                debit_account=account,
                date__range=[date_from, date_to]
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            credit_sum = AccountingEntry.objects.filter(
                credit_account=account,
                date__range=[date_from, date_to]
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            net_expense = debit_sum - credit_sum

            if net_expense != 0:
                expenses.append({
                    'account_code': account.code,
                    'account_name': account.name,
                    'amount': net_expense
                })

        total_revenue = sum(item['amount'] for item in revenues)
        total_expenses = sum(item['amount'] for item in expenses)
        net_profit = total_revenue - total_expenses

        return {
            'period': {'from': date_from, 'to': date_to},
            'revenues': revenues,
            'expenses': expenses,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_profit': net_profit
        }