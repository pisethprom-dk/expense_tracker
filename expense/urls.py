# v1.9.0
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from . import auth_views

router = DefaultRouter()
router.register(r"items", views.ExpenseItemViewSet, basename="expense-item")
router.register(r"records", views.ExpenseRecordViewSet, basename="expense-record")
router.register(r"incomes", views.IncomeRecordViewSet, basename="income-record")
router.register(r"savings", views.SavingRecordViewSet, basename="saving-record")
router.register(r"tasks", views.WeeklyTaskViewSet, basename="weekly-task")

urlpatterns = [
    # specific summary routes FIRST
    path("auth/login/", auth_views.login, name="api-login"),
    path("auth/logout/", auth_views.logout, name="api-logout"),
    path("auth/me/", auth_views.me, name="api-me"),
    path("summary/daily/", views.daily_summary, name="daily-summary"),
    path("summary/monthly/", views.monthly_summary, name="monthly-summary"),
    path("summary/range/", views.range_summary, name="range-summary"),
    path("summary/balance/", views.balance_overview, name="balance-overview"),
    path("summary/balance/set/", views.set_balance, name="balance-set"),
    path("savings/summary/", views.saving_summary, name="saving-summary"),
    path("tasks/summary/", views.week_summary, name="week-summary"),

    # router LAST so its <pk> routes don't shadow the above
    path("", include(router.urls)),
]
