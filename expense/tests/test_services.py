"""Unit tests for the business logic in expense/services.py.

These exercise the money math directly (no HTTP), which is where the
important rules live: income is never part of an expense total, the balance
formula, percentages, week boundaries and template de-duplication.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from expense import services
from expense.models import MonthlyBalance, WeeklyTask
from .factories import (
    make_user, make_item, make_expense, make_income, make_saving,
    make_task, make_template, WEEK_WED, WEEK_MON, WEEK_SUN,
)


class MoneyHelperTests(TestCase):
    def test_money_none_is_zero(self):
        self.assertEqual(services.money(None), "0.00")

    def test_money_pads_to_two_places(self):
        self.assertEqual(services.money(Decimal("2")), "2.00")

    def test_money_rounds_to_two_places(self):
        self.assertEqual(services.money(Decimal("1.239")), "1.24")

    def test_pct_zero_whole_is_safe(self):
        self.assertEqual(services._pct(Decimal("5"), Decimal("0")), "0.00")

    def test_pct_basic(self):
        self.assertEqual(services._pct(Decimal("30"), Decimal("50")), "60.00")


class ParseTests(TestCase):
    def test_parse_date_ok(self):
        self.assertEqual(services.parse_date("2026-01-07"), date(2026, 1, 7))

    def test_parse_date_bad_raises(self):
        with self.assertRaises(ValueError):
            services.parse_date("not-a-date")

    def test_parse_month_ok(self):
        self.assertEqual(services.parse_month("2026-06"), (2026, 6))

    def test_parse_month_bad_raises(self):
        with self.assertRaises(ValueError):
            services.parse_month("2026-13")


class WeekBoundsTests(TestCase):
    def test_week_bounds_returns_monday_to_sunday(self):
        monday, sunday = services.week_bounds(WEEK_WED)
        self.assertEqual(monday, WEEK_MON)
        self.assertEqual(sunday, WEEK_SUN)

    def test_week_bounds_on_monday(self):
        monday, sunday = services.week_bounds(WEEK_MON)
        self.assertEqual(monday, WEEK_MON)
        self.assertEqual(sunday, WEEK_SUN)


class DailySummaryTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.food = make_item("Food")
        self.transport = make_item("Transport")
        self.day = date(2026, 1, 10)

    def test_daily_total_and_breakdown(self):
        make_expense(self.user, self.food, "10.00", self.day)
        make_expense(self.user, self.food, "5.00", self.day)
        make_expense(self.user, self.transport, "20.00", self.day)
        # a different day, must be ignored
        make_expense(self.user, self.food, "100.00", date(2026, 1, 9))

        result = services.get_daily_summary(self.day, user=self.user)

        self.assertEqual(result["date"], "2026-01-10")
        self.assertEqual(result["day_total"], "35.00")
        # ordered by -total_amount: Transport (20) before Food (15)
        self.assertEqual(result["items"][0]["item_name"], "Transport")
        self.assertEqual(result["items"][0]["total_amount"], "20.00")
        food_row = next(r for r in result["items"] if r["item_name"] == "Food")
        self.assertEqual(food_row["total_amount"], "15.00")
        self.assertEqual(food_row["record_count"], 2)

    def test_daily_total_empty_is_zero(self):
        result = services.get_daily_summary(self.day, user=self.user)
        self.assertEqual(result["day_total"], "0.00")
        self.assertEqual(result["items"], [])


class MonthlySummaryTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.food = make_item("Food")
        self.transport = make_item("Transport")

    def test_income_is_excluded_from_expense_total(self):
        make_expense(self.user, self.food, "30.00", date(2026, 6, 5))
        make_expense(self.user, self.transport, "20.00", date(2026, 6, 6))
        make_income(self.user, "Salary", "1000.00", date(2026, 6, 1))
        make_saving(self.user, "100.00", date(2026, 6, 2))

        result = services.get_monthly_summary(2026, 6, user=self.user)

        # expense total must NOT include the 1000 income
        self.assertEqual(result["month_total"], "50.00")
        self.assertEqual(result["income_total"], "1000.00")
        self.assertEqual(result["saving_total"], "100.00")
        # balance = income - (expense + saving) = 1000 - 150 = 850
        self.assertEqual(result["balance"], "850.00")

    def test_percent_of_total(self):
        make_expense(self.user, self.food, "30.00", date(2026, 6, 5))
        make_expense(self.user, self.transport, "20.00", date(2026, 6, 6))

        result = services.get_monthly_summary(2026, 6, user=self.user)
        pct = {r["item_name"]: r["percent_of_total"] for r in result["items"]}
        self.assertEqual(pct["Food"], "60.00")
        self.assertEqual(pct["Transport"], "40.00")

    def test_other_month_ignored(self):
        make_expense(self.user, self.food, "30.00", date(2026, 5, 5))
        result = services.get_monthly_summary(2026, 6, user=self.user)
        self.assertEqual(result["month_total"], "0.00")


class RangeSummaryTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.food = make_item("Food")

    def test_range_bounds_are_inclusive(self):
        make_expense(self.user, self.food, "10.00", date(2026, 1, 1))
        make_expense(self.user, self.food, "20.00", date(2026, 1, 15))
        make_expense(self.user, self.food, "40.00", date(2026, 1, 31))
        # outside the range
        make_expense(self.user, self.food, "99.00", date(2026, 2, 1))

        result = services.get_range_summary(
            date(2026, 1, 1), date(2026, 1, 31), user=self.user
        )
        self.assertEqual(result["range_total"], "70.00")
        self.assertEqual(result["date_from"], "2026-01-01")
        self.assertEqual(result["date_to"], "2026-01-31")


class BalanceOverviewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.food = make_item("Food")

    def test_set_monthly_balance_upserts(self):
        services.set_monthly_balance(2026, 6, Decimal("500.00"), user=self.user)
        services.set_monthly_balance(2026, 6, Decimal("700.00"), user=self.user)
        rows = MonthlyBalance.objects.filter(user=self.user, year=2026, month=6)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().amount, Decimal("700.00"))

    def test_remaining_and_month_inclusion_rules(self):
        # June: balance entered AND spending
        services.set_monthly_balance(2026, 6, Decimal("500.00"), user=self.user)
        make_expense(self.user, self.food, "200.00", date(2026, 6, 10))
        # July: spending but no balance -> still included
        make_expense(self.user, self.food, "50.00", date(2026, 7, 10))
        # August: balance but no spending -> still included
        services.set_monthly_balance(2026, 8, Decimal("100.00"), user=self.user)
        # other months: neither -> excluded

        result = services.get_balance_overview(2026, user=self.user)
        months = {m["month_num"]: m for m in result["months"]}

        self.assertEqual(set(months), {6, 7, 8})
        self.assertEqual(months[6]["remaining"], "300.00")   # 500 - 200
        self.assertEqual(months[7]["balance_input"], "0.00")
        self.assertEqual(months[7]["remaining"], "-50.00")   # 0 - 50
        self.assertEqual(months[8]["remaining"], "100.00")   # 100 - 0

        self.assertEqual(result["year_balance_total"], "600.00")
        self.assertEqual(result["year_spent_total"], "250.00")
        self.assertEqual(result["year_remaining"], "350.00")


class SavingSummaryTests(TestCase):
    def test_saving_per_month_and_year_total(self):
        user = make_user()
        make_saving(user, "50.00", date(2026, 1, 5))
        make_saving(user, "70.00", date(2026, 3, 9))
        result = services.get_saving_summary(2026, user=user)
        months = {m["month_num"]: m["total_amount"] for m in result["months"]}
        self.assertEqual(months, {1: "50.00", 3: "70.00"})
        self.assertEqual(result["year_total"], "120.00")


class WeekSummaryTests(TestCase):
    def test_week_stats_and_achievement(self):
        user = make_user()
        make_task(user, "A", WEEK_MON, WeeklyTask.STATUS_SUCCESS)
        make_task(user, "B", WEEK_MON, WeeklyTask.STATUS_SUCCESS)
        make_task(user, "C", date(2026, 1, 6), WeeklyTask.STATUS_FAILED)
        make_task(user, "D", WEEK_SUN, WeeklyTask.STATUS_PENDING)
        # a task in another week must be ignored
        make_task(user, "E", date(2026, 1, 20), WeeklyTask.STATUS_SUCCESS)

        result = services.get_week_summary(WEEK_WED, user=user)
        self.assertEqual(result["week_start"], "2026-01-05")
        self.assertEqual(result["week_end"], "2026-01-11")
        self.assertEqual(result["total_tasks"], 4)
        self.assertEqual(result["success_tasks"], 2)
        self.assertEqual(result["failed_tasks"], 1)
        self.assertEqual(result["pending_tasks"], 1)
        # 2 success out of 4 total = 50.00
        self.assertEqual(result["achievement_percent"], "50.00")
        self.assertEqual(len(result["days"]), 7)
        self.assertEqual(result["days"][0]["weekday"], "Monday")

    def test_empty_week_is_zero_percent(self):
        user = make_user()
        result = services.get_week_summary(WEEK_WED, user=user)
        self.assertEqual(result["total_tasks"], 0)
        self.assertEqual(result["achievement_percent"], "0.00")


class ApplyTemplatesTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.day = date(2026, 1, 5)

    def test_active_templates_create_tasks_inactive_skipped(self):
        make_template(self.user, "Read", order=0, is_active=True)
        make_template(self.user, "Exercise", order=1, is_active=True)
        make_template(self.user, "Old", order=2, is_active=False)

        created = services.apply_templates_to_dates([self.day], user=self.user)
        self.assertEqual(created, 2)
        titles = set(
            WeeklyTask.objects.filter(user=self.user, task_date=self.day)
            .values_list("title", flat=True)
        )
        self.assertEqual(titles, {"Read", "Exercise"})

    def test_apply_is_idempotent_by_title(self):
        make_template(self.user, "Read", is_active=True)
        services.apply_templates_to_dates([self.day], user=self.user)
        # applying again the same day creates nothing new
        created = services.apply_templates_to_dates([self.day], user=self.user)
        self.assertEqual(created, 0)
        self.assertEqual(
            WeeklyTask.objects.filter(user=self.user, task_date=self.day).count(),
            1,
        )

    def test_existing_task_with_same_title_is_skipped(self):
        make_template(self.user, "Read", is_active=True)
        make_task(self.user, "Read", self.day)  # already there
        created = services.apply_templates_to_dates([self.day], user=self.user)
        self.assertEqual(created, 0)
