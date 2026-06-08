# v1.1.0
from django.contrib import admin

from .models import ExpenseItem, ExpenseRecord, IncomeRecord


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
