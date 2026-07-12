"""Regression tests for adversarial-audit remediation."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.copilot.service import apply_filters, ground_narration, parse_filters, run_copilot
from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load
from apps.scoring.engine import LoadInput, TruckInput, is_feasible, rank_loads

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def carrier_setup(db):
    user = User.objects.create_user(username="remedy", password="test-pass-123")
    carrier = Carrier.objects.create(name="Remedy Co", owner=user)
    truck = Truck.objects.create(
        carrier=carrier,
        equipment_type="dry_van",
        current_lat=32.7767,
        current_lon=-96.7970,
        mpg=6.5,
    )
    Driver.objects.create(
        truck=truck,
        hos_hours_remaining=14,
        home_base_lat=32.7767,
        home_base_lon=-96.7970,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    start = timezone.now()
    load = Load.objects.create(
        origin_lat=32.78,
        origin_lon=-96.80,
        dest_lat=29.76,
        dest_lon=-95.37,
        dest_market="TX",
        miles=240,
        rate_usd=900,
        equipment_type="dry_van",
        pickup_window_start=start,
        pickup_window_end=start + timedelta(hours=8),
        est_transit_hours=4.5,
    )
    return user, truck, load


def _auth(api, username="remedy"):
    res = api.post(
        "/api/auth/token/",
        {"username": username, "password": "test-pass-123"},
        format="json",
    )
    assert res.status_code == 200
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")


@pytest.mark.django_db
def test_truck_id_not_int_is_400(api, carrier_setup):
    _auth(api)
    res = api.post("/api/rank/?truck_id=notanint")
    assert res.status_code == 400
    assert "integer" in res.data["detail"].lower()
    body = str(res.data)
    assert "postgres://" not in body
    assert "SECRET" not in body


@pytest.mark.django_db
def test_loads_read_only_for_non_staff(api, carrier_setup):
    user, truck, load = carrier_setup
    _auth(api)
    assert api.patch(f"/api/loads/{load.id}/", {"rate_usd": 1}, format="json").status_code == 403
    assert api.delete(f"/api/loads/{load.id}/").status_code == 403
    assert api.get(f"/api/loads/{load.id}/").status_code == 200


@pytest.mark.django_db
def test_rank_cache_busts_on_rate_change(api, carrier_setup):
    user, truck, load = carrier_setup
    _auth(api)
    cache.clear()
    r1 = api.post(f"/api/rank/?truck_id={truck.id}")
    assert r1.status_code == 201
    run1 = r1.data["score_run_id"]
    rpm1 = next(x["rate_per_mile"] for x in r1.data["results"] if x["load_id"] == load.id)
    Load.objects.filter(pk=load.id).update(rate_usd=load.rate_usd * 0.1)
    r2 = api.post(f"/api/rank/?truck_id={truck.id}")
    assert r2.status_code == 201
    assert r2.data["score_run_id"] != run1
    rpm2 = next(x["rate_per_mile"] for x in r2.data["results"] if x["load_id"] == load.id)
    assert abs(rpm2 - rpm1) > 0.01


@pytest.mark.django_db
def test_second_active_assignment_rejected(api, carrier_setup):
    user, truck, load = carrier_setup
    truck2 = Truck.objects.create(
        carrier=truck.carrier,
        equipment_type="dry_van",
        current_lat=32.78,
        current_lon=-96.80,
        mpg=6.5,
    )
    Driver.objects.create(
        truck=truck2,
        hos_hours_remaining=14,
        home_base_lat=32.78,
        home_base_lon=-96.80,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    _auth(api)
    a1 = api.post("/api/assignments/", {"load": load.id, "truck": truck.id}, format="json")
    assert a1.status_code == 201
    a2 = api.post("/api/assignments/", {"load": load.id, "truck": truck2.id}, format="json")
    assert a2.status_code == 400


@pytest.mark.django_db
def test_hos_infeasible_assignment_rejected(api, carrier_setup):
    user, truck, _ = carrier_setup
    start = timezone.now()
    long_load = Load.objects.create(
        origin_lat=32.78,
        origin_lon=-96.80,
        dest_lat=41.88,
        dest_lon=-87.63,
        dest_market="IL",
        miles=900,
        rate_usd=4000,
        equipment_type="dry_van",
        pickup_window_start=start,
        pickup_window_end=start + timedelta(hours=12),
        est_transit_hours=20,
    )
    Driver.objects.filter(truck=truck).update(hos_hours_remaining=4)
    _auth(api)
    res = api.post(
        "/api/assignments/", {"load": long_load.id, "truck": truck.id}, format="json"
    )
    assert res.status_code == 400


def test_engine_skips_bad_miles_and_rate():
    truck = TruckInput(1, "dry_van", 32.7, -96.8, 6.5, 11, ["TX"], [])
    bad = [
        LoadInput(1, 32.7, -96.8, 29.7, -95.3, "TX", -10, 600, "dry_van", 4),
        LoadInput(2, 32.7, -96.8, 29.7, -95.3, "TX", 200, -50, "dry_van", 4),
        LoadInput(3, 32.7, -96.8, 29.7, -95.3, "TX", 200, 600, "dry_van", 4),
    ]
    ranked = rank_loads(truck, bad, 3.8)
    assert [r.load_id for r in ranked] == [3]
    assert not is_feasible(truck, bad[0])
    assert not is_feasible(truck, bad[1])


def test_texas_alias_matches_tx():
    loads = [LoadInput(1, 0, 0, 1, 1, "TX", 100, 2000, "dry_van", 3)]
    assert [l.id for l in apply_filters(loads, {"dest_region": "Texas"})] == [1]


def test_grounding_replaces_invented_load_ids():
    payload = {
        "results": [
            {"load_id": 7, "overall": 0.9, "rate_per_mile": 3.5, "deadhead_miles": 10}
        ],
        "best_pair": None,
    }
    narr = ground_narration(
        "Load #9999 pays $50000 and beats everything. Also load 7 is fine.",
        {7},
        payload,
    )
    assert "9999" not in narr
    assert "7" in narr


def test_parse_rejects_bad_min_net_type():
    with patch(
        "apps.copilot.service.llm_client.complete",
        return_value='{"dest_region":"TX","min_net":"nope"}',
    ):
        with pytest.raises(ValueError, match="min_net"):
            parse_filters("x")


def test_run_copilot_enforces_grounding():
    truck = TruckInput(1, "dry_van", 32.78, -96.8, 6.5, 14, ["TX"], [])
    loads = [LoadInput(7, 32.78, -96.8, 29.76, -95.37, "TX", 240, 900, "dry_van", 4.5)]

    def complete(system, user_msg):
        if "Extract" in system or "filters" in system.lower():
            return '{"dest_region":"TX"}'
        return "Load #9999 pays $50000 and beats everything."

    with patch("apps.copilot.service.llm_client.complete", side_effect=complete):
        out = run_copilot("loads to Texas", truck, loads, 3.8)
    assert "9999" not in out["narration"]
    assert 7 in out["allowed_load_ids"]
