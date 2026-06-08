# v1.2.0
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from . import auth_views

router = DefaultRouter()
router.register(r"items", views.ExpenseItemViewSet, basename="expense-item")
router.register(r"records", views.ExpenseRecordViewSet, basename="expense-record")
router.register(r"incomes", views.IncomeRecordViewSet, basename="income-record")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", auth_views.login, name="api-login"),
    path("auth/logout/", auth_views.logout, name="api-logout"),
    path("auth/me/", auth_views.me, name="api-me"),
    path("summary/daily/", views.daily_summary, name="daily-summary"),
    path("summary/monthly/", views.monthly_summary, name="monthly-summary"),
    path("summary/range/", views.range_summary, name="range-summary"),
]
