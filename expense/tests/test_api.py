"""API-level tests: user isolation, auto-assignment of user/order, custom
actions (reorder, apply) and the summary endpoints (200 + shape + 400s)."""
from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from expense.models import ExpenseRecord, WeeklyTask
from .factories import (
    make_user, make_item, make_expense, make_income, make_task, make_template,
)


class UserIsolationTests(APITestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.item = make_item("Food")
        make_expense(self.alice, self.item, "10.00", date(2026, 1, 1))
        make_expense(self.alice, self.item, "20.00", date(2026, 1, 2))
        make_expense(self.bob, self.item, "999.00", date(2026, 1, 1))

    def test_record_list_only_shows_own_rows(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get("/api/records/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        amounts = {r["amount"] for r in resp.data}
        self.assertNotIn("999.00", amounts)

    def test_monthly_summary_is_per_user(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get("/api/summary/monthly/?month=2026-01")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["month_total"], "30.00")  # not 1029.00


class CreateAssignsUserTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.item = make_item("Food")
        self.client.force_authenticate(self.user)

    def test_perform_create_sets_request_user(self):
        resp = self.client.post("/api/records/", {
            "item": self.item.id, "amount": "12.50",
            "expense_date": "2026-01-01",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        rec = ExpenseRecord.objects.get(id=resp.data["id"])
        self.assertEqual(rec.user, self.user)

    def test_expense_negative_amount_rejected_by_api(self):
        resp = self.client.post("/api/records/", {
            "item": self.item.id, "amount": "-1.00",
            "expense_date": "2026-01-01",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class WeeklyTaskOrderingTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.day = "2026-01-05"

    def test_order_auto_increments_per_day(self):
        r1 = self.client.post("/api/tasks/", {"title": "A", "task_date": self.day})
        r2 = self.client.post("/api/tasks/", {"title": "B", "task_date": self.day})
        self.assertEqual(r1.data["order"], 0)
        self.assertEqual(r2.data["order"], 1)

    def test_reorder_action(self):
        a = make_task(self.user, "A", date(2026, 1, 5), order=0)
        b = make_task(self.user, "B", date(2026, 1, 5), order=1)
        c = make_task(self.user, "C", date(2026, 1, 5), order=2)

        resp = self.client.post(
            "/api/tasks/reorder/", {"ids": [c.id, a.id, b.id]}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 3)
        c.refresh_from_db(); a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((c.order, a.order, b.order), (0, 1, 2))

    def test_reorder_rejects_non_list(self):
        resp = self.client.post(
            "/api/tasks/reorder/", {"ids": "nope"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TaskTemplateApplyTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)

    def test_apply_single_day(self):
        make_template(self.user, "Read")
        make_template(self.user, "Exercise")
        resp = self.client.post(
            "/api/task-templates/apply/", {"date": "2026-01-05"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["created"], 2)
        self.assertEqual(
            WeeklyTask.objects.filter(
                user=self.user, task_date=date(2026, 1, 5)
            ).count(),
            2,
        )

    def test_apply_full_week(self):
        make_template(self.user, "Read")
        resp = self.client.post(
            "/api/task-templates/apply/", {"week": "2026-01-07"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["created"], 7)  # one per day, Mon-Sun

    def test_apply_requires_date_or_week(self):
        resp = self.client.post("/api/task-templates/apply/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_invalid_date(self):
        resp = self.client.post(
            "/api/task-templates/apply/", {"date": "bad"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class SummaryEndpointTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.item = make_item("Food")
        make_expense(self.user, self.item, "40.00", date(2026, 6, 5))
        make_income(self.user, "Salary", "1000.00", date(2026, 6, 1))

    def test_daily_summary_ok(self):
        resp = self.client.get("/api/summary/daily/?date=2026-06-05")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["day_total"], "40.00")

    def test_daily_summary_bad_date_400(self):
        resp = self.client.get("/api/summary/daily/?date=oops")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_monthly_summary_shape_and_income_excluded(self):
        resp = self.client.get("/api/summary/monthly/?month=2026-06")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("month_total", "income_total", "saving_total",
                    "balance", "items", "incomes"):
            self.assertIn(key, resp.data)
        self.assertEqual(resp.data["month_total"], "40.00")   # income excluded
        self.assertEqual(resp.data["income_total"], "1000.00")

    def test_monthly_summary_bad_month_400(self):
        resp = self.client.get("/api/summary/monthly/?month=oops")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_range_summary_requires_params(self):
        resp = self.client.get("/api/summary/range/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_range_summary_from_after_to_400(self):
        resp = self.client.get(
            "/api/summary/range/?from=2026-06-30&to=2026-06-01"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_balance_then_overview(self):
        resp = self.client.post(
            "/api/summary/balance/set/",
            {"year": 2026, "month": 6, "amount": "500.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        june = next(m for m in resp.data["months"] if m["month_num"] == 6)
        self.assertEqual(june["balance_input"], "500.00")
        self.assertEqual(june["remaining"], "460.00")  # 500 - 40

    def test_set_balance_bad_month_400(self):
        resp = self.client.post(
            "/api/summary/balance/set/",
            {"year": 2026, "month": 13, "amount": "500.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_week_summary_ok(self):
        make_task(self.user, "A", date(2026, 1, 5), WeeklyTask.STATUS_SUCCESS)
        resp = self.client.get("/api/tasks/summary/?week=2026-01-07")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["week_start"], "2026-01-05")
        self.assertEqual(resp.data["total_tasks"], 1)

    def test_saving_summary_ok(self):
        resp = self.client.get("/api/savings/summary/?year=2026")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("year_total", resp.data)
