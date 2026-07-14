from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fleet.models import Truck
from apps.fleet_opt.locks import locked_pairs_for_carrier
from apps.loads.models import Load
from apps.scoring.engine import LoadInput, TruckInput
from integrations.eia import get_diesel_usd_per_gal

from .service import run_copilot


def _truck_input(t: Truck) -> TruckInput:
    d = t.driver
    return TruckInput(
        id=t.id,
        equipment_type=t.equipment_type,
        lat=t.current_lat,
        lon=t.current_lon,
        mpg=t.mpg,
        hos_hours_remaining=d.hos_hours_remaining,
        preferred_markets=list(d.preferred_markets or []),
        no_go_markets=list(d.no_go_markets or []),
    )


class CopilotView(APIView):
    def post(self, request):
        message = (request.data.get("message") or "").strip()
        truck_id = request.data.get("truck_id") or request.query_params.get("truck_id")
        if not message:
            return Response({"detail": "message required"}, status=400)
        if not truck_id:
            return Response({"detail": "truck_id required"}, status=400)

        try:
            truck = Truck.objects.select_related("driver", "carrier").get(
                pk=truck_id, carrier__owner=request.user
            )
        except Truck.DoesNotExist:
            return Response({"detail": "Truck not found"}, status=404)
        if not hasattr(truck, "driver"):
            return Response({"detail": "Truck has no driver"}, status=400)

        truck_in = _truck_input(truck)
        fleet_qs = (
            Truck.objects.filter(carrier__owner=request.user)
            .select_related("driver")
            .order_by("id")
        )
        trucks_in = [_truck_input(t) for t in fleet_qs if hasattr(t, "driver")]
        load_ins = [
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
            for l in Load.objects.all()
        ]

        try:
            result = run_copilot(
                message,
                truck_in,
                load_ins,
                get_diesel_usd_per_gal(),
                trucks=trucks_in,
                locked_pairs=locked_pairs_for_carrier(request.user),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=422)
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            return Response(
                {"detail": "Copilot unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result)
