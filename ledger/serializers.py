from rest_framework import serializers
from .models import Invoice, ReconciliationResult


class InvoiceUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "file", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]
        
class ReconciliationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationResult
        fields = [
            "id", "line_item", "matched_product", "match_score",
            "expected_price", "actual_price", "price_diff_ratio",
            "decision", "reason", "created_at",
        ]        
        read_only_fields = fields