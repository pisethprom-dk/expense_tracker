# v1.0.0
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth

from expense.models import ExpenseItem, ExpenseRecord
from expense.services import money

from .models import ChargingRecord

THREE_DP = Decimal("0.001")
HUNDRED = Decimal("100")

#: Expense item under which every charging session is recorded.
EV_EXPENSE_ITEM_NAME = "EV Charging"


def kwh(value) -> str:
    """Round a Decimal/None to 3 places and return it as a string."""
    return str((value or Decimal("0")).quantize(THREE_DP, rounding=ROUND_HALF_UP))


def compute_totals(start_percent, end_percent, battery_capacity_kwh, price_per_kwh):
    """Return (total_kwh, total_price) as quantized Decimals.

    total_kwh   = (end% - start%) / 100 * capacity
    total_price = total_kwh * price_per_kwh
    """
    delta = (Decimal(end_percent) - Decimal(start_percent)) / HUNDRED
    total_kwh = (delta * Decimal(battery_capacity_kwh)).quantize(
        THREE_DP, rounding=ROUND_HALF_UP
    )
    total_price = (total_kwh * Decimal(price_per_kwh)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return total_kwh, total_price


def get_ev_expense_item():
    """The shared 'EV Charging' expense item (master data, created on demand)."""
    item, _ = ExpenseItem.objects.get_or_create(
        item_name=EV_EXPENSE_ITEM_NAME, defaults={"is_active": True},
    )
    return item


def build_remark(record) -> str:
    """Human-readable remark written onto the linked expense record."""
    parts = ["EV charge", record.vehicle.display_name,
             "%s kWh" % kwh(record.total_kwh), record.charger_type]
    text = " - ".join(parts)
    if record.location:
        text = "%s @ %s" % (text, record.location)
    return text[:255]


def sync_expense_record(record):
    """Create or update the ExpenseRecord mirroring this charging session.

    Called inside the same transaction as the charging record save. If the
    link was lost (expense deleted directly in the admin), a fresh one is
    created rather than leaving the session unrecorded.
    """
    expense = record.expense_record
    if expense is None:
        expense = ExpenseRecord.objects.create(
            user=record.user,
            item=get_ev_expense_item(),
            amount=record.total_price,
            expense_date=record.charge_date,
            remark=build_remark(record),
        )
        record.expense_record = expense
        record.save(update_fields=["expense_record"])
        return expense

    expense.amount = record.total_price
    expense.expense_date = record.charge_date
    expense.remark = build_remark(record)
    expense.save(update_fields=["amount", "expense_date", "remark"])
    return expense


@transaction.atomic
def save_charging_record(record):
    """Compute totals, persist, and mirror into the expense tracker."""
    record.battery_capacity_kwh = record.vehicle.battery_capacity_kwh
    record.total_kwh, record.total_price = compute_totals(
        record.start_percent,
        record.end_percent,
        record.battery_capacity_kwh,
        record.price_per_kwh,
    )
    record.save()
    sync_expense_record(record)
    return record


@transaction.atomic
def delete_charging_record(record):
    """Delete the session and the expense row it owns."""
    expense = record.expense_record
    record.delete()
    if expense is not None:
        expense.delete()


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------

def _vehicle_breakdown(qs):
    """Per-vehicle totals for an already-filtered charging-record queryset."""
    rows = (
        qs.values("vehicle__id", "vehicle__brand", "vehicle__plate_number")
        .annotate(
            session_count=Count("id"),
            kwh_total=Sum("total_kwh"),
            price_total=Sum("total_price"),
        )
        .order_by("-price_total")
    )
    return [
        {
            "vehicle_id": row["vehicle__id"],
            "brand": row["vehicle__brand"],
            "plate_number": row["vehicle__plate_number"],
            "session_count": row["session_count"],
            "total_kwh": kwh(row["kwh_total"]),
            "total_price": money(row["price_total"]),
        }
        for row in rows
    ]


def get_monthly_ev_summary(year, month, user) -> dict:
    """Plain totals for one month, plus a per-vehicle breakdown."""
    qs = ChargingRecord.objects.filter(
        user=user, charge_date__year=year, charge_date__month=month,
    )
    totals = qs.aggregate(
        session_count=Count("id"),
        kwh_total=Sum("total_kwh"),
        price_total=Sum("total_price"),
    )
    return {
        "month": "%04d-%02d" % (year, month),
        "session_count": totals["session_count"] or 0,
        "total_kwh": kwh(totals["kwh_total"]),
        "total_price": money(totals["price_total"]),
        "vehicles": _vehicle_breakdown(qs),
    }


def get_yearly_ev_summary(year, user) -> dict:
    """Twelve-month rollup for a year, plus a per-vehicle breakdown.

    Months are aggregated in a single query rather than one query per month.
    """
    qs = ChargingRecord.objects.filter(user=user, charge_date__year=year)

    by_month = {
        row["m"]: row
        for row in qs.annotate(m=ExtractMonth("charge_date"))
        .values("m")
        .annotate(
            session_count=Count("id"),
            kwh_total=Sum("total_kwh"),
            price_total=Sum("total_price"),
        )
    }

    months = []
    for m in range(1, 13):
        row = by_month.get(m)
        if not row:
            continue
        months.append({
            "month": "%04d-%02d" % (year, m),
            "month_num": m,
            "session_count": row["session_count"],
            "total_kwh": kwh(row["kwh_total"]),
            "total_price": money(row["price_total"]),
        })

    totals = qs.aggregate(
        session_count=Count("id"),
        kwh_total=Sum("total_kwh"),
        price_total=Sum("total_price"),
    )
    return {
        "year": int(year),
        "session_count": totals["session_count"] or 0,
        "total_kwh": kwh(totals["kwh_total"]),
        "total_price": money(totals["price_total"]),
        "months": months,
        "vehicles": _vehicle_breakdown(qs),
    }
