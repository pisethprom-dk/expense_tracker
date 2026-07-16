# Small helpers shared across the test modules.
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from expense.models import (
    ExpenseItem,
    ExpenseRecord,
    IncomeRecord,
    SavingRecord,
    WeeklyTask,
    TaskTemplate,
)

User = get_user_model()


def make_user(username="tester", password="pass12345", **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


def make_item(name="Food", **kwargs):
    return ExpenseItem.objects.create(item_name=name, **kwargs)


def make_expense(user, item, amount, on, remark=""):
    return ExpenseRecord.objects.create(
        user=user, item=item, amount=Decimal(str(amount)),
        expense_date=on, remark=remark,
    )


def make_income(user, source, amount, on, remark=""):
    return IncomeRecord.objects.create(
        user=user, income_source=source, amount=Decimal(str(amount)),
        income_date=on, remark=remark,
    )


def make_saving(user, amount, on, note=""):
    return SavingRecord.objects.create(
        user=user, amount=Decimal(str(amount)), saving_date=on, note=note,
    )


def make_task(user, title, on, status=WeeklyTask.STATUS_PENDING, order=0):
    return WeeklyTask.objects.create(
        user=user, title=title, task_date=on, status=status, order=order,
    )


def make_template(user, title, order=0, is_active=True, note=""):
    return TaskTemplate.objects.create(
        user=user, title=title, order=order, is_active=is_active, note=note,
    )


# A fixed week for deterministic week-boundary tests.
# 2026-01-07 is a Wednesday -> week is Mon 2026-01-05 .. Sun 2026-01-11.
WEEK_WED = date(2026, 1, 7)
WEEK_MON = date(2026, 1, 5)
WEEK_SUN = date(2026, 1, 11)
