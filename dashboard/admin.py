from django.contrib import admin
from django.db import models  # Import models here
from django.shortcuts import redirect

# Correct inheritance: models.Model
class DashboardLink(models.Model):
    class Meta:
        verbose_name_plural = 'Custom Dashboard'
        managed = False  # Tells Django not to create a database table

@admin.register(DashboardLink)
class DashboardLinkAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): 
        return False
        
    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirects immediately when you click the link in the sidebar
        return redirect('custom_dashboard')