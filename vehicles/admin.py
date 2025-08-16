from django.contrib import admin
from .models import Vehicle, DeviceImei, Customer

@admin.register(DeviceImei)
class DeviceImeiAdmin(admin.ModelAdmin):
    list_display = ('imei_number', 'created_at', 'updated_at')
    search_fields = ('imei_number',)
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'get_imei_number', 'created_at')
    search_fields = ('registration_number', 'imei__imei_number')
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_imei_number(self, obj):
        return obj.imei.imei_number if obj.imei else None
    get_imei_number.short_description = 'IMEI Number'

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_imei_number(self, obj):
        return obj.imei.imei_number if obj.imei else None
    get_imei_number.short_description = 'IMEI Number'







