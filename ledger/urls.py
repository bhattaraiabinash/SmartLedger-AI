from django.urls import path
from .views import (
    InvoiceUploadView, InvoiceListView,
    PendingReconciliationResultsView, ReconciliationResultDecisionView,
)


urlpatterns = [
    path("invoices/upload/", InvoiceUploadView.as_view(), name="invoice-upload"),
    path("invoices/", InvoiceListView.as_view(), name="invoice-list"),
    path("reconciliation/pending/", PendingReconciliationResultsView.as_view(), name="reconciliation-pending"),
    path("reconciliation/<uuid:pk>/decide/", ReconciliationResultDecisionView.as_view(), name="reconciliation-decide"),
]