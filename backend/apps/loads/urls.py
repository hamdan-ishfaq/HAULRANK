from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LoadViewSet

router = DefaultRouter()
router.register("loads", LoadViewSet, basename="load")

urlpatterns = [
    path("", include(router.urls)),
]
