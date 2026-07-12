from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from .models import Truck
from .serializers import TruckSerializer


class TruckViewSet(viewsets.ModelViewSet):
    serializer_class = TruckSerializer

    def get_queryset(self):
        return Truck.objects.filter(carrier__owner=self.request.user).select_related(
            "driver", "carrier"
        )

    def perform_create(self, serializer):
        carrier = getattr(self.request.user, "carrier", None)
        if carrier is None:
            raise PermissionDenied("User has no carrier.")
        serializer.save(carrier=carrier)
