from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TruckViewSet

router = DefaultRouter()
router.register("trucks", TruckViewSet, basename="truck")

urlpatterns = [
    path("", include(router.urls)),
]
