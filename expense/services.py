# v1.8.0
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Sum, Count

from .models import ExpenseRecord, IncomeRecord, MonthlyBalance, SavingRecord, WeeklyTask

TWO_DP = Decimal("0.01")


def money(value) -> str:
    """Round any Decimal/None to 2 places and return as string (SQLite/PG safe)."""
    return str((value or Decimal("0")).quantize(TWO_DP))


def _pct(part, whole) -> str:
    if whole and whole > 0:
        return str((part / whole * 100).quantize(TWO_DP))
    return "0.00"


def get_daily_summary(target_date, user=None) -> dict:
    """Expense total of the day plus breakdown by item."""
    qs = ExpenseRecord.objects.filter(expense_date=target_date)
    if user is not None:
        qs = qs.filter(user=user)

    breakdown = (
        qs.values("item__id", "item__item_name")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )
    day_total = qs.aggregate(total=Sum("amount"))["total"]

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


def get_monthly_summary(year, month, user=None) -> dict:
    """Expense grouped by item (biggest first) + income, saving, and balance.

    balance = income_total - (month_total expense + saving_total).
    """
    exp_qs = ExpenseRecord.objects.filter(
        expense_date__year=year, expense_date__month=month
    )
    inc_qs = IncomeRecord.objects.filter(
        income_date__year=year, income_date__month=month
    )
    sav_qs = SavingRecord.objects.filter(
        saving_date__year=year, saving_date__month=month
    )
    if user is not None:
        exp_qs = exp_qs.filter(user=user)
        inc_qs = inc_qs.filter(user=user)
        sav_qs = sav_qs.filter(user=user)

    month_total = exp_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    income_total = inc_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    saving_total = sav_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    balance = income_total - (month_total + saving_total)

    breakdown = (
        exp_qs.values("item__id", "item__item_name")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )
    items = [
        {
            "item_id": row["item__id"],
            "item_name": row["item__item_name"],
            "total_amount": money(row["total_amount"]),
            "record_count": row["record_count"],
            "percent_of_total": _pct(row["total_amount"], month_total),
        }
        for row in breakdown
    ]

    income_breakdown = (
        inc_qs.values("income_source")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )
    incomes = [
        {
            "income_source": row["income_source"],
            "total_amount": money(row["total_amount"]),
            "record_count": row["record_count"],
            "percent_of_total": _pct(row["total_amount"], income_total),
        }
        for row in income_breakdown
    ]

    return {
        "month": "%04d-%02d" % (year, month),
        "month_total": money(month_total),
        "income_total": money(income_total),
        "saving_total": money(saving_total),
        "balance": money(balance),
        "items": items,
        "incomes": incomes,
    }


def get_range_summary(date_from, date_to, user=None) -> dict:
    """Expense grouped by item over a date range + income, saving, and balance.

    balance = income_total - (range_total expense + saving_total).
    """
    exp_qs = ExpenseRecord.objects.filter(
        expense_date__gte=date_from, expense_date__lte=date_to
    )
    inc_qs = IncomeRecord.objects.filter(
        income_date__gte=date_from, income_date__lte=date_to
    )
    sav_qs = SavingRecord.objects.filter(
        saving_date__gte=date_from, saving_date__lte=date_to
    )
    if user is not None:
        exp_qs = exp_qs.filter(user=user)
        inc_qs = inc_qs.filter(user=user)
        sav_qs = sav_qs.filter(user=user)

    range_total = exp_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    income_total = inc_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    saving_total = sav_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    balance = income_total - (range_total + saving_total)

    breakdown = (
        exp_qs.values("item__id", "item__item_name")
        .annotate(total_amount=Sum("amount"), record_count=Count("id"))
        .order_by("-total_amount")
    )
    items = [
        {
            "item_id": row["item__id"],
            "item_name": row["item__item_name"],
            "total_amount": money(row["total_amount"]),
            "record_count": row["record_count"],
            "percent_of_total": _pct(row["total_amount"], range_total),
        }
        for row in breakdown
    ]

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "range_total": money(range_total),
        "income_total": money(income_total),
        "saving_total": money(saving_total),
        "balance": money(balance),
        "items": items,
    }


def get_balance_overview(year, user=None) -> dict:
    """Per-month entered balance, spent and remaining (balance - spent)."""
    # entered balances for the year, keyed by month
    bal_qs = MonthlyBalance.objects.filter(year=year)
    if user is not None:
        bal_qs = bal_qs.filter(user=user)
    entered = {b.month: b.amount for b in bal_qs}

    months = []
    for m in range(1, 13):
        exp_qs = ExpenseRecord.objects.filter(
            expense_date__year=year, expense_date__month=m
        )
        if user is not None:
            exp_qs = exp_qs.filter(user=user)

        spent = exp_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        balance_in = entered.get(m, Decimal("0"))
        # include months that have a balance entered OR any spending
        if spent == 0 and m not in entered:
            continue
        months.append({
            "month": "%04d-%02d" % (year, m),
            "month_num": m,
            "balance_input": money(balance_in),
            "spent_total": money(spent),
            "remaining": money(balance_in - spent),
        })

    year_balance = sum((Decimal(x["balance_input"]) for x in months), Decimal("0"))
    year_spent = sum((Decimal(x["spent_total"]) for x in months), Decimal("0"))

    return {
        "year": str(year),
        "year_balance_total": money(year_balance),
        "year_spent_total": money(year_spent),
        "year_remaining": money(year_balance - year_spent),
        "months": months,
    }


def set_monthly_balance(year, month, amount, user=None):
    """Upsert the entered balance for a month."""
    obj, _ = MonthlyBalance.objects.update_or_create(
        user=user, year=year, month=month,
        defaults={"amount": amount},
    )
    return obj


def get_saving_summary(year, user=None) -> dict:
    """Per-month saving totals and the whole-year total."""
    qs = SavingRecord.objects.filter(saving_date__year=year)
    if user is not None:
        qs = qs.filter(user=user)

    months = []
    for m in range(1, 13):
        m_total = qs.filter(saving_date__month=m).aggregate(t=Sum("amount"))["t"]
        if not m_total:
            continue
        months.append({
            "month": "%04d-%02d" % (year, m),
            "month_num": m,
            "total_amount": money(m_total),
        })

    year_total = qs.aggregate(t=Sum("amount"))["t"]
    return {
        "year": str(year),
        "year_total": money(year_total),
        "months": months,
    }


def week_bounds(any_date):
    """Return (monday, sunday) for the ISO week containing any_date."""
    monday = any_date - timedelta(days=any_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_week_summary(any_date, user=None) -> dict:
    """Per-day tasks for the week + end-of-week achievement stats."""
    monday, sunday = week_bounds(any_date)
    qs = WeeklyTask.objects.filter(task_date__gte=monday, task_date__lte=sunday)
    if user is not None:
        qs = qs.filter(user=user)

    names = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
    days = []
    total = 0
    done = 0
    for i in range(7):
        d = monday + timedelta(days=i)
        day_tasks = [t for t in qs if t.task_date == d]
        day_tasks.sort(key=lambda t: (t.order, t.created_at))
        d_done = sum(1 for t in day_tasks if t.is_done)
        total += len(day_tasks)
        done += d_done
        days.append({
            "date": d.isoformat(),
            "weekday": names[i],
            "task_count": len(day_tasks),
            "done_count": d_done,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "is_done": t.is_done,
                    "note": t.note,
                    "order": t.order,
                }
                for t in day_tasks
            ],
        })

    percent = str((Decimal(done) / Decimal(total) * 100).quantize(TWO_DP)) \
        if total else "0.00"

    return {
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "total_tasks": total,
        "done_tasks": done,
        "pending_tasks": total - done,
        "achievement_percent": percent,
        "days": days,
    }


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_month(value):
    dt = datetime.strptime(value, "%Y-%m")
    return dt.year, dt.month

