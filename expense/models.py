# v1.1.0
from django.conf import settings
from django.db import models


class ExpenseItem(models.Model):
    """Master list of expense items/categories (e.g. Food, Transport)."""
    item_name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expense_item"
        ordering = ["item_name"]

    def __str__(self):
        return self.item_name


class ExpenseRecord(models.Model):
    """Daily expense record."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="expense_records", null=True, blank=True,
    )
    item = models.ForeignKey(
        ExpenseItem, on_delete=models.PROTECT, related_name="records"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(db_index=True)
    remark = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expense_record"
        ordering = ["-expense_date", "-created_at"]

    def __str__(self):
        return f"{self.expense_date} - {self.item.item_name} - {self.amount}"


class IncomeRecord(models.Model):
    """Income note only — NOT included in any expense calculation."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="income_records", null=True, blank=True,
    )
    income_source = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    income_date = models.DateField(db_index=True)
    remark = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "income_record"
        ordering = ["-income_date", "-created_at"]

    def __str__(self):
        return f"{self.income_date} - {self.income_source} - {self.amount}"
