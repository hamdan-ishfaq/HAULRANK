import hashlib

from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.backhaul.engine import best_chain_for_top_outbounds
from apps.backhaul.models import TripChain
from apps.fleet.models import Truck
from apps.fleet.reliability import eligible_for_high_value, reliability_score
from apps.loads.models import Load
from apps.rates.models import LaneRateHistory, benchmark
from apps.scoring.engine import LoadInput, TruckInput, rank_loads
from apps.scoring.models import ScoreBreakdown, ScoreRun
from apps.weather.service import annotate_weather
from django.conf import settings
from integrations.eia import get_diesel_usd_per_gal

CACHE_TTL = 120


def _loads_hash(load_ids: list[int]) -> str:
    raw = ",".join(str(i) for i in sorted(load_ids))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class RankView(APIView):
    def post(self, request):
        truck_id = request.query_params.get("truck_id") or request.data.get("truck_id")
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

        loads = list(Load.objects.all())
        load_ids = [l.id for l in loads]
        cache_key = f"rank:{truck.id}:{_loads_hash(load_ids)}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        diesel = get_diesel_usd_per_gal()
        driver = truck.driver
        truck_in = TruckInput(
            id=truck.id,
            equipment_type=truck.equipment_type,
            lat=truck.current_lat,
            lon=truck.current_lon,
            mpg=truck.mpg,
            hos_hours_remaining=driver.hos_hours_remaining,
            preferred_markets=list(driver.preferred_markets or []),
            no_go_markets=list(driver.no_go_markets or []),
        )
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
            for l in loads
        ]
        ranked = rank_loads(truck_in, load_ins, diesel)
        pair = best_chain_for_top_outbounds(truck_in, load_ins, diesel)
        # Live weather via Open-Meteo (no key). Demo only if WEATHER_DEMO=1.
        demo_id = None
        if getattr(settings, "WEATHER_DEMO", False) and ranked:
            demo_id = ranked[0].load_id
        weather_rows = {
            w["load_id"]: w
            for w in annotate_weather(load_ins, ranked, demo_load_id=demo_id)
        }

        # Rate benchmarks by dest market
        history_by_market: dict[str, list[float]] = {}
        for row in LaneRateHistory.objects.all():
            history_by_market.setdefault(row.dest_market, []).append(row.avg_rate_per_mile)
        load_by_id = {l.id: l for l in loads}

        driver_rel = reliability_score(
            driver.hos_violations_90d,
            driver.inspection_pass_rate,
            driver.on_time_pct,
        )

        with transaction.atomic():
            run = ScoreRun.objects.create(truck=truck, diesel_usd_per_gal=diesel)
            results = []
            for i, r in enumerate(ranked, start=1):
                load_obj = load_by_id[r.load_id]
                bench = benchmark(
                    r.rate_per_mile,
                    history_by_market.get(load_obj.dest_market, []),
                )
                # small weight blend: nudge overall by z-score (capped)
                overall = r.overall + max(-0.05, min(0.05, bench["z_score"] * 0.02))
                gated = not eligible_for_high_value(driver_rel, load_obj.rate_usd)

                ScoreBreakdown.objects.create(
                    score_run=run,
                    load_id=r.load_id,
                    rate_per_mile_score=r.rate_per_mile_score,
                    deadhead_penalty=r.deadhead_penalty,
                    fuel_efficiency_score=r.fuel_efficiency_score,
                    hos_feasibility=r.hos_feasibility,
                    market_preference_score=r.market_preference_score,
                    overall=overall,
                    deadhead_miles=r.deadhead_miles,
                    rate_per_mile=r.rate_per_mile,
                    rank=i,
                )
                results.append(
                    {
                        "rank": i,
                        "load_id": r.load_id,
                        "overall": overall,
                        "rate_per_mile_score": r.rate_per_mile_score,
                        "deadhead_penalty": r.deadhead_penalty,
                        "fuel_efficiency_score": r.fuel_efficiency_score,
                        "hos_feasibility": r.hos_feasibility,
                        "market_preference_score": r.market_preference_score,
                        "deadhead_miles": r.deadhead_miles,
                        "rate_per_mile": r.rate_per_mile,
                        "weather_risk": weather_rows.get(r.load_id, {}).get(
                            "weather_risk", False
                        ),
                        "weather_reason": weather_rows.get(r.load_id, {}).get(
                            "weather_reason", ""
                        ),
                        "overall_adjusted": weather_rows.get(r.load_id, {}).get(
                            "overall_adjusted", overall
                        ),
                        "rate_benchmark": bench,
                        "compliance_gated": gated,
                        "driver_reliability": driver_rel,
                    }
                )
            # drop gated high-value loads from visible ranking (still auditable via field)
            results = [row for row in results if not row["compliance_gated"]]
            for i, row in enumerate(results, start=1):
                row["rank"] = i
            best_pair = None
            if pair:
                TripChain.objects.create(
                    outbound_id=pair.outbound_id,
                    return_load_id=pair.return_id,
                    combined_score=pair.combined_score,
                    total_deadhead_miles=pair.total_deadhead_miles,
                    total_hours=pair.total_hours,
                    total_rate_usd=pair.total_rate_usd,
                )
                best_pair = {
                    "outbound_id": pair.outbound_id,
                    "return_id": pair.return_id,
                    "combined_score": pair.combined_score,
                    "total_deadhead_miles": pair.total_deadhead_miles,
                    "total_hours": pair.total_hours,
                    "total_rate_usd": pair.total_rate_usd,
                }

        payload = {
            "score_run_id": run.id,
            "truck_id": truck.id,
            "diesel_usd_per_gal": diesel,
            "results": results,
            "best_single": results[0] if results else None,
            "best_pair": best_pair,
        }
        cache.set(cache_key, payload, CACHE_TTL)
        return Response(payload, status=status.HTTP_201_CREATED)
