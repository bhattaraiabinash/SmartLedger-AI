from django.contrib import admin
from .models import Vendor, Invoice

admin.site.register(Vendor)
admin.site.register(Invoice)