# v1.0.0
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from expense.models import ExpenseRecord


class Vehicle(models.Model):
    """A vehicle owned by the user. Battery capacity drives every kWh figure."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="vehicles",
    )
    brand = models.CharField(max_length=100)
    plate_number = models.CharField(max_length=20, blank=True, default="")
    color = models.CharField(max_length=50, blank=True, default="")
    battery_capacity_kwh = models.DecimalField(
        max_digits=6, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ev_vehicle"
        ordering = ["brand", "plate_number", "id"]

    def __str__(self):
        if self.plate_number:
            return "%s (%s)" % (self.brand, self.plate_number)
        return self.brand

    @property
    def display_name(self):
        return str(self)


class ChargingRecord(models.Model):
    """One charging session.

    ``battery_capacity_kwh`` is snapshotted from the vehicle at save time so
    that correcting a vehicle's capacity later never re-prices past sessions.
    ``total_kwh`` and ``total_price`` are computed in services.py, never by
    the client.
    """

    CHARGER_AC = "AC"
    CHARGER_DC = "DC"
    CHARGER_TYPE_CHOICES = [
        (CHARGER_AC, "AC"),
        (CHARGER_DC, "DC"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="charging_records",
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="charging_records",
    )
    charger_type = models.CharField(
        max_length=2, choices=CHARGER_TYPE_CHOICES, default=CHARGER_AC,
    )
    charge_date = models.DateField(db_index=True)
    location = models.CharField(max_length=255, blank=True, default="")

    start_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0")),
                    MaxValueValidator(Decimal("100"))],
    )
    end_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0")),
                    MaxValueValidator(Decimal("100"))],
    )
    price_per_kwh = models.DecimalField(
        max_digits=8, decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )

    # snapshot of vehicle.battery_capacity_kwh at the time of the session
    battery_capacity_kwh = models.DecimalField(max_digits=6, decimal_places=2)

    total_kwh = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    expense_record = models.OneToOneField(
        ExpenseRecord, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="charging_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ev_charging_record"
        ordering = ["-charge_date", "-created_at"]

    def __str__(self):
        return "%s - %s - %s kWh" % (
            self.charge_date, self.vehicle.brand, self.total_kwh,
        )
