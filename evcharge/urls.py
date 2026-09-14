# v1.0.0
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"vehicles", views.VehicleViewSet, basename="ev-vehicle")
router.register(r"charges", views.ChargingRecordViewSet, basename="ev-charge")

urlpatterns = [
    # specific summary routes FIRST
    path("summary/monthly/", views.monthly_ev_summary, name="ev-monthly-summary"),
    path("summary/yearly/", views.yearly_ev_summary, name="ev-yearly-summary"),

    # router LAST so its <pk> routes don't shadow the above
    path("", include(router.urls)),
]
