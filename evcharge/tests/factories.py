# v1.0.0
"""Small helpers shared across the evcharge test modules."""
from datetime import date
from decimal import Decimal

from evcharge.models import Vehicle, ChargingRecord
from evcharge import services


def make_vehicle(user, brand="Tesla", capacity="75.00", plate="1AA-1234",
                 color="White", is_active=True):
    return Vehicle.objects.create(
        user=user, brand=brand, plate_number=plate, color=color,
        battery_capacity_kwh=Decimal(capacity), is_active=is_active,
    )


def make_charge(user, vehicle, start="20", end="80", price="0.2500",
                on=None, charger_type=ChargingRecord.CHARGER_AC,
                location="Toul Kork"):
    record = ChargingRecord(
        user=user,
        vehicle=vehicle,
        charger_type=charger_type,
        charge_date=on or date(2026, 3, 15),
        location=location,
        start_percent=Decimal(start),
        end_percent=Decimal(end),
        price_per_kwh=Decimal(price),
    )
    return services.save_charging_record(record)


MAR = date(2026, 3, 15)
APR = date(2026, 4, 2)
