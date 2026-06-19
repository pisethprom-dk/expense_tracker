# v1.9.0
from django.contrib import admin

from .models import ExpenseItem, ExpenseRecord, IncomeRecord, MonthlyBalance, SavingRecord, WeeklyTask


@admin.register(ExpenseItem)
class ExpenseItemAdmin(admin.ModelAdmin):
    list_display = ["id", "item_name", "is_active", "created_at"]
    search_fields = ["item_name"]
    list_filter = ["is_active"]


@admin.register(ExpenseRecord)
class ExpenseRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "expense_date", "item", "amount", "remark"]
    list_filter = ["expense_date", "item"]
    date_hierarchy = "expense_date"


@admin.register(IncomeRecord)
class IncomeRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "income_date", "income_source", "amount", "remark"]
    list_filter = ["income_date"]
    date_hierarchy = "income_date"


@admin.register(MonthlyBalance)
class MonthlyBalanceAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "year", "month", "amount", "updated_at"]
    list_filter = ["year", "month"]


@admin.register(SavingRecord)
class SavingRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "saving_date", "amount", "note", "user"]
    list_filter = ["saving_date"]
    date_hierarchy = "saving_date"


@admin.register(WeeklyTask)
class WeeklyTaskAdmin(admin.ModelAdmin):
    list_display = ["id", "task_date", "title", "is_done", "user"]
    list_filter = ["task_date", "is_done"]
    date_hierarchy = "task_date"
