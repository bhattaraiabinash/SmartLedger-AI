from django.contrib import admin
from .models import (
    
Vendor, Invoice, InvoiceLineItem, Product, VendorProductPrice,
ReconciliationResult, ActionLog,

)
admin.site.register(Vendor)
admin.site.register(Invoice)
admin.site.register(InvoiceLineItem)
admin.site.register(Product)
admin.site.register(VendorProductPrice)
admin.site.register(ReconciliationResult)
admin.site.register(ActionLog)