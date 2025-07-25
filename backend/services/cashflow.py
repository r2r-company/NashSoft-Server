# backend/services/cashflow.py - НОВИЙ ФАЙЛ

from django.db.models import Sum, Q
from decimal import Decimal
from datetime import date, timedelta

from backend.models import CashFlowForecast, PaymentSchedule
from settlements.models import Account


class CashFlowService:
    """Сервіс аналізу грошових потоків"""

    @staticmethod
    def generate_forecast(company, days_ahead=90):
        """Генерація прогнозу на основі історичних даних"""
        end_date = date.today() + timedelta(days=days_ahead)

        # Очищуємо старі прогнози
        CashFlowForecast.objects.filter(
            company=company,
            forecast_date__gte=date.today(),
            is_actual=False
        ).delete()

        forecasts = []

        # Прогноз на основі дебіторської заборгованості
        receivables = PaymentSchedule.objects.filter(
            company=company,
            schedule_type='receivables',
            status='planned',
            due_date__lte=end_date
        )

        for receivable in receivables:
            CashFlowForecast.objects.create(
                company=company,
                account=company.accounts.filter(account_type='bank').first(),
                forecast_date=receivable.due_date,
                amount=receivable.amount - receivable.paid_amount,
                flow_type='inflow',
                category='receivables',
                description=f"Оплата від {receivable.counterparty_name}",
                probability=80,  # Дебіторка має ризик
                customer=receivable.customer
            )

        # Прогноз витрат на постачальників
        payables = PaymentSchedule.objects.filter(
            company=company,
            schedule_type='payables',
            status='planned',
            due_date__lte=end_date
        )

        for payable in payables:
            CashFlowForecast.objects.create(
                company=company,
                account=company.accounts.filter(account_type='bank').first(),
                forecast_date=payable.due_date,
                amount=payable.amount - payable.paid_amount,
                flow_type='outflow',
                category='suppliers',
                description=f"Оплата {payable.counterparty_name}",
                probability=95,  # Зобов'язання треба виконувати
                supplier=payable.supplier
            )

        return True

    @staticmethod
    def get_cashflow_report(company, date_from, date_to):
        """Звіт по грошових потоках"""
        accounts = Account.objects.filter(company=company)

        # Початкові залишки
        opening_balances = {}
        for account in accounts:
            opening_balances[account.id] = account.get_balance_on_date(date_from)

        # Надходження по днях
        daily_flows = {}
        current_date = date_from

        while current_date <= date_to:
            # Фактичні потоки
            inflows = CashFlowForecast.objects.filter(
                company=company,
                forecast_date=current_date,
                flow_type='inflow',
                is_actual=True
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            outflows = CashFlowForecast.objects.filter(
                company=company,
                forecast_date=current_date,
                flow_type='outflow',
                is_actual=True
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            # Прогнозні потоки
            forecast_inflows = CashFlowForecast.objects.filter(
                company=company,
                forecast_date=current_date,
                flow_type='inflow',
                is_actual=False
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            forecast_outflows = CashFlowForecast.objects.filter(
                company=company,
                forecast_date=current_date,
                flow_type='outflow',
                is_actual=False
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            daily_flows[current_date] = {
                'actual_inflows': inflows,
                'actual_outflows': outflows,
                'forecast_inflows': forecast_inflows,
                'forecast_outflows': forecast_outflows,
                'net_flow': inflows - outflows,
                'forecast_net_flow': forecast_inflows - forecast_outflows
            }

            current_date += timedelta(days=1)

        return {
            'period': {'from': date_from, 'to': date_to},
            'opening_balances': opening_balances,
            'daily_flows': daily_flows
        }

    @staticmethod
    def check_liquidity_risk(company, days_ahead=30):
        """Перевірка ризику ліквідності"""
        end_date = date.today() + timedelta(days=days_ahead)

        # Поточні залишки
        total_cash = Account.objects.filter(
            company=company,
            account_type__in=['cash', 'bank']
        ).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0')

        # Прогнозні витрати
        forecast_outflows = CashFlowForecast.objects.filter(
            company=company,
            forecast_date__range=[date.today(), end_date],
            flow_type='outflow'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

        # Прогнозні надходження
        forecast_inflows = CashFlowForecast.objects.filter(
            company=company,
            forecast_date__range=[date.today(), end_date],
            flow_type='inflow'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

        projected_balance = total_cash + forecast_inflows - forecast_outflows

        # Аналіз ризику
        risk_level = 'low'
        if projected_balance < 0:
            risk_level = 'critical'
        elif projected_balance < forecast_outflows * Decimal('0.1'):  # Менше 10% від витрат
            risk_level = 'high'
        elif projected_balance < forecast_outflows * Decimal('0.3'):  # Менше 30% від витрат
            risk_level = 'medium'

        return {
            'current_cash': total_cash,
            'forecast_inflows': forecast_inflows,
            'forecast_outflows': forecast_outflows,
            'projected_balance': projected_balance,
            'risk_level': risk_level,
            'days_of_coverage': int(total_cash / (forecast_outflows / days_ahead)) if forecast_outflows > 0 else 999
        }