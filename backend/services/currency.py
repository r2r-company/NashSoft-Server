# backend/services/currency.py - НОВИЙ ФАЙЛ

import requests
from decimal import Decimal
from django.utils import timezone

from backend.models import ExchangeRate, Currency
from settlements.models import Account


class CurrencyService:
    """Сервіс роботи з валютами"""

    @staticmethod
    def get_nbu_rates():
        """Завантаження курсів з НБУ"""
        try:
            url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
            response = requests.get(url, timeout=10)
            data = response.json()

            today = timezone.now().date()
            created_count = 0

            for rate_data in data:
                currency_code = rate_data['cc']
                rate = Decimal(str(rate_data['rate']))

                # Знаходимо або створюємо валюту
                currency, created = Currency.objects.get_or_create(
                    code=currency_code,
                    defaults={
                        'name': rate_data['txt'],
                        'symbol': currency_code
                    }
                )

                # Створюємо курс
                exchange_rate, created = ExchangeRate.objects.get_or_create(
                    currency=currency,
                    date=today,
                    defaults={
                        'rate': rate,
                        'source': 'nbu'
                    }
                )

                if created:
                    created_count += 1

            return {'success': True, 'created': created_count}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def convert_amount(amount, from_currency, to_currency, date=None):
        """Конвертація сум між валютами"""
        if not date:
            date = timezone.now().date()

        if from_currency == to_currency:
            return amount

        base_currency = Currency.objects.get(is_base=True)

        # Конвертуємо до базової валюти
        if from_currency != base_currency:
            from_rate = ExchangeRate.objects.filter(
                currency=from_currency,
                date__lte=date
            ).order_by('-date').first()

            if not from_rate:
                raise ValueError(f"Немає курсу для {from_currency.code}")

            amount_in_base = amount / from_rate.rate
        else:
            amount_in_base = amount

        # Конвертуємо до цільової валюти
        if to_currency != base_currency:
            to_rate = ExchangeRate.objects.filter(
                currency=to_currency,
                date__lte=date
            ).order_by('-date').first()

            if not to_rate:
                raise ValueError(f"Немає курсу для {to_currency.code}")

            result = amount_in_base * to_rate.rate
        else:
            result = amount_in_base

        return result.quantize(Decimal('0.01'))

    @staticmethod
    def revalue_accounts(date=None):
        """Переоцінка валютних рахунків"""
        if not date:
            date = timezone.now().date()


        base_currency = Currency.objects.get(is_base=True)

        revaluation_entries = []

        for account in Account.objects.filter(currency__is_base=False):
            # Поточний баланс в валюті рахунку
            current_balance = account.get_balance()

            if current_balance == 0:
                continue

            # Курс на дату переоцінки
            rate = ExchangeRate.objects.filter(
                currency=account.currency,
                date__lte=date
            ).order_by('-date').first()

            if not rate:
                continue

            # Новий баланс в базовій валюті
            new_balance_base = current_balance * rate.rate

            # Різниця від переоцінки
            # Тут потрібно порівняти з попереднім балансом в базовій валюті
            # і створити проводку на курсову різницю

        return revaluation_entries