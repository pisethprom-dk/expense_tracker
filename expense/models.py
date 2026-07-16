# v1.11.0
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


class MonthlyBalance(models.Model):
    """User-entered balance for a given month. remaining = amount - spent."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="monthly_balances", null=True, blank=True,
    )
    year = models.IntegerField()
    month = models.IntegerField()  # 1-12
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "monthly_balance"
        ordering = ["-year", "-month"]
        unique_together = ("user", "year", "month")

    def __str__(self):
        return f"{self.year}-{self.month:02d} : {self.amount}"


class SavingRecord(models.Model):
    """A money-saving entry (money set aside)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="saving_records", null=True, blank=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    saving_date = models.DateField(db_index=True)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "saving_record"
        ordering = ["-saving_date", "-created_at"]

    def __str__(self):
        return f"{self.saving_date} - {self.amount}"


class WeeklyTask(models.Model):
    """A task planned for a specific day. Week = Mon-Sun containing task_date."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="weekly_tasks", null=True, blank=True,
    )
    title = models.CharField(max_length=255)
    task_date = models.DateField(db_index=True)
    is_done = models.BooleanField(default=False)
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    note = models.CharField(max_length=255, blank=True, default="")
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weekly_task"
        ordering = ["task_date", "order", "created_at"]

    def __str__(self):
        return f"{self.task_date} - {'[x]' if self.is_done else '[ ]'} {self.title}"


class TaskTemplate(models.Model):
    """A reusable daily task. Templates can be applied to a day/week to
    generate WeeklyTask entries that repeat every day."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="task_templates", null=True, blank=True,
    )
    title = models.CharField(max_length=255)
    note = models.CharField(max_length=255, blank=True, default="")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_template"
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.title


class MonthlyTask(models.Model):
    """A task planned for a specific month. Year view = 12 months of a year."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="monthly_tasks", null=True, blank=True,
    )
    title = models.CharField(max_length=255)
    year = models.IntegerField()
    month = models.IntegerField()  # 1-12
    is_done = models.BooleanField(default=False)
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    note = models.CharField(max_length=255, blank=True, default="")
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monthly_task"
        ordering = ["year", "month", "order", "created_at"]

    def __str__(self):
        return f"{self.year}-{self.month:02d} - {'[x]' if self.is_done else '[ ]'} {self.title}"
