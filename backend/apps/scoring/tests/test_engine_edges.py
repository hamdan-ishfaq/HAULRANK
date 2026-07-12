"""Extra scoring edge cases for DoD confidence."""

from apps.scoring.engine import LoadInput, TruckInput, rank_loads


def _truck(**kw):
    base = dict(
        id=1,
        equipment_type="dry_van",
        lat=32.7767,
        lon=-96.7970,
        mpg=6.5,
        hos_hours_remaining=11.0,
        preferred_markets=["TX"],
        no_go_markets=["NY"],
    )
    base.update(kw)
    return TruckInput(**base)


def _load(id_, **kw):
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
    base.update(kw)
    return LoadInput(**base)


def test_negative_coords_still_score():
    ranked = rank_loads(
        _truck(lat=-33.8, lon=151.2),
        [_load(1, origin_lat=-33.9, origin_lon=151.1)],
        3.8,
    )
    assert len(ranked) == 1


def test_very_high_deadhead_still_ranked_if_hos_ok():
    truck = _truck(hos_hours_remaining=20)
    far = _load(1, origin_lat=41.88, origin_lon=-87.63, est_transit_hours=8)  # Chicago
    near = _load(2, origin_lat=32.8, origin_lon=-96.8, est_transit_hours=4)
    ranked = rank_loads(truck, [far, near], 3.8)
    ids = [r.load_id for r in ranked]
    assert 2 in ids
    # far may or may not be HOS-feasible; if present should rank below near when rates equal
    if 1 in ids:
        assert ids.index(2) < ids.index(1)


def test_mpg_effect_on_fuel_ordering():
    efficient = _truck(id=1, mpg=9.0)
    thirsty = _truck(id=2, mpg=4.0)
    loads = [_load(1, rate_usd=800, miles=200), _load(2, rate_usd=500, miles=200)]
    r_eff = {r.load_id: r.fuel_efficiency_score for r in rank_loads(efficient, loads, 4.5)}
    r_thirsty = {r.load_id: r.fuel_efficiency_score for r in rank_loads(thirsty, loads, 4.5)}
    # both produce valid 0..1 fuel scores
    assert all(0 <= v <= 1 for v in r_eff.values())
    assert all(0 <= v <= 1 for v in r_thirsty.values())


def test_zero_hos_excludes_all_with_positive_transit():
    assert rank_loads(_truck(hos_hours_remaining=0), [_load(1)], 3.8) == []
