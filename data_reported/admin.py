from django.contrib import admin
from .models import ReportedData

@admin.register(ReportedData)
class ReportedDataAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'created_at', 'is_success')
    list_filter = ('is_success', 'created_at')
    search_fields = ('vehicle__registration_number', 'vehicle__imei')
    readonly_fields = ('created_at',)
