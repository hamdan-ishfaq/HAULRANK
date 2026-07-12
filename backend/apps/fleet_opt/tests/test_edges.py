"""Extra edge cases: fleet opt, reliability gates, benchmarks."""

from apps.fleet.reliability import eligible_for_high_value, reliability_score
from apps.fleet_opt.engine import optimize_fleet
from apps.rates.models import benchmark
from apps.scoring.engine import LoadInput, TruckInput


def _truck(id_, **kw):
    base = dict(
        id=id_,
        equipment_type="dry_van",
        lat=32.78,
        lon=-96.80,
        mpg=6.5,
        hos_hours_remaining=11.0,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    base.update(kw)
    return TruckInput(**base)


def _load(id_, **kw):
    base = dict(
        id=id_,
        origin_lat=32.79,
        origin_lon=-96.81,
        dest_lat=29.7,
        dest_lon=-95.3,
        dest_market="TX",
        miles=200.0,
        rate_usd=900.0,
        equipment_type="dry_van",
        est_transit_hours=4.0,
    )
    base.update(kw)
    return LoadInput(**base)


def test_fleet_prefers_closer_truck_for_same_load_pool():
    # Truck 1 near Dallas loads; truck 2 near Houston origin load
    trucks = [
        _truck(1, lat=32.78, lon=-96.80),
        _truck(2, lat=29.76, lon=-95.37),
    ]
    loads = [
        _load(10, origin_lat=32.79, origin_lon=-96.81, rate_usd=1000),
        _load(11, origin_lat=29.77, origin_lon=-95.38, rate_usd=1000),
    ]
    pairs = {p.truck_id: p.load_id for p in optimize_fleet(trucks, loads, 3.8)}
    assert pairs.get(1) == 10
    assert pairs.get(2) == 11


def test_fleet_more_trucks_than_loads():
    trucks = [_truck(1), _truck(2), _truck(3)]
    loads = [_load(10), _load(11)]
    pairs = optimize_fleet(trucks, loads, 3.8)
    assert len(pairs) == 2
    assert len({p.load_id for p in pairs}) == 2


def test_fleet_hos_exhausted_gets_nothing():
    trucks = [_truck(1, hos_hours_remaining=0), _truck(2, hos_hours_remaining=11)]
    loads = [_load(10), _load(11)]
    pairs = optimize_fleet(trucks, loads, 3.8)
    assert all(p.truck_id != 1 for p in pairs)
    assert any(p.truck_id == 2 for p in pairs)


def test_reliability_bounds():
    assert reliability_score(0, 1.0, 1.0) == 1.0 or reliability_score(0, 1.0, 1.0) <= 1.0
    assert reliability_score(100, 0.0, 0.0) >= 0.0
    assert reliability_score(100, 0.0, 0.0) <= 1.0


def test_gate_boundary_exactly_threshold():
    # High-value (≥$2000) requires reliability ≥ 0.55
    assert eligible_for_high_value(0.54, 5000) is False
    assert eligible_for_high_value(0.55, 5000) is True
    assert eligible_for_high_value(0.40, 1999) is True


def test_benchmark_empty_history_is_typical():
    row = benchmark(2.5, [])
    assert row["flag"] == "typical"
    assert row["z_score"] == 0.0


def test_benchmark_single_sample_stable():
    row = benchmark(3.0, [3.0])
    assert row["flag"] == "typical"
