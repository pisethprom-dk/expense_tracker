# v1.0.0
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from expense import services as expense_services

from .models import Vehicle, ChargingRecord
from .serializers import VehicleSerializer, ChargingRecordSerializer
from . import services


class VehicleViewSet(viewsets.ModelViewSet):
    """CRUD for vehicles; filter with ?active=true to hide retired cars."""

    permission_classes = [IsAuthenticated]
    serializer_class = VehicleSerializer

    def get_queryset(self):
        qs = Vehicle.objects.filter(user=self.request.user)
        active = self.request.query_params.get("active")
        if active is not None:
            qs = qs.filter(is_active=active.lower() in ("1", "true", "yes"))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ChargingRecordViewSet(viewsets.ModelViewSet):
    """CRUD for charging sessions.

    Filters: ?vehicle=<id>, ?charger_type=AC|DC, ?month=YYYY-MM,
    ?from=YYYY-MM-DD, ?to=YYYY-MM-DD
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ChargingRecordSerializer

    def get_queryset(self):
        qs = (
            ChargingRecord.objects.select_related("vehicle", "expense_record")
            .filter(user=self.request.user)
        )
        params = self.request.query_params
        vehicle_id = params.get("vehicle")
        charger_type = params.get("charger_type")
        month = params.get("month")
        date_from = params.get("from")
        date_to = params.get("to")

        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)
        if charger_type:
            qs = qs.filter(charger_type=charger_type.upper())
        if month:
            year, mon = expense_services.parse_month(month)
            qs = qs.filter(charge_date__year=year, charge_date__month=mon)
        if date_from:
            qs = qs.filter(charge_date__gte=expense_services.parse_date(date_from))
        if date_to:
            qs = qs.filter(charge_date__lte=expense_services.parse_date(date_to))
        return qs

    def list(self, request, *args, **kwargs):
        # bad filter values return 400 rather than silently listing everything
        try:
            return super().list(request, *args, **kwargs)
        except ValueError:
            return Response(
                {"detail": "Invalid filter value. Use YYYY-MM-DD or YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def perform_create(self, serializer):
        record = ChargingRecord(
            user=self.request.user,
            charge_date=serializer.validated_data.pop(
                "charge_date", None
            ) or timezone.localdate(),
            **serializer.validated_data
        )
        services.save_charging_record(record)
        serializer.instance = record

    def perform_update(self, serializer):
        record = serializer.instance
        for field, value in serializer.validated_data.items():
            setattr(record, field, value)
        services.save_charging_record(record)

    def perform_destroy(self, instance):
        services.delete_charging_record(instance)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_ev_summary(request):
    """GET /api/ev/summary/monthly/?month=YYYY-MM (default: current month)"""
    month_str = request.query_params.get("month")
    try:
        if month_str:
            year, month = expense_services.parse_month(month_str)
        else:
            today = timezone.localdate()
            year, month = today.year, today.month
    except ValueError:
        return Response(
            {"detail": "Invalid month format. Use YYYY-MM."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_monthly_ev_summary(year, month, user=request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def yearly_ev_summary(request):
    """GET /api/ev/summary/yearly/?year=YYYY (default: current year)"""
    year_str = request.query_params.get("year")
    try:
        year = int(year_str) if year_str else timezone.localdate().year
    except (TypeError, ValueError):
        return Response(
            {"detail": "Invalid year. Use YYYY."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_yearly_ev_summary(year, user=request.user))
