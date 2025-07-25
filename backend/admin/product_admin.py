from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline, ModelAdmin
from django.contrib import admin
from backend.models import Unit, ProductGroup, Product, ProductCalculation, ProductCalculationItem, DiscountRule, \
    ProductUnitConversion, PaymentType, PaymentSchedule, CashFlowForecast, BudgetLine, BudgetPeriod, ExchangeRate, \
    Currency, CostCenter, AccountingEntry, ChartOfAccounts
from production.models import MaintenanceType, MaintenanceSchedule, QualityCheckPoint, QualityCheck, WasteType, \
    WasteRecord, WorkTimeNorm


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    search_fields = ('name',)

@admin.register(ProductGroup)
class ProductGroupAdmin(ModelAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)

class ProductUnitConversionInline(TabularInline):
    model = ProductUnitConversion
    extra = 1
    autocomplete_fields = ['from_unit', 'to_unit']

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('id', 'name', 'type', 'firm', 'unit',  'group')
    list_filter = ('type', 'firm', 'group')
    search_fields = ('name',)
    inlines = [ProductUnitConversionInline]
    fieldsets = (
        (None, {
            'fields': (
                ('firm', 'name'),
                ('type', 'unit'),
            )
        }),
    )


class ProductCalculationItemInline(TabularInline):
    model = ProductCalculationItem
    extra = 1
    autocomplete_fields = ['component']
    fields = [
        'component', 'quantity', 'unit_conversion', 'loss_percent',
        'cooking_loss_percent', 'note'
    ]

    # ✅ ДОДАЄМО JAVASCRIPT ДЛЯ ФІЛЬТРАЦІЇ ФАСУВАНЬ
    class Media:
        js = ('admin/js/calculation_packaging.js',)


@admin.register(ProductCalculation)
class ProductCalculationAdmin(ModelAdmin):
    list_display = ['product', 'date', 'note', 'total_ingredients']
    list_filter = ['product__firm', 'product__type']
    search_fields = ['product__name', 'note']
    inlines = [ProductCalculationItemInline]

    def total_ingredients(self, obj):
        return obj.items.count()

    total_ingredients.short_description = 'Кількість інгредієнтів'

@admin.register(DiscountRule)
class DiscountRuleAdmin(ModelAdmin):
    list_display = ('name', 'percent', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    filter_horizontal = ('products', 'trade_points')
    search_fields = ('name',)



@admin.register(PaymentType)
class PaymentTypeAdmin(ModelAdmin):
    list_display = ['name']


@admin.register(MaintenanceType)
class MaintenanceTypeAdmin(ModelAdmin):
   list_display = ['name', 'frequency_type', 'frequency_value', 'duration_hours', 'estimated_cost', 'is_active']
   list_filter = ['frequency_type', 'is_active']
   search_fields = ['name', 'description']

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(ModelAdmin):
   list_display = ['production_line', 'maintenance_type', 'scheduled_date', 'status', 'assigned_to', 'actual_cost']
   list_filter = ['status', 'production_line', 'maintenance_type']
   search_fields = ['production_line__name', 'maintenance_type__name']
   date_hierarchy = 'scheduled_date'
   readonly_fields = ['created_at']

# ========== КОНТРОЛЬ ЯКОСТІ ==========

@admin.register(QualityCheckPoint)
class QualityCheckPointAdmin(ModelAdmin):
   list_display = ['name', 'production_line', 'check_type', 'check_frequency', 'acceptable_deviation', 'is_active']
   list_filter = ['check_type', 'check_frequency', 'production_line', 'is_active']
   search_fields = ['name', 'criteria']

@admin.register(QualityCheck)
class QualityCheckAdmin(ModelAdmin):
   list_display = ['production_order', 'checkpoint', 'check_date', 'checked_quantity', 'passed_quantity', 'status', 'inspector']
   list_filter = ['status', 'checkpoint', 'inspector']
   search_fields = ['production_order__order_number', 'checkpoint__name']
   date_hierarchy = 'check_date'

# ========== БРАК ТА ВІДХОДИ ==========

@admin.register(WasteType)
class WasteTypeAdmin(ModelAdmin):
   list_display = ['name', 'category', 'is_recoverable', 'recovery_cost_per_unit']
   list_filter = ['category', 'is_recoverable']
   search_fields = ['name', 'description']

@admin.register(WasteRecord)
class WasteRecordAdmin(ModelAdmin):
   list_display = ['production_order', 'waste_type', 'quantity', 'total_loss', 'cause_category', 'is_recovered', 'occurred_at']
   list_filter = ['waste_type__category', 'cause_category', 'is_recovered']
   search_fields = ['production_order__order_number', 'waste_type__name', 'cause_description']
   date_hierarchy = 'occurred_at'

# ========== НОРМИ ЧАСУ ==========

@admin.register(WorkTimeNorm)
class WorkTimeNormAdmin(ModelAdmin):
   list_display = ['production_line', 'product', 'cycle_time_seconds', 'efficiency_factor', 'is_active', 'valid_from']
   list_filter = ['production_line', 'is_active']
   search_fields = ['production_line__name', 'product__name']
   date_hierarchy = 'valid_from'


# ========== ПЛАН РАХУНКІВ ==========

@admin.register(ChartOfAccounts)
class ChartOfAccountsAdmin(ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'parent', 'is_active', 'is_analytic']
    list_filter = ['account_type', 'is_active', 'is_analytic']
    search_fields = ['code', 'name']
    ordering = ['code']
    list_editable = ['is_active']


@admin.register(AccountingEntry)
class AccountingEntryAdmin(ModelAdmin):
    list_display = ['date', 'debit_account', 'credit_account', 'amount', 'description', 'document']
    list_filter = ['date', 'debit_account__account_type', 'credit_account__account_type']
    search_fields = ['description', 'debit_account__name', 'credit_account__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']


# ========== ЦЕНТРИ ВИТРАТ ==========

@admin.register(CostCenter)
class CostCenterAdmin(ModelAdmin):
    list_display = ['code', 'name', 'center_type', 'company', 'monthly_budget', 'manager', 'is_active']
    list_filter = ['center_type', 'company', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['monthly_budget', 'is_active']


# ========== ВАЛЮТИ ==========

@admin.register(Currency)
class CurrencyAdmin(ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'is_base', 'is_active']
    list_filter = ['is_base', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['is_active']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(ModelAdmin):
    list_display = ['currency', 'date', 'rate', 'source', 'created_at']
    list_filter = ['currency', 'source', 'date']
    search_fields = ['currency__code']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']


# ========== БЮДЖЕТИ ==========

class BudgetLineInline(TabularInline):
    model = BudgetLine
    extra = 0
    fields = ['account', 'cost_center', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov',
              'dec']


@admin.register(BudgetPeriod)
class BudgetPeriodAdmin(ModelAdmin):
    list_display = ['name', 'company', 'start_date', 'end_date', 'status', 'created_by', 'approved_by']
    list_filter = ['status', 'company', 'start_date']
    search_fields = ['name']
    readonly_fields = ['approved_at']
    inlines = [BudgetLineInline]


@admin.register(BudgetLine)
class BudgetLineAdmin(ModelAdmin):
    list_display = ['budget_period', 'account', 'cost_center', 'get_total_budget']
    list_filter = ['budget_period', 'account__account_type']
    search_fields = ['account__name', 'cost_center__name']


# ========== CASHFLOW ==========

@admin.register(CashFlowForecast)
class CashFlowForecastAdmin(ModelAdmin):
    list_display = ['forecast_date', 'account', 'flow_type', 'category', 'amount', 'probability', 'is_actual']
    list_filter = ['flow_type', 'category', 'is_actual', 'account']
    search_fields = ['description']
    date_hierarchy = 'forecast_date'
    list_editable = ['probability', 'is_actual']


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(ModelAdmin):
    list_display = ['counterparty_name', 'schedule_type', 'amount', 'due_date', 'status', 'paid_amount']
    list_filter = ['schedule_type', 'status', 'due_date']
    search_fields = ['counterparty_name']
    date_hierarchy = 'due_date'
    list_editable = ['status', 'paid_amount']

    def get_list_display_links(self, request, list_display):
        return ['counterparty_name']