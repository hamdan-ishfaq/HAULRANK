"""Backhaul unit tests."""

from apps.backhaul.engine import best_backhaul_pair, best_chain_for_top_outbounds
from apps.scoring.engine import LoadInput, TruckInput


def truck(**kw):
    base = dict(
        id=1,
        equipment_type="dry_van",
        lat=32.7767,
        lon=-96.7970,
        mpg=6.5,
        hos_hours_remaining=14.0,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    base.update(kw)
    return TruckInput(**base)


def load(id_, **kw):
    base = dict(
        id=id_,
        origin_lat=32.7767,
        origin_lon=-96.7970,
        dest_lat=29.7604,
        dest_lon=-95.3698,
        dest_market="TX",
        miles=240.0,
        rate_usd=900.0,
        equipment_type="dry_van",
        est_transit_hours=4.5,
    )
    base.update(kw)
    return LoadInput(**base)


def test_pair_within_radius():
    outbound = load(1)
    ret = load(
        2,
        origin_lat=29.80,
        origin_lon=-95.40,
        dest_lat=32.78,
        dest_lon=-96.80,
        dest_market="TX",
        miles=240,
        rate_usd=850,
        est_transit_hours=4.5,
    )
    far = load(
        3,
        origin_lat=41.88,
        origin_lon=-87.63,
        dest_lat=32.78,
        dest_lon=-96.80,
        miles=900,
        rate_usd=3000,
        est_transit_hours=16,
    )
    pair = best_backhaul_pair(truck(), outbound, [outbound, ret, far], 3.8)
    assert pair is not None
    assert pair.return_id == 2


def test_outside_radius_no_pair():
    outbound = load(1)
    far = load(
        2,
        origin_lat=41.88,
        origin_lon=-87.63,
        dest_lat=32.78,
        dest_lon=-96.80,
        miles=900,
        rate_usd=3000,
        est_transit_hours=4,
    )
    assert best_backhaul_pair(truck(), outbound, [outbound, far], 3.8) is None


def test_hos_blocks_return():
    outbound = load(1, est_transit_hours=10)
    ret = load(
        2,
        origin_lat=29.80,
        origin_lon=-95.40,
        dest_lat=32.78,
        dest_lon=-96.80,
        est_transit_hours=8,
    )
    assert best_backhaul_pair(truck(hos_hours_remaining=11), outbound, [ret], 3.8) is None


def test_chain_beats_single_scenario():
    from apps.backhaul.engine import pair_beats_best_single, single_load_net_per_hour

    t = truck(hos_hours_remaining=16)
    outbound = load(1, rate_usd=700, miles=240)
    strong_return = load(
        2,
        origin_lat=29.78,
        origin_lon=-95.38,
        dest_lat=32.78,
        dest_lon=-96.80,
        miles=240,
        rate_usd=1100,
        est_transit_hours=4.5,
    )
    loads = [outbound, strong_return]
    pair = best_chain_for_top_outbounds(t, loads, 3.8)
    assert pair is not None
    assert pair.outbound_id == 1
    assert pair.return_id == 2
    assert pair.combined_score > single_load_net_per_hour(t, outbound, 3.8)
    assert pair_beats_best_single(t, loads, 3.8, pair) is True
