# v1.0.0
from decimal import Decimal

from rest_framework import serializers

from .models import Vehicle, ChargingRecord


class VehicleSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id", "brand", "plate_number", "color",
            "battery_capacity_kwh", "is_active",
            "display_name", "created_at",
        ]
        read_only_fields = ["id", "display_name", "created_at"]

    def validate_battery_capacity_kwh(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Battery capacity must be greater than 0."
            )
        return value


class ChargingRecordSerializer(serializers.ModelSerializer):
    vehicle_name = serializers.CharField(
        source="vehicle.display_name", read_only=True
    )
    expense_record_id = serializers.IntegerField(
        source="expense_record.id", read_only=True, allow_null=True,
    )

    class Meta:
        model = ChargingRecord
        fields = [
            "id", "vehicle", "vehicle_name", "charger_type",
            "charge_date", "location",
            "start_percent", "end_percent", "price_per_kwh",
            "battery_capacity_kwh", "total_kwh", "total_price",
            "expense_record_id", "created_at",
        ]
        read_only_fields = [
            "id", "vehicle_name", "battery_capacity_kwh",
            "total_kwh", "total_price", "expense_record_id", "created_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        # a user may only charge their own vehicles
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            fields["vehicle"].queryset = Vehicle.objects.filter(user=request.user)
        # charge_date defaults to today in the view
        fields["charge_date"].required = False
        return fields

    def validate_price_per_kwh(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Price per kWh must be greater than 0."
            )
        return value

    def _check_percent(self, value, label):
        if value < Decimal("0") or value > Decimal("100"):
            raise serializers.ValidationError(
                {label: "Must be between 0 and 100."}
            )

    def validate(self, attrs):
        start = attrs.get("start_percent")
        end = attrs.get("end_percent")
        if self.instance is not None:
            if start is None:
                start = self.instance.start_percent
            if end is None:
                end = self.instance.end_percent

        self._check_percent(start, "start_percent")
        self._check_percent(end, "end_percent")

        if end <= start:
            raise serializers.ValidationError(
                {"end_percent": "Completed % must be greater than start %."}
            )
        return attrs
