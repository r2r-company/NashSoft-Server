# production/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # Базові ViewSets
    ProductionLineViewSet, WorkCenterViewSet, EquipmentViewSet,
    WorkerPositionViewSet, ProductionWorkerViewSet, WorkShiftViewSet,
    ProductionPlanViewSet, ProductionPlanItemViewSet, ProductionOrderViewSet,

    # Базові API Views
    ProductionDashboardView, ProductionReportsView,
    MaterialsRequirementView, ProductionCalendarView, QuickActionsView, MaintenanceViewSet, QualityControlViewSet,
    WasteManagementViewSet, WorkTimeNormViewSet
)

# Нові ViewSets для розширеного функціоналу


# Router для ViewSets
router = DefaultRouter()

# ========== БАЗОВА ІНФРАСТРУКТУРА ==========
router.register(r'production-lines', ProductionLineViewSet, basename='production-lines')
router.register(r'work-centers', WorkCenterViewSet, basename='work-centers')
router.register(r'equipment', EquipmentViewSet, basename='equipment')

# ========== ПРАЦІВНИКИ ==========
router.register(r'worker-positions', WorkerPositionViewSet, basename='worker-positions')
router.register(r'production-workers', ProductionWorkerViewSet, basename='production-workers')
router.register(r'work-shifts', WorkShiftViewSet, basename='work-shifts')

# ========== ПЛАНУВАННЯ ТА ВИРОБНИЦТВО ==========
router.register(r'production-plans', ProductionPlanViewSet, basename='production-plans')
router.register(r'production-plan-items', ProductionPlanItemViewSet, basename='production-plan-items')
router.register(r'production-orders', ProductionOrderViewSet, basename='production-orders')

# ========== НОВИЙ ФУНКЦІОНАЛ ==========
# Технічне обслуговування
router.register(r'maintenance', MaintenanceViewSet, basename='maintenance')
router.register(r'maintenance-types', MaintenanceViewSet, basename='maintenance-types')

# Контроль якості
router.register(r'quality-control', QualityControlViewSet, basename='quality-control')
router.register(r'quality-checkpoints', QualityControlViewSet, basename='quality-checkpoints')

# Управління браком та відходами
router.register(r'waste-management', WasteManagementViewSet, basename='waste-management')
router.register(r'waste-types', WasteManagementViewSet, basename='waste-types')

# Норми робочого часу
router.register(r'work-time-norms', WorkTimeNormViewSet, basename='work-time-norms')

# URL patterns
urlpatterns = [
    # ViewSets через router
    path('api/', include(router.urls)),

    # ========== БАЗОВІ API ENDPOINTS ==========
    path('api/dashboard/', ProductionDashboardView.as_view(), name='production-dashboard'),
    path('api/reports/', ProductionReportsView.as_view(), name='production-reports'),
    path('api/materials-requirement/', MaterialsRequirementView.as_view(), name='materials-requirement'),
    path('api/calendar/', ProductionCalendarView.as_view(), name='production-calendar'),
    path('api/quick-actions/', QuickActionsView.as_view(), name='quick-actions'),

    # ========== АНАЛІТИКА ТА ЗВІТНІСТЬ ==========
    # Тимчасово коментуємо до створення правильного класу
    # path('api/analytics/comprehensive-report/',
    #      ProductionAnalyticsView.as_view(),
    #      name='comprehensive-report'),
    # path('api/analytics/line-efficiency/',
    #      ProductionAnalyticsView.as_view(),
    #      name='line-efficiency'),

    # ========== ТЕХНІЧНЕ ОБСЛУГОВУВАННЯ ==========
    # Автоматично включені через router:
    # GET    /production/api/maintenance/                     - Список ТО
    # POST   /production/api/maintenance/                     - Створити ТО
    # GET    /production/api/maintenance/{id}/                - Деталі ТО
    # PUT    /production/api/maintenance/{id}/                - Оновити ТО
    # DELETE /production/api/maintenance/{id}/                - Видалити ТО

    # Додаткові дії:
    # GET    /production/api/maintenance/overdue/             - Прострочені ТО
    # GET    /production/api/maintenance/upcoming/            - Найближчі ТО
    # POST   /production/api/maintenance/{id}/start/          - Початок ТО
    # POST   /production/api/maintenance/{id}/complete/       - Завершення ТО
    # POST   /production/api/maintenance/{id}/cancel/         - Скасування ТО

    # ========== КОНТРОЛЬ ЯКОСТІ ==========
    # Автоматично включені через router:
    # GET    /production/api/quality-control/                 - Список перевірок
    # POST   /production/api/quality-control/                 - Створити перевірку
    # GET    /production/api/quality-control/{id}/            - Деталі перевірки

    # Додаткові дії:
    # POST   /production/api/quality-control/perform_check/   - Виконати контроль
    # GET    /production/api/quality-control/summary/         - Зведення по якості
    # GET    /production/api/quality-control/checkpoints/     - Контрольні точки

    # ========== УПРАВЛІННЯ БРАКОМ ==========
    # Автоматично включені через router:
    # GET    /production/api/waste-management/                - Список браку/відходів
    # POST   /production/api/waste-management/                - Створити запис
    # GET    /production/api/waste-management/{id}/           - Деталі запису

    # Додаткові дії:
    # POST   /production/api/waste-management/register/       - Зареєструвати брак
    # POST   /production/api/waste-management/{id}/attempt_recovery/ - Спроба відновлення
    # GET    /production/api/waste-management/analytics/      - Аналітика браку

    # ========== НОРМИ РОБОЧОГО ЧАСУ ==========
    # Автоматично включені через router:
    # GET    /production/api/work-time-norms/                 - Список норм
    # POST   /production/api/work-time-norms/                 - Створити норму
    # GET    /production/api/work-time-norms/{id}/            - Деталі норми

    # Додаткові дії:
    # POST   /production/api/work-time-norms/create_norm/     - Створити норму часу
    # POST   /production/api/work-time-norms/calculate_schedule/ - Розрахунок графіку
    # GET    /production/api/work-time-norms/optimization/    - Оптимізація послідовності
]

# ========== ПРИКЛАДИ ВИКОРИСТАННЯ API ==========

"""
🏭 БАЗОВИЙ ФУНКЦІОНАЛ:

📊 ДЕШБОРД:
GET /production/api/dashboard/?company=1&firm=1

📋 ВИРОБНИЧІ ЛІНІЇ:
GET /production/api/production-lines/?company=1
POST /production/api/production-lines/
GET /production/api/production-lines/1/workload/?date_from=2025-01-01&date_to=2025-01-31

📅 ПЛАНИ ВИРОБНИЦТВА:
GET /production/api/production-plans/?company=1&status=approved
POST /production/api/production-plans/
POST /production/api/production-plans/1/actions/  # {"action": "approve"}

🏭 ВИРОБНИЧІ ЗАМОВЛЕННЯ:
GET /production/api/production-orders/?company=1&status=in_progress
POST /production/api/production-orders/
POST /production/api/production-orders/1/actions/  # {"action": "start"}

📦 ПОТРЕБИ У МАТЕРІАЛАХ:
GET /production/api/materials-requirement/?company=1&firm=1&date_from=2025-01-01&date_to=2025-01-31

📅 КАЛЕНДАР ВИРОБНИЦТВА:
GET /production/api/calendar/?company=1&date_from=2025-01-20&date_to=2025-01-26

⚡ ШВИДКІ ДІЇ:
POST /production/api/quick-actions/

═══════════════════════════════════════════════════════════════════

🔧 НОВИЙ ФУНКЦІОНАЛ:

🔧 ТЕХНІЧНЕ ОБСЛУГОВУВАННЯ:

# Список всіх ТО
GET /production/api/maintenance/?company=1&status=scheduled&production_line=1

# Прострочені ТО
GET /production/api/maintenance/overdue/?company=1

# Найближчі ТО (на 7 днів)
GET /production/api/maintenance/upcoming/?company=1&days=7

# Створення планового ТО
POST /production/api/maintenance/
{
    "production_line": 1,
    "maintenance_type": 1,
    "scheduled_date": "2025-01-25T10:00:00Z",
    "assigned_to": 5
}

# Початок виконання ТО
POST /production/api/maintenance/1/start/

# Завершення ТО
POST /production/api/maintenance/1/complete/
{
    "actual_cost": 500.00,
    "completion_notes": "Замінено фільтри, налаштовано швидкість"
}

🔍 КОНТРОЛЬ ЯКОСТІ:

# Список перевірок якості
GET /production/api/quality-control/?production_order=1&status=fail

# Виконання контролю якості
POST /production/api/quality-control/perform_check/
{
    "production_order": 1,
    "checkpoint": 1,
    "checked_quantity": 100,
    "passed_quantity": 98,
    "measured_value": 99.5,
    "notes": "Незначні відхилення в межах норми"
}

# Зведення по якості
GET /production/api/quality-control/summary/?production_line=1&date_from=2025-01-01&date_to=2025-01-31

♻️ УПРАВЛІННЯ БРАКОМ:

# Список браку та відходів
GET /production/api/waste-management/?production_line=1&waste_type=defect&cause_category=equipment

# Реєстрація браку
POST /production/api/waste-management/register/
{
    "production_order": 1,
    "waste_type": 1,
    "quantity": 5,
    "unit_cost": 25.00,
    "cause_category": "equipment",
    "cause_description": "Збій налаштувань пакувальної машини",
    "work_center": 1
}

# Спроба відновлення браку
POST /production/api/waste-management/1/attempt_recovery/
{
    "recovery_cost": 50.00,
    "action_taken": "Переробка через ручне сортування"
}

# Аналітика браку
GET /production/api/waste-management/analytics/?company=1&date_from=2025-01-01&date_to=2025-01-31

⏱️ НОРМИ РОБОЧОГО ЧАСУ:

# Список норм часу
GET /production/api/work-time-norms/?production_line=1&is_active=true

# Створення норми часу
POST /production/api/work-time-norms/create_norm/
{
    "production_line": 1,
    "product": 1,
    "setup_time_minutes": 30,
    "cycle_time_seconds": 45,
    "cleanup_time_minutes": 15,
    "efficiency_factor": 0.85,
    "quality_factor": 0.95
}

# Розрахунок графіку виробництва
POST /production/api/work-time-norms/calculate_schedule/
{
    "order_ids": [1, 2, 3, 4]
}

📊 РОЗШИРЕНА АНАЛІТИКА:

# Комплексний звіт
GET /production/api/analytics/comprehensive-report/?company=1&date_from=2025-01-01&date_to=2025-01-31

# Ефективність ліній
GET /production/api/analytics/line-efficiency/?company=1&days=30

# OEE звіт (Overall Equipment Effectiveness)
GET /production/api/analytics/oee-report/?company=1&production_line=1&days=30

# Тренди якості
GET /production/api/analytics/quality-trends/?company=1&date_from=2025-01-01&date_to=2025-01-31

# Тренди браку
GET /production/api/analytics/waste-trends/?company=1&date_from=2025-01-01&date_to=2025-01-31

═══════════════════════════════════════════════════════════════════

🔥 ІНТЕГРАЦІЇ:

# Інтеграція з основним складським обліком
GET /api/products/1/production-readiness/  # Готовність сировини
POST /api/documents/  # Автоматичне списання сировини при запуску ВЗ

# Інтеграція з фінансами
GET /api/money/production-costs/?production_order=1  # Витрати на виробництво
POST /api/money/production-payment/  # Оплата за виконані роботи

# Інтеграція з HR
GET /api/production-workers/1/performance/  # Продуктивність працівника
POST /api/work-shifts/1/attendance/  # Облік робочого часу
"""