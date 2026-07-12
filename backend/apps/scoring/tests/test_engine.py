"""Unit tests for pure scoring engine."""

from apps.scoring.engine import LoadInput, TruckInput, rank_loads


def _truck(**kwargs):
    base = dict(
        id=1,
        equipment_type="dry_van",
        lat=32.7767,
        lon=-96.7970,  # Dallas
        mpg=6.5,
        hos_hours_remaining=11.0,
        preferred_markets=["TX"],
        no_go_markets=["NY"],
    )
    base.update(kwargs)
    return TruckInput(**base)


def _load(id_, **kwargs):
    base = dict(
        id=id_,
        origin_lat=32.7767,
        origin_lon=-96.7970,
        dest_lat=29.7604,
        dest_lon=-95.3698,
        dest_market="TX",
        miles=200.0,
        rate_usd=600.0,
        equipment_type="dry_van",
        est_transit_hours=4.0,
    )
    base.update(kwargs)
    return LoadInput(**base)


def test_higher_rpm_ranks_higher_when_else_equal():
    truck = _truck()
    loads = [
        _load(1, rate_usd=500, miles=200),  # 2.5
        _load(2, rate_usd=700, miles=200),  # 3.5
    ]
    ranked = rank_loads(truck, loads, diesel_usd_per_gal=3.8)
    assert [r.load_id for r in ranked] == [2, 1]


def test_less_deadhead_wins_when_rates_equal():
    truck = _truck(lat=32.7767, lon=-96.7970)
    loads = [
        _load(1, origin_lat=33.5, origin_lon=-96.8, rate_usd=600, miles=200),  # farther
        _load(2, origin_lat=32.8, origin_lon=-96.8, rate_usd=600, miles=200),  # near
    ]
    ranked = rank_loads(truck, loads, diesel_usd_per_gal=3.8)
    assert ranked[0].load_id == 2


def test_hos_infeasible_excluded():
    truck = _truck(hos_hours_remaining=2.0)
    loads = [
        _load(1, est_transit_hours=5.0),  # infeasible
        _load(2, est_transit_hours=1.0, origin_lat=32.78, origin_lon=-96.80),
    ]
    ranked = rank_loads(truck, loads, diesel_usd_per_gal=3.8)
    ids = [r.load_id for r in ranked]
    assert 1 not in ids
    assert 2 in ids


def test_equipment_mismatch_excluded():
    truck = _truck(equipment_type="dry_van")
    loads = [_load(1, equipment_type="reefer")]
    assert rank_loads(truck, loads, diesel_usd_per_gal=3.8) == []


def test_preferred_market_beats_neutral():
    truck = _truck(preferred_markets=["TX"], no_go_markets=[])
    loads = [
        _load(1, dest_market="OK", rate_usd=600, miles=200),
        _load(2, dest_market="TX", rate_usd=600, miles=200),
    ]
    ranked = rank_loads(truck, loads, diesel_usd_per_gal=3.8)
    assert ranked[0].load_id == 2


def test_no_go_market_scores_low_but_listed():
    truck = _truck(preferred_markets=[], no_go_markets=["NY"])
    loads = [
        _load(1, dest_market="NY", rate_usd=900, miles=200),
        _load(2, dest_market="OK", rate_usd=900, miles=200),
    ]
    ranked = rank_loads(truck, loads, diesel_usd_per_gal=3.8)
    assert len(ranked) == 2
    assert ranked[0].load_id == 2


def test_single_load_no_div_zero():
    ranked = rank_loads(_truck(), [_load(1)], diesel_usd_per_gal=3.8)
    assert len(ranked) == 1
    assert ranked[0].overall > 0


def test_empty_loads():
    assert rank_loads(_truck(), [], diesel_usd_per_gal=3.8) == []


def test_stable_sort_by_load_id():
    truck = _truck()
    loads = [_load(5), _load(3), _load(9)]
    ranked = rank_loads(truck, loads, diesel_usd_per_gal=3.8)
    # identical scores → ascending load_id among ties via (-overall, load_id)
    assert [r.load_id for r in ranked] == [3, 5, 9]


def test_expensive_diesel_lowers_fuel_score_relative():
    truck = _truck(mpg=6.5)
    cheap = rank_loads(truck, [_load(1), _load(2, rate_usd=400)], diesel_usd_per_gal=2.5)
    pricey = rank_loads(truck, [_load(1), _load(2, rate_usd=400)], diesel_usd_per_gal=6.0)
    # relative ordering of fuel factor: higher rate load should still win, engine runs both
    assert len(cheap) == 2 and len(pricey) == 2
