import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.backhaul.engine import best_chain_for_top_outbounds, pair_beats_best_single
from apps.backhaul.models import TripChain
from apps.compliance.engine import CLEAR, SUSPENDED, WATCH
from apps.fleet.models import Truck
from apps.fleet.reliability import eligible_for_high_value
from apps.loads.models import Load
from apps.rates.models import LaneRateHistory, benchmark
from apps.scoring.engine import LoadInput, TruckInput, rank_loads
from apps.scoring.models import ScoreBreakdown, ScoreRun
from apps.weather.service import annotate_weather
from integrations.eia import get_diesel_usd_per_gal

CACHE_TTL = 120
logger = logging.getLogger(__name__)


def _rank_fingerprint(
    truck_in: TruckInput,
    loads: list[LoadInput],
    diesel: float,
    *,
    compliance_state: str,
) -> str:
    """Hash all fields that affect scoring/backhaul so rate edits bust the cache."""
    parts: list[str] = [
        f"t:{truck_in.id}:{truck_in.equipment_type}:{truck_in.lat:.5f}:{truck_in.lon:.5f}"
        f":{truck_in.mpg}:{truck_in.hos_hours_remaining}"
        f":{','.join(truck_in.preferred_markets)}:{','.join(truck_in.no_go_markets)}"
        f":cs:{compliance_state}",
        f"d:{round(diesel, 4)}",
    ]
    for l in sorted(loads, key=lambda x: x.id):
        parts.append(
            f"l:{l.id}:{l.origin_lat:.5f}:{l.origin_lon:.5f}:{l.dest_lat:.5f}:{l.dest_lon:.5f}"
            f":{l.dest_market}:{l.miles}:{l.rate_usd}:{l.equipment_type}:{l.est_transit_hours}"
        )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _cache_get(key: str):
    try:
        return cache.get(key)
    except Exception as exc:
        logger.warning("cache get failed for %s: %s", key, exc)
        return None


def _cache_set(key: str, value, ttl: int) -> None:
    try:
        cache.set(key, value, ttl)
    except Exception as exc:
        logger.warning("cache set failed for %s: %s", key, exc)


class RankView(APIView):
    def post(self, request):
        truck_id_raw = request.query_params.get("truck_id") or request.data.get("truck_id")
        if truck_id_raw is None or truck_id_raw == "":
            return Response({"detail": "truck_id required"}, status=400)
        try:
            truck_id = int(truck_id_raw)
        except (TypeError, ValueError):
            return Response({"detail": "truck_id must be an integer"}, status=400)

        try:
            truck = Truck.objects.select_related("driver", "carrier").get(
                pk=truck_id, carrier__owner=request.user
            )
        except Truck.DoesNotExist:
            return Response({"detail": "Truck not found"}, status=404)

        if not hasattr(truck, "driver"):
            return Response({"detail": "Truck has no driver"}, status=400)

        driver = truck.driver
        compliance_state = driver.compliance_state or CLEAR
        if compliance_state == SUSPENDED:
            return Response(
                {
                    "detail": "Driver compliance suspended — dispatch eligibility revoked",
                    "compliance_state": SUSPENDED,
                    "compliance_reason": driver.compliance_reason,
                    "driver_reliability": driver.reliability_score,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        loads = list(Load.objects.all())
        diesel = get_diesel_usd_per_gal()
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
        cache_key = (
            f"rank:{truck.id}:{_rank_fingerprint(truck_in, load_ins, diesel, compliance_state=compliance_state)}"
        )
        cached = _cache_get(cache_key)
        if cached:
            return Response(cached)

        ranked = rank_loads(truck_in, load_ins, diesel)
        pair = best_chain_for_top_outbounds(truck_in, load_ins, diesel)
        demo_id = None
        if getattr(settings, "WEATHER_DEMO", False) and ranked:
            demo_id = ranked[0].load_id
        weather_rows = {
            w["load_id"]: w
            for w in annotate_weather(load_ins, ranked, demo_load_id=demo_id)
        }

        history_by_market: dict[str, list[float]] = {}
        for row in LaneRateHistory.objects.all():
            history_by_market.setdefault(row.dest_market, []).append(row.avg_rate_per_mile)
        load_by_id = {l.id: l for l in loads}

        driver_rel = driver.reliability_score
        # State machine is source of truth after poll; score gate is defense-in-depth.
        high_value_ok = compliance_state in (CLEAR, WATCH)

        with transaction.atomic():
            run = ScoreRun.objects.create(truck=truck, diesel_usd_per_gal=diesel)
            results = []
            for i, r in enumerate(ranked, start=1):
                load_obj = load_by_id[r.load_id]
                bench = benchmark(
                    r.rate_per_mile,
                    history_by_market.get(load_obj.dest_market, []),
                )
                overall = r.overall + max(-0.05, min(0.05, bench["z_score"] * 0.02))
                gated = not (
                    high_value_ok and eligible_for_high_value(driver_rel, load_obj.rate_usd)
                )

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
                wx = weather_rows.get(r.load_id, {})
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
                        "weather_risk": wx.get("weather_risk", False),
                        "weather_status": wx.get("weather_status", "unavailable"),
                        "weather_reason": wx.get("weather_reason", ""),
                        "overall_adjusted": wx.get("overall_adjusted", overall),
                        "rate_benchmark": bench,
                        "compliance_gated": gated,
                        "compliance_state": compliance_state,
                        "driver_reliability": driver_rel,
                    }
                )
            results = [row for row in results if not row["compliance_gated"]]
            for i, row in enumerate(results, start=1):
                row["rank"] = i
            best_pair = None
            beats = (
                pair_beats_best_single(truck_in, load_ins, diesel, pair) if pair else False
            )
            if pair and beats:
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
                    "beats_best_single": True,
                    "metric": "net_usd_per_hour",
                }

        payload = {
            "score_run_id": run.id,
            "truck_id": truck.id,
            "diesel_usd_per_gal": diesel,
            "compliance_state": compliance_state,
            "results": results,
            "best_single": results[0] if results else None,
            "best_pair": best_pair,
        }
        _cache_set(cache_key, payload, CACHE_TTL)
        return Response(payload, status=status.HTTP_201_CREATED)
