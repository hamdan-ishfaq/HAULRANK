from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fleet.models import Truck
from apps.fleet_opt.engine import optimize_fleet
from apps.loads.models import Load
from apps.scoring.engine import LoadInput, TruckInput
from integrations.eia import get_diesel_usd_per_gal


class FleetOptimizeView(APIView):
    def post(self, request):
        qs = (
            Truck.objects.filter(carrier__owner=request.user)
            .select_related("driver", "carrier")
            .order_by("id")
        )
        trucks_in: list[TruckInput] = []
        for t in qs:
            if not hasattr(t, "driver"):
                continue
            d = t.driver
            trucks_in.append(
                TruckInput(
                    id=t.id,
                    equipment_type=t.equipment_type,
                    lat=t.current_lat,
                    lon=t.current_lon,
                    mpg=t.mpg,
                    hos_hours_remaining=d.hos_hours_remaining,
                    preferred_markets=list(d.preferred_markets or []),
                    no_go_markets=list(d.no_go_markets or []),
                )
            )
        loads = [
            LoadInput(
                id=l.id,
                origin_lat=l.origin_lat,
                origin_lon=l.origin_lon,
                dest_lat=l.dest_lat,
                dest_lon=l.dest_lon,
                dest_market=l.dest_market,
                miles=l.miles,
                rate_usd=l.rate_usd,
                equipment_type=l.equipment_type,
                est_transit_hours=l.est_transit_hours,
            )
            for l in Load.objects.all().order_by("id")
        ]
        diesel = get_diesel_usd_per_gal()
        pairs = optimize_fleet(trucks_in, loads, diesel)
        return Response(
            {
                "diesel_usd_per_gal": diesel,
                "assignments": [
                    {"truck_id": p.truck_id, "load_id": p.load_id, "score": p.score}
                    for p in pairs
                ],
            }
        )
