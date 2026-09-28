# v1.0.0
"""Covers the v1.13.0 additions: income summary, amount filters, income filters."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APITestCase

from expense import services
from expense.models import IncomeRecord
from expense.tests.factories import make_user, make_item, make_expense


def make_income(user, source, amount, on):
    return IncomeRecord.objects.create(
        user=user, income_source=source,
        amount=Decimal(amount), income_date=on,
    )


class IncomeSummaryServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user(username="other")

    def test_year_total_and_months(self):
        make_income(self.user, "Salary", "1200.00", date(2026, 1, 15))
        make_income(self.user, "Salary", "1200.00", date(2026, 2, 15))
        make_income(self.user, "Freelance", "300.00", date(2026, 2, 20))

        data = services.get_income_summary(2026, user=self.user)
        self.assertEqual(data["year"], "2026")
        self.assertEqual(data["year_total"], "2700.00")
        self.assertEqual([m["month_num"] for m in data["months"]], [1, 2])
        self.assertEqual(data["months"][1]["total_amount"], "1500.00")
        self.assertEqual(data["months"][1]["record_count"], 2)

    def test_source_breakdown_is_ordered_by_size(self):
        make_income(self.user, "Salary", "1200.00", date(2026, 1, 15))
        make_income(self.user, "Freelance", "300.00", date(2026, 1, 20))
        data = services.get_income_summary(2026, user=self.user)
        self.assertEqual(data["sources"][0]["income_source"], "Salary")
        self.assertEqual(data["sources"][0]["percent_of_total"], "80.00")

    def test_empty_year(self):
        data = services.get_income_summary(2026, user=self.user)
        self.assertEqual(data["year_total"], "0.00")
        self.assertEqual(data["months"], [])
        self.assertEqual(data["sources"], [])

    def test_scoped_to_user(self):
        make_income(self.other, "Salary", "9999.00", date(2026, 1, 15))
        data = services.get_income_summary(2026, user=self.user)
        self.assertEqual(data["year_total"], "0.00")

    def test_other_years_excluded(self):
        make_income(self.user, "Salary", "500.00", date(2025, 6, 1))
        data = services.get_income_summary(2026, user=self.user)
        self.assertEqual(data["year_total"], "0.00")


class IncomeSummaryApiTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_returns_summary(self):
        make_income(self.user, "Salary", "1200.00", date(2026, 1, 15))
        response = self.client.get("/api/incomes/summary/?year=2026")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["year_total"], "1200.00")

    def test_bad_year_returns_400(self):
        response = self.client.get("/api/incomes/summary/?year=abcd")
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/incomes/summary/").status_code, 401
        )


class IncomeFilterTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)
        make_income(self.user, "Salary", "1200.00", date(2026, 1, 15))
        make_income(self.user, "Bonus", "500.00", date(2025, 12, 1))

    def test_year_filter(self):
        response = self.client.get("/api/incomes/?year=2026")
        self.assertEqual(len(response.data), 1)

    def test_range_filter(self):
        response = self.client.get(
            "/api/incomes/?from=2025-11-01&to=2025-12-31"
        )
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["income_source"], "Bonus")


class ExpenseAmountFilterTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)
        self.item = make_item("Food")
        make_expense(self.user, self.item, "12.00", date(2026, 3, 1))
        make_expense(self.user, self.item, "55.00", date(2026, 3, 2))
        make_expense(self.user, self.item, "120.00", date(2026, 3, 3))

    def test_min_amount(self):
        response = self.client.get("/api/records/?min_amount=50")
        self.assertEqual(len(response.data), 2)

    def test_min_amount_with_period(self):
        response = self.client.get(
            "/api/records/?min_amount=50&from=2026-03-01&to=2026-03-02"
        )
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["amount"], "55.00")

    def test_max_amount(self):
        response = self.client.get("/api/records/?max_amount=50")
        self.assertEqual(len(response.data), 1)

    def test_bad_min_amount_returns_400(self):
        response = self.client.get("/api/records/?min_amount=lots")
        self.assertEqual(response.status_code, 400)
