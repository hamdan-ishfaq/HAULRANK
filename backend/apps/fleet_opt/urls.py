from django.urls import path

from .views import FleetOptimizeView

urlpatterns = [
    path("fleet/optimize/", FleetOptimizeView.as_view(), name="fleet-optimize"),
]
