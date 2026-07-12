"""Backhaul / trip-chain pairing — reuses rank_loads, no second formula stack."""

from __future__ import annotations

from dataclasses import dataclass

from apps.scoring.engine import AVG_SPEED_MPH, LoadInput, TruckInput, rank_loads
from integrations.distance import haversine_miles


@dataclass(frozen=True)
class TripPair:
    outbound_id: int
    return_id: int
    combined_score: float
    total_deadhead_miles: float
    total_hours: float
    total_rate_usd: float


def _leg_net(load: LoadInput, deadhead_mi: float, mpg: float, diesel: float) -> float:
    fuel = (deadhead_mi + load.miles) / mpg * diesel if mpg > 0 else 0.0
    return load.rate_usd - fuel


def best_backhaul_pair(
    truck: TruckInput,
    outbound: LoadInput,
    candidates: list[LoadInput],
    diesel_usd_per_gal: float,
    radius_miles: float = 75.0,
) -> TripPair | None:
    deadhead1 = haversine_miles(truck.lat, truck.lon, outbound.origin_lat, outbound.origin_lon)
    hours_used = deadhead1 / AVG_SPEED_MPH + outbound.est_transit_hours
    remaining = truck.hos_hours_remaining - hours_used
    if remaining <= 0:
        return None

    nearby = [
        l
        for l in candidates
        if l.id != outbound.id
        and l.equipment_type == truck.equipment_type
        and haversine_miles(l.origin_lat, l.origin_lon, outbound.dest_lat, outbound.dest_lon)
        <= radius_miles
        and l.est_transit_hours <= remaining
    ]
    if not nearby:
        return None

    truck_after = TruckInput(
        id=truck.id,
        equipment_type=truck.equipment_type,
        lat=outbound.dest_lat,
        lon=outbound.dest_lon,
        mpg=truck.mpg,
        hos_hours_remaining=remaining,
        preferred_markets=truck.preferred_markets,
        no_go_markets=truck.no_go_markets,
    )
    ranked_returns = rank_loads(truck_after, nearby, diesel_usd_per_gal)
    if not ranked_returns:
        return None

    best_return_id = ranked_returns[0].load_id
    ret = next(l for l in nearby if l.id == best_return_id)
    deadhead2 = haversine_miles(
        outbound.dest_lat, outbound.dest_lon, ret.origin_lat, ret.origin_lon
    )
    total_hours = (
        hours_used + deadhead2 / AVG_SPEED_MPH + ret.est_transit_hours
    )
    if total_hours <= 0:
        return None

    net = _leg_net(outbound, deadhead1, truck.mpg, diesel_usd_per_gal) + _leg_net(
        ret, deadhead2, truck.mpg, diesel_usd_per_gal
    )
    combined = net / total_hours

    return TripPair(
        outbound_id=outbound.id,
        return_id=ret.id,
        combined_score=combined,
        total_deadhead_miles=deadhead1 + deadhead2,
        total_hours=total_hours,
        total_rate_usd=outbound.rate_usd + ret.rate_usd,
    )


def single_load_net_per_hour(
    truck: TruckInput, load: LoadInput, diesel_usd_per_gal: float
) -> float:
    """Same $/hr metric used by trip pairs — for apples-to-apples DoD compare."""
    deadhead = haversine_miles(truck.lat, truck.lon, load.origin_lat, load.origin_lon)
    hours = deadhead / AVG_SPEED_MPH + load.est_transit_hours
    if hours <= 0:
        return 0.0
    return _leg_net(load, deadhead, truck.mpg, diesel_usd_per_gal) / hours


def best_chain_for_top_outbounds(
    truck: TruckInput,
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    top_n: int = 5,
    radius_miles: float = 75.0,
) -> TripPair | None:
    ranked = rank_loads(truck, loads, diesel_usd_per_gal)[:top_n]
    by_id = {l.id: l for l in loads}
    best: TripPair | None = None
    for r in ranked:
        outbound = by_id[r.load_id]
        pair = best_backhaul_pair(
            truck, outbound, loads, diesel_usd_per_gal, radius_miles=radius_miles
        )
        if pair and (best is None or pair.combined_score > best.combined_score):
            best = pair
    return best


def pair_beats_best_single(
    truck: TruckInput,
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    pair: TripPair | None,
) -> bool:
    if not pair:
        return False
    ranked = rank_loads(truck, loads, diesel_usd_per_gal)
    if not ranked:
        return False
    by_id = {l.id: l for l in loads}
    single = single_load_net_per_hour(truck, by_id[ranked[0].load_id], diesel_usd_per_gal)
    return pair.combined_score > single