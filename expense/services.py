# v1.2.0
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Sum, Count

from .models import ExpenseRecord


def get_daily_summary(target_date: date, user=None) -> dict:
    """Total of the day plus breakdown by item."""
    qs = ExpenseRecord.objects.filter(expense_date=target_date)
    if user is not None:
        qs = qs.filter(user=user)

    breakdown = (
        qs.values("item__id", "item__item_name")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )

    day_total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return {
        "date": target_date.isoformat(),
        "day_total": money(day_total),
        "items": [
            {
                "item_id": row["item__id"],
                "item_name": row["item__item_name"],
                "total_amount": money(row["total_amount"]),
                "record_count": row["record_count"],
            }
            for row in breakdown
        ],
    }


def get_monthly_summary(year: int, month: int, user=None) -> dict:
    """Group by item, sorted descending so the biggest spend items
    (candidates to reduce) appear first, with % of month total."""
    qs = ExpenseRecord.objects.filter(
        expense_date__year=year, expense_date__month=month
    )
    if user is not None:
        qs = qs.filter(user=user)

    month_total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    breakdown = (
        qs.values("item__id", "item__item_name")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )

    items = []
    for row in breakdown:
        percent = (
            (row["total_amount"] / month_total * 100).quantize(Decimal("0.01"))
            if month_total > 0 else Decimal("0.00")
        )
        items.append({
            "item_id": row["item__id"],
            "item_name": row["item__item_name"],
            "total_amount": money(row["total_amount"]),
            "record_count": row["record_count"],
            "percent_of_total": str(percent),
        })

    return {
        "month": f"{year:04d}-{month:02d}",
        "month_total": money(month_total),
        "items": items,
    }


def get_range_summary(date_from: date, date_to: date, user=None) -> dict:
    """Group by item over an arbitrary date range, biggest spend first."""
    qs = ExpenseRecord.objects.filter(
        expense_date__gte=date_from, expense_date__lte=date_to
    )
    if user is not None:
        qs = qs.filter(user=user)

    range_total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    breakdown = (
        qs.values("item__id", "item__item_name")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )

    items = []
    for row in breakdown:
        percent = (
            (row["total_amount"] / range_total * 100).quantize(Decimal("0.01"))
            if range_total > 0 else Decimal("0.00")
        )
        items.append({
            "item_id": row["item__id"],
            "item_name": row["item__item_name"],
            "total_amount": money(row["total_amount"]),
            "record_count": row["record_count"],
            "percent_of_total": str(percent),
        })

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "range_total": money(range_total),
        "items": items,
    }


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_month(value: str) -> tuple[int, int]:
    dt = datetime.strptime(value, "%Y-%m")
    return dt.year, dt.month

TWO_DP = Decimal("0.01")

def money(value) -> str:
    return str((value or Decimal("0")).quantize(TWO_DP))