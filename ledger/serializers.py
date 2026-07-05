from rest_framework import serializers
from .models import Invoice


class InvoiceUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "file", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]