from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(username="ranker", password="test-pass-123")
    carrier = Carrier.objects.create(name="Rank Co", owner=user)
    truck = Truck.objects.create(
        carrier=carrier,
        equipment_type="dry_van",
        current_lat=32.7767,
        current_lon=-96.7970,
        mpg=6.5,
    )
    Driver.objects.create(
        truck=truck,
        hos_hours_remaining=11.0,
        home_base_lat=32.7767,
        home_base_lon=-96.7970,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    start = timezone.now()
    load_ok = Load.objects.create(
        origin_lat=32.8,
        origin_lon=-96.8,
        dest_lat=29.7,
        dest_lon=-95.3,
        dest_market="TX",
        miles=240,
        rate_usd=900,
        equipment_type="dry_van",
        pickup_window_start=start,
        pickup_window_end=start + timedelta(hours=6),
        est_transit_hours=5,
    )
    Load.objects.create(
        origin_lat=32.8,
        origin_lon=-96.8,
        dest_lat=40.7,
        dest_lon=-74.0,
        dest_market="NY",
        miles=1500,
        rate_usd=4000,
        equipment_type="dry_van",
        pickup_window_start=start,
        pickup_window_end=start + timedelta(hours=6),
        est_transit_hours=30,  # HOS infeasible
    )
    return user, truck, load_ok


@pytest.mark.django_db
def test_rank_excludes_hos_and_returns_breakdown(api, setup):
    user, truck, load_ok = setup
    token = api.post(
        "/api/auth/token/",
        {"username": "ranker", "password": "test-pass-123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    res = api.post(f"/api/rank/?truck_id={truck.id}")
    assert res.status_code == 201, res.data
    ids = [r["load_id"] for r in res.data["results"]]
    assert load_ok.id in ids
    assert all(r["hos_feasibility"] == 1.0 for r in res.data["results"])
    assert res.data["best_single"]["load_id"] == load_ok.id


@pytest.mark.django_db
def test_assignment_chain(api, setup):
    user, truck, load_ok = setup
    token = api.post(
        "/api/auth/token/",
        {"username": "ranker", "password": "test-pass-123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    created = api.post(
        "/api/assignments/",
        {"load": load_ok.id, "truck": truck.id},
        format="json",
    )
    assert created.status_code == 201, created.data
    aid = created.data["id"]

    bad = api.patch(f"/api/assignments/{aid}/", {"status": "dispatched"}, format="json")
    assert bad.status_code == 400

    for st in ("accepted", "dispatched", "delivered"):
        ok = api.patch(f"/api/assignments/{aid}/", {"status": st}, format="json")
        assert ok.status_code == 200, ok.data

    hist = api.get(f"/api/assignments/{aid}/history/")
    assert hist.status_code == 200
    assert len(hist.data["history"]) == 4
