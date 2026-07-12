"""Fleet optimization unit tests."""

from apps.fleet_opt.engine import optimize_fleet
from apps.scoring.engine import LoadInput, TruckInput


def _truck(id_, lat, lon, eq="dry_van", hos=11.0):
    return TruckInput(
        id=id_,
        equipment_type=eq,
        lat=lat,
        lon=lon,
        mpg=6.5,
        hos_hours_remaining=hos,
        preferred_markets=["TX"],
        no_go_markets=[],
    )


def _load(id_, olat, olon, rate, miles=200.0, eq="dry_van"):
    return LoadInput(
        id=id_,
        origin_lat=olat,
        origin_lon=olon,
        dest_lat=29.7,
        dest_lon=-95.3,
        dest_market="TX",
        miles=miles,
        rate_usd=rate,
        equipment_type=eq,
        est_transit_hours=4.0,
    )


def test_no_duplicate_loads():
    trucks = [
        _truck(1, 32.78, -96.80),
        _truck(2, 32.90, -96.90),
    ]
    loads = [
        _load(10, 32.79, -96.81, 900),
        _load(11, 32.91, -96.91, 800),
    ]
    pairs = optimize_fleet(trucks, loads, 3.8)
    load_ids = [p.load_id for p in pairs]
    assert len(load_ids) == len(set(load_ids))
    assert len(pairs) == 2


def test_empty_inputs():
    assert optimize_fleet([], [], 3.8) == []


def test_equipment_mismatch_skipped():
    trucks = [_truck(1, 32.78, -96.80, eq="dry_van")]
    loads = [_load(10, 32.79, -96.81, 900, eq="reefer")]
    assert optimize_fleet(trucks, loads, 3.8) == []
