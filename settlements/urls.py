from django.urls import path
from .views import (
    AccountListCreateView, ContractCreateView, ContractActionView, MoneyDocumentActionView, MoneyBalanceView,
    CreateManualPaymentView, SupplierBalanceView, SupplierDebtListView, SupplierAnalyticsView, MoneyLedgerEntryListView,
    MoneyDocumentListView, MoneyOperationListView, MoneyLedgerListView, VATReportView, VatObligationReportView,
    AccountLedgerBalanceView, ContractDetailView, ContractsBySupplierView, ContractListCreateView,
    ContractsByClientView,

)

urlpatterns = [
    # 🏦 Рахунки
    path('money/accounts/', AccountListCreateView.as_view(), name='account_list_create'),
    # 📄 Договори
    path('contracts/', ContractListCreateView.as_view(), name='contract_list_create'),
    path('contracts/<int:pk>/', ContractDetailView.as_view(), name='contract_detail'),
    path('contracts/action/', ContractActionView.as_view(), name='contract_action'),
    path('contracts/by-client/', ContractsByClientView.as_view(), name='contracts_by_client'),

    path('contracts/by-supplier/', ContractsBySupplierView.as_view(), name='contracts_by_supplier'),
    path('money/action/', MoneyDocumentActionView.as_view(), name='money_document_action'),
    path('money/balance/', MoneyBalanceView.as_view(), name='money_balance'),
    path('money/create-manual-payment/', CreateManualPaymentView.as_view(), name='create_manual_payment'),
    path('supplier-balance/', SupplierBalanceView.as_view()),
    path('supplier-debts/', SupplierDebtListView.as_view()),
    path('supplier-payments/', SupplierAnalyticsView.as_view()),
    path('ledger-entries/', MoneyLedgerEntryListView.as_view()),
    path("money-documents/", MoneyDocumentListView.as_view()),
    path("money-operations/", MoneyOperationListView.as_view()),
    path("money-ledger/", MoneyLedgerListView.as_view()),
    path("vat-report/", VATReportView.as_view()),
    path("vat-obligation-report/", VatObligationReportView.as_view()),
    path("account-ledger-balance/", AccountLedgerBalanceView.as_view(), name="account_ledger_balance"),


]
