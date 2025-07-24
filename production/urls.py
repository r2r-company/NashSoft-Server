# production/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # ViewSets
    ProductionLineViewSet, WorkCenterViewSet, EquipmentViewSet,
    WorkerPositionViewSet, ProductionWorkerViewSet, WorkShiftViewSet,
    ProductionPlanViewSet, ProductionPlanItemViewSet, ProductionOrderViewSet,

    # API Views
    ProductionDashboardView, ProductionReportsView,
    MaterialsRequirementView, ProductionCalendarView, QuickActionsView
)

# Router для ViewSets
router = DefaultRouter()

# Інфраструктура
router.register(r'production-lines', ProductionLineViewSet, basename='production-lines')
router.register(r'work-centers', WorkCenterViewSet, basename='work-centers')
router.register(r'equipment', EquipmentViewSet, basename='equipment')

# Працівники
router.register(r'worker-positions', WorkerPositionViewSet, basename='worker-positions')
router.register(r'production-workers', ProductionWorkerViewSet, basename='production-workers')
router.register(r'work-shifts', WorkShiftViewSet, basename='work-shifts')

# Планування та виробництво
router.register(r'production-plans', ProductionPlanViewSet, basename='production-plans')
router.register(r'production-plan-items', ProductionPlanItemViewSet, basename='production-plan-items')
router.register(r'production-orders', ProductionOrderViewSet, basename='production-orders')

# URL patterns
urlpatterns = [
    # ViewSets через router
    path('api/', include(router.urls)),

    # Окремі API endpoints
    path('api/dashboard/', ProductionDashboardView.as_view(), name='production-dashboard'),
    path('api/reports/', ProductionReportsView.as_view(), name='production-reports'),
    path('api/materials-requirement/', MaterialsRequirementView.as_view(), name='materials-requirement'),
    path('api/calendar/', ProductionCalendarView.as_view(), name='production-calendar'),
    path('api/quick-actions/', QuickActionsView.as_view(), name='quick-actions'),
]

# ✅ ПРИКЛАДИ ВИКОРИСТАННЯ API:

"""
🔗 ОСНОВНІ ENDPOINTS:

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
GET /production/api/production-orders/1/materials/

📦 ПОТРЕБИ У МАТЕРІАЛАХ:
GET /production/api/materials-requirement/?company=1&firm=1&date_from=2025-01-01&date_to=2025-01-31

📅 КАЛЕНДАР ВИРОБНИЦТВА:
GET /production/api/calendar/?company=1&date_from=2025-01-20&date_to=2025-01-26

📈 ЗВІТИ:
GET /production/api/reports/?type=efficiency&company=1&date_from=2025-01-01&date_to=2025-01-31

⚡ ШВИДКІ ДІЇ:
POST /production/api/quick-actions/
{
    "action": "create_urgent_order",
    "company": 1,
    "firm": 1,
    "recipe": 1,
    "quantity_ordered": 100,
    "production_line": 1,
    "source_warehouse": 1,
    "target_warehouse": 1
}

POST /production/api/quick-actions/
{
    "action": "emergency_stop",
    "production_line_id": 1,
    "reason": "Технічна несправність"
}

POST /production/api/quick-actions/
{
    "action": "quick_material_check",
    "product_ids": [1, 2, 3],
    "warehouse_id": 1,
    "firm_id": 1
}
"""