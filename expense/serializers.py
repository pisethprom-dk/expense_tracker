# v1.11.0
from rest_framework import serializers

from .models import ExpenseItem, ExpenseRecord, IncomeRecord, SavingRecord, WeeklyTask, TaskTemplate, MonthlyTask


class ExpenseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseItem
        fields = ["id", "item_name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ExpenseRecordSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)

    class Meta:
        model = ExpenseRecord
        fields = [
            "id", "item", "item_name", "amount",
            "expense_date", "remark", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value


class IncomeRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeRecord
        fields = [
            "id", "income_source", "amount",
            "income_date", "remark", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value


class SavingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingRecord
        fields = ["id", "amount", "saving_date", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value


class WeeklyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyTask
        fields = ["id", "title", "task_date", "is_done", "status", "note", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class TaskTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskTemplate
        fields = ["id", "title", "note", "order", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class MonthlyTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyTask
        fields = ["id", "title", "year", "month", "is_done", "status", "note", "order", "created_at"]
        read_only_fields = ["id", "created_at"]
