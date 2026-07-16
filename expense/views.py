# v1.11.0
from datetime import date

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ExpenseItem, ExpenseRecord, IncomeRecord, SavingRecord, WeeklyTask, TaskTemplate, MonthlyTask
from .serializers import (
    ExpenseItemSerializer,
    ExpenseRecordSerializer,
    IncomeRecordSerializer,
    SavingRecordSerializer,
    WeeklyTaskSerializer,
    TaskTemplateSerializer,
    MonthlyTaskSerializer,
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
        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if expense_date:
            qs = qs.filter(expense_date=expense_date)
        if month:
            try:
                year, mon = services.parse_month(month)
                qs = qs.filter(expense_date__year=year, expense_date__month=mon)
            except ValueError:
                pass
        if date_from:
            qs = qs.filter(expense_date__gte=date_from)
        if date_to:
            qs = qs.filter(expense_date__lte=date_to)
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


class SavingRecordViewSet(viewsets.ModelViewSet):
    """CRUD for savings; filter by ?date=YYYY-MM-DD, ?month=YYYY-MM or ?year=YYYY."""
    permission_classes = [IsAuthenticated]
    serializer_class = SavingRecordSerializer

    def get_queryset(self):
        qs = SavingRecord.objects.filter(user=self.request.user)
        saving_date = self.request.query_params.get("date")
        month = self.request.query_params.get("month")
        year = self.request.query_params.get("year")
        if saving_date:
            qs = qs.filter(saving_date=saving_date)
        if month:
            try:
                y, mon = services.parse_month(month)
                qs = qs.filter(saving_date__year=y, saving_date__month=mon)
            except ValueError:
                pass
        if year:
            try:
                qs = qs.filter(saving_date__year=int(year))
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WeeklyTaskViewSet(viewsets.ModelViewSet):
    """CRUD for tasks; filter by ?date=YYYY-MM-DD or ?week=YYYY-MM-DD (any day in week)."""
    permission_classes = [IsAuthenticated]
    serializer_class = WeeklyTaskSerializer

    def get_queryset(self):
        qs = WeeklyTask.objects.filter(user=self.request.user)
        task_date = self.request.query_params.get("date")
        week = self.request.query_params.get("week")
        if task_date:
            qs = qs.filter(task_date=task_date)
        if week:
            try:
                anchor = services.parse_date(week)
                monday, sunday = services.week_bounds(anchor)
                qs = qs.filter(task_date__gte=monday, task_date__lte=sunday)
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        # place new task at the end of its day
        task_date = serializer.validated_data.get("task_date")
        last = (
            WeeklyTask.objects.filter(user=self.request.user, task_date=task_date)
            .order_by("-order")
            .first()
        )
        next_order = (last.order + 1) if last else 0
        serializer.save(user=self.request.user, order=next_order)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """POST /api/tasks/reorder/  Body: {"ids": [id1, id2, ...]}
        Sets order to match the given id sequence (same day)."""
        ids = request.data.get("ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "ids must be a list."}, status=400)
        tasks = {
            t.id: t for t in WeeklyTask.objects.filter(
                user=request.user, id__in=ids
            )
        }
        for index, tid in enumerate(ids):
            t = tasks.get(tid)
            if t:
                t.order = index
                t.save(update_fields=["order"])
        return Response({"detail": "reordered", "count": len(ids)})


class TaskTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for reusable daily task templates."""
    permission_classes = [IsAuthenticated]
    serializer_class = TaskTemplateSerializer

    def get_queryset(self):
        return TaskTemplate.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        last = (
            TaskTemplate.objects.filter(user=self.request.user)
            .order_by("-order")
            .first()
        )
        next_order = (last.order + 1) if last else 0
        serializer.save(user=self.request.user, order=next_order)

    @action(detail=False, methods=["post"])
    def apply(self, request):
        """POST /api/task-templates/apply/
        Body: {"week": "YYYY-MM-DD"} -> apply to all 7 days of that week,
        or {"date": "YYYY-MM-DD"} -> apply to a single day.
        """
        week = request.data.get("week")
        single = request.data.get("date")
        try:
            if week:
                anchor = services.parse_date(week)
                monday, sunday = services.week_bounds(anchor)
                from datetime import timedelta
                dates = [monday + timedelta(days=i) for i in range(7)]
            elif single:
                dates = [services.parse_date(single)]
            else:
                return Response(
                    {"detail": "Provide 'week' or 'date' (YYYY-MM-DD)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = services.apply_templates_to_dates(dates, user=request.user)
        return Response({"detail": "applied", "created": created})


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def balance_overview(request):
    """GET /api/summary/balance/?year=YYYY (default: current year)

    Per-month income, spent and remaining balance for the year.
    """
    from datetime import date as _date
    year_str = request.query_params.get("year")
    try:
        year = int(year_str) if year_str else _date.today().year
    except ValueError:
        return Response(
            {"detail": "Invalid year. Use YYYY."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_balance_overview(year, user=request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_balance(request):
    """POST /api/summary/balance/set/  Body: {"year": 2026, "month": 6, "amount": "500.00"}"""
    from decimal import Decimal, InvalidOperation
    try:
        year = int(request.data.get("year"))
        month = int(request.data.get("month"))
        amount = Decimal(str(request.data.get("amount")))
    except (TypeError, ValueError, InvalidOperation):
        return Response(
            {"detail": "year, month and amount are required and must be valid."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if month < 1 or month > 12:
        return Response(
            {"detail": "month must be 1-12."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    services.set_monthly_balance(year, month, amount, user=request.user)
    return Response(services.get_balance_overview(year, user=request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def saving_summary(request):
    """GET /api/savings/summary/?year=YYYY — per-month + whole-year saving total."""
    from datetime import date as _date
    year_str = request.query_params.get("year")
    try:
        year = int(year_str) if year_str else _date.today().year
    except ValueError:
        return Response(
            {"detail": "Invalid year. Use YYYY."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_saving_summary(year, user=request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_summary(request):
    """GET /api/tasks/summary/?week=YYYY-MM-DD (any day in the week; default: today)"""
    from datetime import date as _date
    week_str = request.query_params.get("week")
    try:
        anchor = services.parse_date(week_str) if week_str else _date.today()
    except ValueError:
        return Response(
            {"detail": "Invalid date. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_week_summary(anchor, user=request.user))


class MonthlyTaskViewSet(viewsets.ModelViewSet):
    """CRUD for monthly tasks; filter by ?year=YYYY (12 months) or ?year=YYYY&month=M."""
    permission_classes = [IsAuthenticated]
    serializer_class = MonthlyTaskSerializer

    def get_queryset(self):
        qs = MonthlyTask.objects.filter(user=self.request.user)
        year = self.request.query_params.get("year")
        month = self.request.query_params.get("month")
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        return qs

    def perform_create(self, serializer):
        # place new task at the end of its month
        year = serializer.validated_data.get("year")
        month = serializer.validated_data.get("month")
        last = (
            MonthlyTask.objects.filter(user=self.request.user, year=year, month=month)
            .order_by("-order")
            .first()
        )
        next_order = (last.order + 1) if last else 0
        serializer.save(user=self.request.user, order=next_order)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """POST /api/monthly-tasks/reorder/  Body: {"ids": [id1, id2, ...]}
        Sets order to match the given id sequence (same month)."""
        ids = request.data.get("ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "ids must be a list."}, status=400)
        tasks = {
            t.id: t for t in MonthlyTask.objects.filter(
                user=request.user, id__in=ids
            )
        }
        for index, tid in enumerate(ids):
            t = tasks.get(tid)
            if t:
                t.order = index
                t.save(update_fields=["order"])
        return Response({"detail": "reordered", "count": len(ids)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def yearly_summary(request):
    """GET /api/summary/yearly/?year=YYYY (default: current year)"""
    from datetime import date as _date
    year_str = request.query_params.get("year")
    try:
        year = int(year_str) if year_str else _date.today().year
    except (TypeError, ValueError):
        return Response(
            {"detail": "Invalid year. Use YYYY."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(services.get_year_summary(year, user=request.user))
