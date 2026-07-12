from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated

from .models import Load
from .serializers import LoadSerializer


class IsStaffOrReadOnly(BasePermission):
    """Synthetic board: carriers may list; only staff may mutate."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class LoadViewSet(viewsets.ModelViewSet):
    serializer_class = LoadSerializer
    queryset = Load.objects.all().order_by("id")
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        equipment = self.request.query_params.get("equipment_type")
        market = self.request.query_params.get("dest_market")
        if equipment:
            qs = qs.filter(equipment_type=equipment)
        if market:
            qs = qs.filter(dest_market=market)
        return qs
