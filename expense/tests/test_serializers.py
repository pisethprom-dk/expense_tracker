"""Validation tests: serializer rules (amount > 0) and DB-level constraints."""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from expense.models import ExpenseItem, MonthlyBalance
from expense.serializers import (
    ExpenseRecordSerializer,
    IncomeRecordSerializer,
    SavingRecordSerializer,
)
from .factories import make_user, make_item


class AmountValidationTests(TestCase):
    def setUp(self):
        self.item = make_item("Food")

    def test_expense_amount_must_be_positive(self):
        s = ExpenseRecordSerializer(data={
            "item": self.item.id, "amount": "-5.00",
            "expense_date": "2026-01-01",
        })
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_expense_amount_zero_rejected(self):
        s = ExpenseRecordSerializer(data={
            "item": self.item.id, "amount": "0.00",
            "expense_date": "2026-01-01",
        })
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_expense_amount_positive_ok(self):
        s = ExpenseRecordSerializer(data={
            "item": self.item.id, "amount": "5.00",
            "expense_date": "2026-01-01",
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_income_amount_must_be_positive(self):
        s = IncomeRecordSerializer(data={
            "income_source": "Salary", "amount": "-1.00",
            "income_date": "2026-01-01",
        })
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_saving_amount_must_be_positive(self):
        s = SavingRecordSerializer(data={
            "amount": "0", "saving_date": "2026-01-01",
        })
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)


class ConstraintTests(TestCase):
    def test_expense_item_name_is_unique(self):
        ExpenseItem.objects.create(item_name="Food")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseItem.objects.create(item_name="Food")

    def test_monthly_balance_unique_per_user_year_month(self):
        user = make_user()
        MonthlyBalance.objects.create(user=user, year=2026, month=6, amount="1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MonthlyBalance.objects.create(
                    user=user, year=2026, month=6, amount="2"
                )
