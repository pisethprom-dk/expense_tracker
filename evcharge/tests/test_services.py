# v1.0.1
from decimal import Decimal

from django.test import TestCase

from expense.models import ExpenseRecord
from expense.tests.factories import make_user
from evcharge import services
from evcharge.models import ChargingRecord

from .factories import make_vehicle, make_charge, MAR, APR


class ComputeTotalsTests(TestCase):
    def test_basic_calculation(self):
        # 60% of a 75 kWh pack = 45 kWh; at $0.25 = $11.25
        total_kwh, total_price = services.compute_totals(
            Decimal("20"), Decimal("80"), Decimal("75.00"), Decimal("0.2500")
        )
        self.assertEqual(total_kwh, Decimal("45.000"))
        self.assertEqual(total_price, Decimal("11.25"))

    def test_full_charge_uses_whole_capacity(self):
        total_kwh, _ = services.compute_totals(
            Decimal("0"), Decimal("100"), Decimal("64.50"), Decimal("0.3000")
        )
        self.assertEqual(total_kwh, Decimal("64.500"))

    def test_fractional_price_rounds_to_cents(self):
        # 30% of 40 kWh = 12 kWh at $0.2875 = $3.45
        total_kwh, total_price = services.compute_totals(
            Decimal("50"), Decimal("80"), Decimal("40.00"), Decimal("0.2875")
        )
        self.assertEqual(total_kwh, Decimal("12.000"))
        self.assertEqual(total_price, Decimal("3.45"))


class ChargingRecordSaveTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(self.user)

    def test_totals_are_persisted(self):
        record = make_charge(self.user, self.vehicle)
        self.assertEqual(record.total_kwh, Decimal("45.000"))
        self.assertEqual(record.total_price, Decimal("11.25"))

    def test_capacity_is_snapshotted(self):
        record = make_charge(self.user, self.vehicle)
        self.assertEqual(record.battery_capacity_kwh, Decimal("75.00"))

    def test_editing_vehicle_capacity_does_not_reprice_history(self):
        record = make_charge(self.user, self.vehicle)
        self.vehicle.battery_capacity_kwh = Decimal("100.00")
        self.vehicle.save()
        record.refresh_from_db()
        self.assertEqual(record.total_kwh, Decimal("45.000"))
        self.assertEqual(record.total_price, Decimal("11.25"))


class ExpenseSyncTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(self.user)

    def test_creates_linked_expense(self):
        record = make_charge(self.user, self.vehicle)
        self.assertIsNotNone(record.expense_record)
        expense = record.expense_record
        self.assertEqual(expense.amount, Decimal("11.25"))
        self.assertEqual(expense.expense_date, MAR)
        self.assertEqual(expense.item.item_name, services.EV_EXPENSE_ITEM_NAME)
        self.assertEqual(expense.user, self.user)

    def test_remark_describes_the_session(self):
        record = make_charge(self.user, self.vehicle)
        self.assertIn("EV charge", record.expense_record.remark)
        self.assertIn("Tesla", record.expense_record.remark)
        self.assertIn("Toul Kork", record.expense_record.remark)

    def test_ev_item_is_reused_not_duplicated(self):
        make_charge(self.user, self.vehicle)
        make_charge(self.user, self.vehicle, on=APR)
        from expense.models import ExpenseItem
        self.assertEqual(
            ExpenseItem.objects.filter(
                item_name=services.EV_EXPENSE_ITEM_NAME
            ).count(),
            1,
        )

    def test_update_repushes_amount_to_expense(self):
        record = make_charge(self.user, self.vehicle)
        record.end_percent = Decimal("100")
        services.save_charging_record(record)
        record.expense_record.refresh_from_db()
        # 80% of 75 = 60 kWh at $0.25 = $15.00
        self.assertEqual(record.total_kwh, Decimal("60.000"))
        self.assertEqual(record.expense_record.amount, Decimal("15.00"))

    def test_delete_removes_the_linked_expense(self):
        record = make_charge(self.user, self.vehicle)
        services.delete_charging_record(record)
        self.assertEqual(ChargingRecord.objects.count(), 0)
        self.assertEqual(ExpenseRecord.objects.count(), 0)

    def test_lost_link_is_recreated_on_next_save(self):
        record = make_charge(self.user, self.vehicle)
        record.expense_record.delete()
        record.refresh_from_db()
        self.assertIsNone(record.expense_record)
        services.save_charging_record(record)
        self.assertIsNotNone(record.expense_record)


class ReportTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user(username="other")
        self.tesla = make_vehicle(self.user, brand="Tesla", capacity="75.00")
        self.byd = make_vehicle(
            self.user, brand="BYD", capacity="60.00", plate="2BB-5678"
        )

    def test_monthly_totals_and_vehicle_breakdown(self):
        make_charge(self.user, self.tesla, on=MAR)              # 45 kWh / 11.25
        make_charge(self.user, self.byd, start="50", end="100",
                    price="0.3000", on=MAR)                     # 30 kWh / 9.00
        make_charge(self.user, self.tesla, on=APR)              # different month

        data = services.get_monthly_ev_summary(2026, 3, user=self.user)
        self.assertEqual(data["month"], "2026-03")
        self.assertEqual(data["session_count"], 2)
        self.assertEqual(data["total_kwh"], "75.000")
        self.assertEqual(data["total_price"], "20.25")
        self.assertEqual(len(data["vehicles"]), 2)
        # ordered by spend, biggest first
        self.assertEqual(data["vehicles"][0]["brand"], "Tesla")
        self.assertEqual(data["vehicles"][0]["total_price"], "11.25")

    def test_empty_month_returns_zeroes(self):
        data = services.get_monthly_ev_summary(2026, 7, user=self.user)
        self.assertEqual(data["session_count"], 0)
        self.assertEqual(data["total_kwh"], "0.000")
        self.assertEqual(data["total_price"], "0.00")
        self.assertEqual(data["vehicles"], [])

    def test_yearly_rollup_lists_only_months_with_activity(self):
        make_charge(self.user, self.tesla, on=MAR)
        make_charge(self.user, self.tesla, on=APR)
        data = services.get_yearly_ev_summary(2026, user=self.user)
        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["session_count"], 2)
        self.assertEqual(data["total_price"], "22.50")
        self.assertEqual([m["month_num"] for m in data["months"]], [3, 4])

    def test_two_sessions_in_one_month_collapse_to_one_row(self):
        # regression: Meta.ordering leaking into GROUP BY split these apart
        from datetime import date
        make_charge(self.user, self.tesla, on=date(2026, 3, 5))
        make_charge(self.user, self.tesla, on=date(2026, 3, 20))
        data = services.get_yearly_ev_summary(2026, user=self.user)
        self.assertEqual(len(data["months"]), 1)
        self.assertEqual(data["months"][0]["session_count"], 2)
        self.assertEqual(data["months"][0]["total_price"], "22.50")
        self.assertEqual(len(data["vehicles"]), 1)
        self.assertEqual(data["vehicles"][0]["session_count"], 2)

    def test_reports_are_scoped_to_the_user(self):
        other_vehicle = make_vehicle(self.other, brand="Nissan")
        make_charge(self.other, other_vehicle, on=MAR)
        data = services.get_monthly_ev_summary(2026, 3, user=self.user)
        self.assertEqual(data["session_count"], 0)
