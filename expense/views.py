# v1.2.0
from datetime import date

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ExpenseItem, ExpenseRecord, IncomeRecord
from .serializers import (
    ExpenseItemSerializer,
    ExpenseRecordSerializer,
    IncomeRecordSerializer,
)
from . import services


class ExpenseItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = ExpenseItem.objects.all()
    serializer_class = ExpenseItemSerializer


class ExpenseRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ExpenseRecordSerializer

    def get_queryset(self):
        qs = (
            ExpenseRecord.objects.select_related("item")
            .filter(user=self.request.user)
        )
        expense_date = self.request.query_params.get("date")
        month = self.request.query_params.get("month")  # YYYY-MM
        item_id = self.request.query_params.get("item")
        if expense_date:
            qs = qs.filter(expense_date=expense_date)
        if month:
            try:
                year, mon = services.parse_month(month)
                qs = qs.filter(expense_date__year=year, expense_date__month=mon)
            except ValueError:
                pass
        if item_id:
            qs = qs.filter(item_id=item_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class IncomeRecordViewSet(viewsets.ModelViewSet):
    """Income is record-only; it is never combined with expense summaries."""
    permission_classes = [IsAuthenticated]
    serializer_class = IncomeRecordSerializer

    def get_queryset(self):
        qs = IncomeRecord.objects.filter(user=self.request.user)
        income_date = self.request.query_params.get("date")
        month = self.request.query_params.get("month")
        if income_date:
            qs = qs.filter(income_date=income_date)
        if month:
            try:
                year, mon = services.parse_month(month)
                qs = qs.filter(income_date__year=year, income_date__month=mon)
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def daily_summary(request):
    """GET /api/expense/summary/daily/?date=YYYY-MM-DD (default: today)"""
    date_str = request.query_params.get("date")
    try:
        target = services.parse_date(date_str) if date_str else date.today()
    except ValueError:
        return Response(
            {"detail": "Invalid date format. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_daily_summary(target, user=request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_summary(request):
    """GET /api/expense/summary/monthly/?month=YYYY-MM (default: current month)"""
    month_str = request.query_params.get("month")
    try:
        if month_str:
            year, month = services.parse_month(month_str)
        else:
            today = date.today()
            year, month = today.year, today.month
    except ValueError:
        return Response(
            {"detail": "Invalid month format. Use YYYY-MM."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_monthly_summary(year, month, user=request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def range_summary(request):
    """GET /api/summary/range/?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    from_str = request.query_params.get("from")
    to_str = request.query_params.get("to")
    if not from_str or not to_str:
        return Response(
            {"detail": "'from' and 'to' query params are required (YYYY-MM-DD)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        date_from = services.parse_date(from_str)
        date_to = services.parse_date(to_str)
    except ValueError:
        return Response(
            {"detail": "Invalid date format. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if date_from > date_to:
        return Response(
            {"detail": "'from' must be before 'to'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_range_summary(date_from, date_to, user=request.user))
