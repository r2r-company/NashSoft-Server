from django.urls import path
from backend.views import (
    DocumentPostView, StockBalanceView, ProductOperationsDebugView, StockByWarehouseView,
    DocumentListView, DocumentActionGetView, TransferActionView, ReturnToSupplierActionView,
    ReturnFromClientActionView, SaleActionView, InventoryActionView, PriceSettingDocumentActionView,
    CreatePriceSettingDocumentView, PriceSettingDocumentListView, stock_report, WhoAmIView,
    CustomLoginView, DocumentDetailView, ProductListView, ProductDetailView, CompanyListView,
    WarehouseListView, CustomerListCreateView, SupplierListCreateView, ProductGroupTreeView,
    StockInActionView, UserListView, PaymentTypeListCreateView,
    DepartmentListView, AccountListView, TechCalculationAPIView, ProductGroupFlatView,
    PriceTypeListView, CompanyDetailView, FirmDetailView, VatTypeChoicesView,
    FirmListCreateView, WarehouseDetailView, WarehouseListCreateView, DepartmentDetailView, ProductGroupDetailView,
    ProductGroupListCreateView, UnitListCreateView, UnitDetailView, SupplierDetailView, CustomerDetailView,
    CustomerTypeListCreateView, CustomerTypeDetailView, AccountDetailView, PriceTypeListCreateView, PriceTypeDetailView,
    AppUserListCreateView, AppUserDetailView, InterfaceListCreateView, InterfaceDetailView, ProductTotalStockView,
    TradePointListCreateView, TradePointDetailView, ReceiptProductsView, ProductUnitConversionDetailView,
    ProductUnitConversionListCreateView, ProductConversionsByProductIdView, ConversionActionView, StockValueReportView,
    ProfitabilityReportView, inventory_in_action
)
from kkm.service.kkm.shift import ShiftStatusView, OpenShiftView, CloseShiftView
from kkm.views import PrintMultiFirmReceiptsView
from settlements.views import CreateManualPaymentView, MoneyDocumentActionView, PaySupplierDebtView
from vchasno_kasa.views import VchasnoSystemTaskView

urlpatterns = [
    # === Документи ===
    path('documents/', DocumentListView.as_view(), name='document_list'),  # GET
    path('document/', DocumentPostView.as_view(), name='document_post'),  # POST
    path('document/<int:doc_id>/', DocumentDetailView.as_view(), name='document_detail'),

    # === Дії над документами ===
    path('receipts/', DocumentActionGetView.as_view(), name='receipts_get_action'),
    path('transfer/', TransferActionView.as_view(), name='transfer_action'),
    path('return-to-supplier/', ReturnToSupplierActionView.as_view(), name='return_to_supplier_action'),
    path('return-from-client/', ReturnFromClientActionView.as_view(), name='return_from_client_action'),
    path('sale/', SaleActionView.as_view(), name='sale_action'),
    path('inventory/', InventoryActionView.as_view(), name='inventory_action'),
    path('stock-in/', StockInActionView.as_view(), name='stock_in_action'),

    # === Ціноутворення ===
    path('price-setting-document-action/', PriceSettingDocumentActionView.as_view(),
         name='price-setting-document-action'),
    path('create-price-setting-document/', CreatePriceSettingDocumentView.as_view(),
         name='create-price-setting-document'),
    path('price-setting-documents/', PriceSettingDocumentListView.as_view(), name='price-setting-documents-list'),

    # === Аналітика / залишки ===
    path('stock/', StockBalanceView.as_view(), name='stock_balance'),
    path('stock/warehouses/', StockByWarehouseView.as_view(), name='stock_by_warehouse'),
    path('debug/operations/<int:product_id>/', ProductOperationsDebugView.as_view(), name='product_operations_debug'),
    path('stock-report/', stock_report, name='stock_report'),

    # === Користувачі та логін ===
    path('login/', CustomLoginView.as_view(), name='custom_login'),
    path('whoami/', WhoAmIView.as_view(), name='whoami'),
    path('users/', UserListView.as_view(), name='user_list'),

    # === Довідники ===
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path("product-groups/create/", ProductGroupListCreateView.as_view()),  # POST, GET
    path("product-groups/<int:pk>/", ProductGroupDetailView.as_view()),  # GET, PUT, DELETE

    path('companies/', CompanyListView.as_view(), name='company_list'),
    path('companies/<int:pk>/', CompanyDetailView.as_view()),  # ← ось ця стрічка
    path('warehouses/', WarehouseListView.as_view(), name='warehouse_list'),
    path("warehouses/", WarehouseListCreateView.as_view()),
    path("warehouses/<int:pk>/", WarehouseDetailView.as_view()),
    path('customers/', CustomerListCreateView.as_view(), name='customer_list_create'),
    path('customers/<int:pk>/', CustomerDetailView.as_view(), name='customer_detail'),

    path("customer-types/", CustomerTypeListCreateView.as_view()),
    path("customer-types/<int:pk>/", CustomerTypeDetailView.as_view()),
    path('suppliers/', SupplierListCreateView.as_view(), name='supplier_list_create'),
    path('suppliers/<int:pk>/', SupplierDetailView.as_view(), name='supplier_detail'),

    path('product-groups/', ProductGroupTreeView.as_view(), name='product_group_tree'),
    path("product-groups/flat/", ProductGroupFlatView.as_view()),
    path('units/', UnitListCreateView.as_view(), name='unit_list_create'),
    path('units/<int:pk>/', UnitDetailView.as_view(), name='unit_detail'),
    path('payment-types/', PaymentTypeListCreateView.as_view(), name='payment_type_list_create'),

    path("firms/", FirmListCreateView.as_view(), name="firm-list"),
    path("firms/<int:pk>/", FirmDetailView.as_view(), name="firm-detail"),

    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path("departments/<int:pk>/", DepartmentDetailView.as_view()),

    path('accounts/', AccountListView.as_view(), name='account_list'),
    path('accounts/<int:pk>/', AccountDetailView.as_view(), name='account_detail'),

    path("price-types/", PriceTypeListView.as_view()),
    path('price-types/', PriceTypeListCreateView.as_view(), name='price_type_list_create'),
    path('price-types/<int:pk>/', PriceTypeDetailView.as_view(), name='price_type_detail'),

    # === Фінанси ===
    path('manual-payment/', CreateManualPaymentView.as_view(), name='manual_payment'),
    path('money/action/', MoneyDocumentActionView.as_view(), name='money_action'),
    path('pay-debt/', PaySupplierDebtView.as_view(), name='pay_debt'),
    path("system-users/", AppUserListCreateView.as_view(), name='app_user_list_create'),
    path("system-users/<int:pk>/", AppUserDetailView.as_view(), name='app_user_detail'),
    path("access-groups/", InterfaceListCreateView.as_view(), name='interface_list_create'),
    path("access-groups/<int:pk>/", InterfaceDetailView.as_view(), name='interface_detail'),

    # === Калькуляція ===
    path('tech-calc/', TechCalculationAPIView.as_view(), name='tech_calc'),

    # === KKM ===
    path('kkm/open-shift/', OpenShiftView.as_view(), name='open_shift'),
    path('kkm/close-shift/', CloseShiftView.as_view(), name='close_shift'),
    path('kkm/shift-status/', ShiftStatusView.as_view(), name='shift_status'),
    path('kkm/print-receipts/', PrintMultiFirmReceiptsView.as_view(), name='print_multi_receipts'),

    # === System tasks ===
    path('system-task/', VchasnoSystemTaskView.as_view(), name='vchasno_system_task'),

    path("vat-types/", VatTypeChoicesView.as_view(), name="vat_types"),
    path("stock/product/<int:product_id>/", ProductTotalStockView.as_view()),
    path('trade-points/', TradePointListCreateView.as_view(), name='trade_point_list_create'),
    path('trade-points/<int:pk>/', TradePointDetailView.as_view(), name='trade_point_detail'),
    path("receipt-products/", ReceiptProductsView.as_view()),
    path("unit-conversions/", ProductUnitConversionListCreateView.as_view(), name="unit_conversion_list_create"),
    path("unit-conversions/<int:pk>/", ProductUnitConversionDetailView.as_view(), name="unit_conversion_detail"),
    path("unit-conversions/by-product/<int:product_id>/", ProductConversionsByProductIdView.as_view(),
         name="unit_conversions_by_product"),
    path('conversion/', ConversionActionView.as_view(), name='conversion_action'),
    path('reports/profitability/', ProfitabilityReportView.as_view()),
    path('reports/stock-value/', StockValueReportView.as_view()),
    path('inventory_in/', inventory_in_action),

]
