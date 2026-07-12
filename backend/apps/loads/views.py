from rest_framework import viewsets

from .models import Load
from .serializers import LoadSerializer


class LoadViewSet(viewsets.ModelViewSet):
    serializer_class = LoadSerializer
    queryset = Load.objects.all().order_by("id")

    def get_queryset(self):
        qs = super().get_queryset()
        equipment = self.request.query_params.get("equipment_type")
        market = self.request.query_params.get("dest_market")
        if equipment:
            qs = qs.filter(equipment_type=equipment)
        if market:
            qs = qs.filter(dest_market=market)
        return qs
