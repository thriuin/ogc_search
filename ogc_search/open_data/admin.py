from django.contrib import admin
from .models import CatalogType

# Register your models here.
@admin.register(CatalogType)
class CatalogTYpeAdmin(admin.ModelAdmin):
    pass
