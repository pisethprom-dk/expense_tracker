# v1.0.0
from django.contrib import admin

from .models import Vehicle, ChargingRecord


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("brand", "plate_number", "color",
                    "battery_capacity_kwh", "is_active", "user")
    list_filter = ("is_active", "brand")
    search_fields = ("brand", "plate_number")


@admin.register(ChargingRecord)
class ChargingRecordAdmin(admin.ModelAdmin):
    list_display = ("charge_date", "vehicle", "charger_type", "location",
                    "start_percent", "end_percent",
                    "total_kwh", "price_per_kwh", "total_price")
    list_filter = ("charger_type", "charge_date")
    search_fields = ("location", "vehicle__brand", "vehicle__plate_number")
    readonly_fields = ("battery_capacity_kwh", "total_kwh",
                       "total_price", "expense_record")
