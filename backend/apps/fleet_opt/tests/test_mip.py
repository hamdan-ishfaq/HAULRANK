"""HR-1 / HR-2 fleet MIP + Hungarian + brownfield lock tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assignments.models import Assignment
from apps.fleet.models import Carrier, Driver, Truck
from apps.fleet_opt.engine import optimize_fleet, run_optimize
from apps.fleet_opt.mip_engine import solve_mip
from apps.loads.models import Load
from apps.scoring.engine import LoadInput, TruckInput, is_feasible

User = get_user_model()


def _truck(id_, lat=32.78, lon=-96.80, eq="dry_van", hos=14.0):
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


def _load(id_, olat=32.79, olon=-96.81, rate=900.0, miles=200.0, eq="dry_van", hours=4.0):
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
        est_transit_hours=hours,
    )


def _five_truck_fixture():
    trucks = [
        _truck(1, 32.78, -96.80, hos=14),
        _truck(2, 29.76, -95.37, hos=11),
        _truck(3, 35.47, -97.52, hos=11),
        _truck(4, 30.27, -97.74, hos=8),
        _truck(5, 35.15, -90.05, hos=11),
    ]
    loads = [
        _load(10, 32.79, -96.81, 1000),
        _load(11, 29.77, -95.38, 950),
        _load(12, 35.48, -97.53, 900),
        _load(13, 30.28, -97.75, 880),
        _load(14, 35.16, -90.06, 870),
        _load(15, 32.80, -96.82, 860),
        _load(16, 29.78, -95.39, 850),
    ]
    return trucks, loads


def test_mip_five_truck_feasible_one_load_per_truck():
    trucks, loads = _five_truck_fixture()
    result = solve_mip(trucks, loads, 3.8)
    assert result.solver == "mip"
    assert result.constraints_summary
    assert "one load per truck" in result.constraints_summary
    lids = [a.load_id for a in result.assignments]
    tids = [a.truck_id for a in result.assignments]
    assert len(lids) == len(set(lids))
    assert len(tids) == len(set(tids))
    load_by_id = {l.id: l for l in loads}
    truck_by_id = {t.id: t for t in trucks}
    for a in result.assignments:
        assert is_feasible(truck_by_id[a.truck_id], load_by_id[a.load_id])


def test_hungarian_vs_mip_objectives_equal_unconstrained():
    trucks, loads = _five_truck_fixture()
    hun = run_optimize(trucks, loads, 3.8, solver="hungarian")
    mip = run_optimize(trucks, loads, 3.8, solver="mip")
    assert hun.solver == "hungarian"
    assert mip.solver == "mip"
    assert abs(hun.objective_value - mip.objective_value) < 1e-6
    assert mip.baseline_comparison.get("matches") is True


def test_locked_pairs_not_stolen():
    trucks, loads = _five_truck_fixture()
    locked = [(1, 10), (2, 11)]
    for solver in ("mip", "hungarian"):
        result = run_optimize(trucks, loads, 3.8, solver=solver, locked_pairs=locked)
        by_truck = {a.truck_id: a.load_id for a in result.assignments}
        assert by_truck.get(1) == 10
        assert by_truck.get(2) == 11
        # No other truck gets locked loads
        for a in result.assignments:
            if a.truck_id not in (1, 2):
                assert a.load_id not in (10, 11)
        assert "locked brownfield" in " ".join(result.constraints_summary)
        assert len(result.locked_assignments) == 2


def test_optimize_fleet_compat_list():
    trucks, loads = _five_truck_fixture()
    pairs = optimize_fleet(trucks, loads, 3.8)
    assert isinstance(pairs, list)
    assert len({p.load_id for p in pairs}) == len(pairs)


@pytest.mark.django_db
def test_optimize_api_mip_constraints_summary():
    user = User.objects.create_user(username="optapi", password="x")
    carrier = Carrier.objects.create(name="Opt", owner=user)
    truck = Truck.objects.create(
        carrier=carrier,
        equipment_type="dry_van",
        current_lat=32.78,
        current_lon=-96.80,
        mpg=6.5,
    )
    Driver.objects.create(
        truck=truck,
        hos_hours_remaining=14,
        home_base_lat=32.78,
        home_base_lon=-96.80,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    now = timezone.now()
    Load.objects.create(
        origin_lat=32.79,
        origin_lon=-96.81,
        dest_lat=29.7,
        dest_lon=-95.3,
        dest_market="TX",
        miles=200,
        rate_usd=900,
        equipment_type="dry_van",
        pickup_window_start=now,
        pickup_window_end=now,
        est_transit_hours=4,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post("/api/fleet/optimize/?solver=mip")
    assert resp.status_code == 200
    assert resp.data["solver"] == "mip"
    assert resp.data["constraints_summary"]
    assert "baseline_comparison" in resp.data
    assert "locked_assignments" in resp.data


@pytest.mark.django_db
def test_api_honors_brownfield_locks():
    user = User.objects.create_user(username="bf", password="x")
    carrier = Carrier.objects.create(name="BF", owner=user)
    t1 = Truck.objects.create(
        carrier=carrier, equipment_type="dry_van",
        current_lat=32.78, current_lon=-96.80, mpg=6.5,
    )
    t2 = Truck.objects.create(
        carrier=carrier, equipment_type="dry_van",
        current_lat=29.76, current_lon=-95.37, mpg=6.5,
    )
    t3 = Truck.objects.create(
        carrier=carrier, equipment_type="dry_van",
        current_lat=35.47, current_lon=-97.52, mpg=6.5,
    )
    for t in (t1, t2, t3):
        Driver.objects.create(
            truck=t, hos_hours_remaining=14,
            home_base_lat=t.current_lat, home_base_lon=t.current_lon,
            preferred_markets=["TX"], no_go_markets=[],
        )
    now = timezone.now()

    def mk_load(olat, olon, rate):
        return Load.objects.create(
            origin_lat=olat, origin_lon=olon,
            dest_lat=29.7, dest_lon=-95.3, dest_market="TX",
            miles=200, rate_usd=rate, equipment_type="dry_van",
            pickup_window_start=now, pickup_window_end=now,
            est_transit_hours=4,
        )

    l1 = mk_load(32.79, -96.81, 1000)
    l2 = mk_load(29.77, -95.38, 950)
    l3 = mk_load(35.48, -97.53, 900)
    Assignment.objects.create(load=l1, truck=t1, status=Assignment.Status.DISPATCHED)
    Assignment.objects.create(load=l2, truck=t2, status=Assignment.Status.ACCEPTED)

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post("/api/fleet/optimize/", {"solver": "mip"}, format="json")
    assert resp.status_code == 200
    locked = {(x["truck_id"], x["load_id"]) for x in resp.data["locked_assignments"]}
    assert (t1.id, l1.id) in locked
    assert (t2.id, l2.id) in locked
    by_truck = {a["truck_id"]: a["load_id"] for a in resp.data["assignments"]}
    assert by_truck[t1.id] == l1.id
    assert by_truck[t2.id] == l2.id
    # t3 must not steal locked loads
    if t3.id in by_truck:
        assert by_truck[t3.id] not in (l1.id, l2.id)
