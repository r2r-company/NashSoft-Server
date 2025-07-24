# backend/admin/admin_group_titles.py - ПРОСТА РЕОРГАНІЗАЦІЯ

GROUP_TITLES = {
    # 🏢 ОСНОВА (найважливіше для роботи)
    "Company": "🏢 Компанії та фірми",
    "Firm": "🏢 Компанії та фірми",
    "Warehouse": "🏢 Компанії та фірми",
    "Department": "🏢 Компанії та фірми",
    "TradePoint": "🏢 Компанії та фірми",

    # 📦 ТОВАРИ (щоденна робота)
    "Product": "📦 Товари та склад",
    "ProductGroup": "📦 Товари та склад",
    "ProductCalculation": "📦 Товари та склад",
    "ProductCalculationItem": "📦 Товари та склад",
    "Unit": "📦 Товари та склад",
    "ProductUnitConversion": "📦 Товари та склад",

    # 🧾 ДОКУМЕНТИ (основні операції)
    "Document": "🧾 Документи та операції",
    "DocumentItem": "🧾 Документи та операції",
    "Operation": "🧾 Документи та операції",

    # 👥 КОНТРАГЕНТИ
    "Customer": "👥 Клієнти та постачальники",
    "Supplier": "👥 Клієнти та постачальники",
    "CustomerType": "👥 Клієнти та постачальники",
    "Contract": "👥 Клієнти та постачальники",

    # 💰 ЦІНИ
    "PriceType": "💰 Ціни та знижки",
    "PriceSettingDocument": "💰 Ціни та знижки",
    "DiscountRule": "💰 Ціни та знижки",

    # 💵 ФІНАНСИ
    "Account": "💵 Каса та банк",
    "MoneyDocument": "💵 Каса та банк",
    "MoneyOperation": "💵 Каса та банк",
    "MoneyLedgerEntry": "💵 Каса та банк",

    # 🖨️ КАСИ
    "CashRegister": "🖨️ Касові апарати",
    "CashShift": "🖨️ Касові апарати",
    "CashSession": "🖨️ Касові апарати",
    "FiscalReceipt": "🖨️ Касові апарати",
    "ReceiptOperation": "🖨️ Касові апарати",
    "CashWorkstation": "🖨️ Касові апарати",
    "VchasnoDevice": "🖨️ Касові апарати",
    "VchasnoCashier": "🖨️ Касові апарати",
    "VchasnoShift": "🖨️ Касові апарати",

    # 🏭 ВИРОБНИЦТВО (весь новий модуль)
    "ProductionLine": "🏭 Виробництво",
    "WorkCenter": "🏭 Виробництво",
    "Equipment": "🏭 Виробництво",
    "ProductionPlan": "🏭 Виробництво",
    "ProductionPlanItem": "🏭 Виробництво",
    "ProductionOrder": "🏭 Виробництво",
    "WorkerPosition": "🏭 Виробництво",
    "ProductionWorker": "🏭 Виробництво",
    "WorkShift": "🏭 Виробництво",

    # 👨‍💻 КОРИСТУВАЧІ
    "AppUser": "👨‍💻 Користувачі та права",
    "Interface": "👨‍💻 Користувачі та права",

    # ⚙️ НАЛАШТУВАННЯ (ховаємо внизу)
    "AccountingSettings": "⚙️ Налаштування",
    "DocumentSettings": "⚙️ Налаштування",
    "PaymentType": "⚙️ Налаштування",
    "DepartmentWarehouseAccess": "⚙️ Налаштування",

    # 📊 ЛОГИ (для техніків)
    "AuditLog": "📊 Логи системи",
}