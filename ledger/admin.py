from django.contrib import admin
from .models import Vendor, Invoice, InvoiceLineItem

admin.site.register(Vendor)
admin.site.register(Invoice)
admin.site.register(InvoiceLineItem)