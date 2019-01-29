from django.contrib import admin
from .models import CatalogType, Organization, QueryLog

# Register your models here.
@admin.register(CatalogType)
class CatalogTypeAdmin(admin.ModelAdmin):
    pass

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    pass

@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    pass