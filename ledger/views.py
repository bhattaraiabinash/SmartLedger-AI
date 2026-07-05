from rest_framework import generics, permissions
from .models import Invoice
from .serializers import InvoiceUploadSerializer


class InvoiceUploadView(generics.CreateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceUploadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user, status="pending")


class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceUploadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Invoice.objects.filter(uploaded_by=self.request.user)