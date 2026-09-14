# v1.0.0
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from expense.models import ExpenseRecord
from expense.tests.factories import make_user
from evcharge.models import ChargingRecord

from .factories import make_vehicle, make_charge, MAR, APR


class AuthMixin:
    def auth(self, user):
        self.client.force_authenticate(user=user)


class VehicleApiTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user(username="other")
        self.auth(self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/ev/vehicles/")
        self.assertEqual(response.status_code, 401)

    def test_create_vehicle(self):
        response = self.client.post("/api/ev/vehicles/", {
            "brand": "BYD",
            "plate_number": "2BB-5678",
            "color": "Blue",
            "battery_capacity_kwh": "60.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["brand"], "BYD")
        self.assertEqual(response.data["display_name"], "BYD (2BB-5678)")

    def test_optional_fields_may_be_omitted(self):
        response = self.client.post("/api/ev/vehicles/", {
            "brand": "VinFast",
            "battery_capacity_kwh": "42.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["plate_number"], "")
        self.assertEqual(response.data["color"], "")

    def test_capacity_must_be_positive(self):
        response = self.client.post("/api/ev/vehicles/", {
            "brand": "Ghost", "battery_capacity_kwh": "0",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("battery_capacity_kwh", response.data)

    def test_only_own_vehicles_are_listed(self):
        make_vehicle(self.user, brand="Tesla")
        make_vehicle(self.other, brand="Nissan")
        response = self.client.get("/api/ev/vehicles/")
        brands = [v["brand"] for v in response.data]
        self.assertEqual(brands, ["Tesla"])

    def test_active_filter(self):
        make_vehicle(self.user, brand="Tesla", is_active=True)
        make_vehicle(self.user, brand="Old Leaf", plate="", is_active=False)
        response = self.client.get("/api/ev/vehicles/?active=true")
        self.assertEqual([v["brand"] for v in response.data], ["Tesla"])


class ChargingRecordApiTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user(username="other")
        self.vehicle = make_vehicle(self.user)
        self.auth(self.user)

    def _payload(self, **overrides):
        data = {
            "vehicle": self.vehicle.id,
            "charger_type": "DC",
            "charge_date": "2026-03-15",
            "location": "Toul Kork",
            "start_percent": "20",
            "end_percent": "80",
            "price_per_kwh": "0.2500",
        }
        data.update(overrides)
        return data

    def test_create_computes_totals(self):
        response = self.client.post(
            "/api/ev/charges/", self._payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total_kwh"], "45.000")
        self.assertEqual(response.data["total_price"], "11.25")
        self.assertEqual(response.data["battery_capacity_kwh"], "75.00")
        self.assertIsNotNone(response.data["expense_record_id"])

    def test_charge_date_defaults_to_today(self):
        payload = self._payload()
        payload.pop("charge_date")
        response = self.client.post("/api/ev/charges/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.data["charge_date"])

    def test_end_must_exceed_start(self):
        response = self.client.post(
            "/api/ev/charges/",
            self._payload(start_percent="80", end_percent="80"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_percent", response.data)

    def test_percent_above_100_rejected(self):
        response = self.client.post(
            "/api/ev/charges/",
            self._payload(end_percent="120"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_zero_price_rejected(self):
        response = self.client.post(
            "/api/ev/charges/",
            self._payload(price_per_kwh="0"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("price_per_kwh", response.data)

    def test_cannot_charge_another_users_vehicle(self):
        foreign = make_vehicle(self.other, brand="Nissan")
        response = self.client.post(
            "/api/ev/charges/", self._payload(vehicle=foreign.id), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_update_recomputes_and_syncs(self):
        record = make_charge(self.user, self.vehicle)
        response = self.client.patch(
            "/api/ev/charges/%d/" % record.id,
            {"end_percent": "100"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_price"], "15.00")
        record.expense_record.refresh_from_db()
        self.assertEqual(record.expense_record.amount, Decimal("15.00"))

    def test_delete_removes_expense_too(self):
        record = make_charge(self.user, self.vehicle)
        response = self.client.delete("/api/ev/charges/%d/" % record.id)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(ChargingRecord.objects.count(), 0)
        self.assertEqual(ExpenseRecord.objects.count(), 0)

    def test_filter_by_vehicle_and_type(self):
        byd = make_vehicle(self.user, brand="BYD", capacity="60.00", plate="2BB")
        make_charge(self.user, self.vehicle, charger_type="AC")
        make_charge(self.user, byd, charger_type="DC")

        response = self.client.get("/api/ev/charges/?vehicle=%d" % byd.id)
        self.assertEqual(len(response.data), 1)

        response = self.client.get("/api/ev/charges/?charger_type=DC")
        self.assertEqual(len(response.data), 1)

    def test_filter_by_month(self):
        make_charge(self.user, self.vehicle, on=MAR)
        make_charge(self.user, self.vehicle, on=APR)
        response = self.client.get("/api/ev/charges/?month=2026-03")
        self.assertEqual(len(response.data), 1)

    def test_bad_filter_returns_400_not_everything(self):
        make_charge(self.user, self.vehicle)
        response = self.client.get("/api/ev/charges/?month=garbage")
        self.assertEqual(response.status_code, 400)

    def test_only_own_records_listed(self):
        foreign = make_vehicle(self.other, brand="Nissan")
        make_charge(self.other, foreign)
        response = self.client.get("/api/ev/charges/")
        self.assertEqual(len(response.data), 0)


class SummaryApiTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(self.user)
        self.auth(self.user)

    def test_monthly_summary(self):
        make_charge(self.user, self.vehicle, on=MAR)
        response = self.client.get("/api/ev/summary/monthly/?month=2026-03")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_price"], "11.25")
        self.assertEqual(len(response.data["vehicles"]), 1)

    def test_monthly_summary_bad_month(self):
        response = self.client.get("/api/ev/summary/monthly/?month=nope")
        self.assertEqual(response.status_code, 400)

    def test_yearly_summary(self):
        make_charge(self.user, self.vehicle, on=MAR)
        make_charge(self.user, self.vehicle, on=APR)
        response = self.client.get("/api/ev/summary/yearly/?year=2026")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_count"], 2)
        self.assertEqual(len(response.data["months"]), 2)

    def test_yearly_summary_bad_year(self):
        response = self.client.get("/api/ev/summary/yearly/?year=abcd")
        self.assertEqual(response.status_code, 400)

    def test_summary_requires_auth(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/ev/summary/monthly/").status_code, 401
        )


class LinkedExpenseGuardTests(AuthMixin, APITestCase):
    """An expense owned by a charging session is read-only from /api/records/."""

    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(self.user)
        self.auth(self.user)
        self.record = make_charge(self.user, self.vehicle)

    def test_linked_expense_cannot_be_updated(self):
        response = self.client.patch(
            "/api/records/%d/" % self.record.expense_record.id,
            {"amount": "1.00"}, format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.record.expense_record.refresh_from_db()
        self.assertEqual(self.record.expense_record.amount, Decimal("11.25"))

    def test_linked_expense_cannot_be_deleted(self):
        response = self.client.delete(
            "/api/records/%d/" % self.record.expense_record.id
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ExpenseRecord.objects.count(), 1)

    def test_is_linked_flag_exposed(self):
        response = self.client.get("/api/records/")
        self.assertTrue(response.data[0]["is_linked"])

    def test_unlinked_expense_still_editable(self):
        from expense.tests.factories import make_item, make_expense
        item = make_item("Coffee")
        plain = make_expense(self.user, item, "3.50", MAR)
        response = self.client.patch(
            "/api/records/%d/" % plain.id, {"amount": "4.00"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_linked"])
