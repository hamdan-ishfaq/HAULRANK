"""Pure scoring engine — no ORM, no LLM."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf

from integrations.distance import haversine_miles

WEIGHTS = {
    "rate": 0.30,
    "deadhead": 0.25,
    "fuel": 0.20,
    "hos": 0.15,
    "market": 0.10,
}
AVG_SPEED_MPH = 55.0


@dataclass(frozen=True)
class TruckInput:
    id: int
    equipment_type: str
    lat: float
    lon: float
    mpg: float
    hos_hours_remaining: float
    preferred_markets: list[str]
    no_go_markets: list[str]


@dataclass(frozen=True)
class LoadInput:
    id: int
    origin_lat: float
    origin_lon: float
    dest_market: str
    miles: float
    rate_usd: float
    equipment_type: str
    est_transit_hours: float


@dataclass(frozen=True)
class ScoreResult:
    load_id: int
    rate_per_mile_score: float
    deadhead_penalty: float
    fuel_efficiency_score: float
    hos_feasibility: float
    market_preference_score: float
    overall: float
    deadhead_miles: float
    rate_per_mile: float


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _market_raw(load: LoadInput, truck: TruckInput) -> float:
    if load.dest_market in truck.no_go_markets:
        return 0.0
    if load.dest_market in truck.preferred_markets:
        return 1.0
    return 0.5


def rank_loads(
    truck: TruckInput,
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    avg_speed_mph: float = AVG_SPEED_MPH,
) -> list[ScoreResult]:
    """Rank feasible, equipment-matching loads. HOS-infeasible loads are excluded."""
    candidates: list[tuple[LoadInput, float, float, float, float]] = []
    # tuple: load, rpm, deadhead_mi, net_after_fuel_per_mi, market_raw

    for load in loads:
        if load.equipment_type != truck.equipment_type:
            continue
        deadhead = haversine_miles(truck.lat, truck.lon, load.origin_lat, load.origin_lon)
        deadhead_hours = deadhead / avg_speed_mph if avg_speed_mph > 0 else inf
        if deadhead_hours + load.est_transit_hours > truck.hos_hours_remaining:
            continue  # hard filter
        rpm = load.rate_usd / load.miles if load.miles > 0 else 0.0
        fuel_cost_per_mi = diesel_usd_per_gal / truck.mpg if truck.mpg > 0 else 0.0
        net_per_mi = rpm - fuel_cost_per_mi
        market = _market_raw(load, truck)
        candidates.append((load, rpm, deadhead, net_per_mi, market))

    if not candidates:
        return []

    rpm_n = _minmax([c[1] for c in candidates])
    # less deadhead is better → invert after normalize
    dh_n = _minmax([c[2] for c in candidates])
    dh_inv = [1.0 - x for x in dh_n]
    fuel_n = _minmax([c[3] for c in candidates])
    market_n = _minmax([c[4] for c in candidates])
    # HOS already filtered; surviving loads get 1.0
    hos = 1.0

    results: list[ScoreResult] = []
    for i, (load, rpm, deadhead, _net, _m) in enumerate(candidates):
        overall = (
            WEIGHTS["rate"] * rpm_n[i]
            + WEIGHTS["deadhead"] * dh_inv[i]
            + WEIGHTS["fuel"] * fuel_n[i]
            + WEIGHTS["hos"] * hos
            + WEIGHTS["market"] * market_n[i]
        )
        results.append(
            ScoreResult(
                load_id=load.id,
                rate_per_mile_score=rpm_n[i],
                deadhead_penalty=dh_n[i],
                fuel_efficiency_score=fuel_n[i],
                hos_feasibility=hos,
                market_preference_score=market_n[i],
                overall=overall,
                deadhead_miles=deadhead,
                rate_per_mile=rpm,
            )
        )

    results.sort(key=lambda r: (-r.overall, r.load_id))
    return results
