from django.urls import path
from .views import InvoiceUploadView, InvoiceListView

urlpatterns = [
    path("invoices/upload/", InvoiceUploadView.as_view(), name="invoice-upload"),
    path("invoices/", InvoiceListView.as_view(), name="invoice-list"),
]