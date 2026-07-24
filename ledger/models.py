import uuid
from django.db import models
from django.contrib.auth.models import User


class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    contact_email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    reorder_threshold = models.IntegerField(default=5)
    preferred_vendor = models.ForeignKey(
        Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"  
    
class VendorProductPrice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="product_prices")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="vendor_prices")
    last_price = models.DecimalField(max_digits=10, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)   

    class Meta:
        unique_together = ("vendor", "product")
        
        def __str__(self):
            return f"{self.vendor.name} -> {self.product.name}: {self.last_price}"
        

class Invoice(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("extracted", "Extracted"),
        ("reconciled", "Reconciled"),
        ("needs_approval", "Needs approval"),
        ("resolved", "Resolved"),
        ("failed", "Failed"),
    ]
    raw_extracted_text = models.TextField(blank=True, null=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invoices")
    file = models.FileField(upload_to="invoices/%Y/%m/")
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class InvoiceLineItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
    raw_item_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.raw_item_name} x{self.quantity}"   
    
class ReconciliationResult(models.Model):
    DECISION_CHOICES = [
        ("auto_resolved", "Auto-resolved"),
        ("needs_approval", "Needs approval"),
        ("unmatched", "Unmatched"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line_item = models.OneToOneField(
        InvoiceLineItem, on_delete=models.CASCADE, related_name="reconciliation_result"
    )
    matched_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    match_score = models.FloatField(default=0.0)
    expected_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_diff_ratio = models.FloatField(null=True, blank=True)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.line_item.raw_item_name}: {self.decision}"
    
class ActionLog(models.Model):
    ACTOR_CHOICES = [
        ("action_agent", "Action agent"),
        ("owner", "Owner"),
    ]
    ACTION_TYPE_CHOICES = [
        ("restock", "Restock"),
        ("reorder_suggested", "Reorder suggested"),
        ("vendor_alert_drafted", "Vendor alert drafted"),
        ("approved", "Owner approved"),
        ("rejected", "Owner rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reconciliation_result = models.ForeignKey(
        ReconciliationResult, on_delete=models.CASCADE, related_name="action_logs",
        null=True, blank=True,
    )
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    actor = models.CharField(max_length=30, choices=ACTOR_CHOICES)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.actor}] {self.action_type}"
    
        
    
    
