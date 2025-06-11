from collections import defaultdict
from settlements.models import MoneyLedgerEntry

def calculate_account_ledger_balance():
    balances = defaultdict(lambda: {"debit": 0, "credit": 0})

    for entry in MoneyLedgerEntry.objects.all():
        balances[entry.debit_account]["debit"] += float(entry.amount)
        balances[entry.credit_account]["credit"] += 0  # на випадок, якщо дебет і кредит збігаються
        balances[entry.credit_account]["credit"] += float(entry.amount)

    result = []
    for acc_code, data in balances.items():
        result.append({
            "account_code": acc_code,
            "debit": round(data["debit"], 2),
            "credit": round(data["credit"], 2),
            "balance": round(data["debit"] - data["credit"], 2),
        })

    return sorted(result, key=lambda x: x["account_code"])
