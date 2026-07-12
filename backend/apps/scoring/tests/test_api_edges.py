"""API edge cases: auth, illegal transitions, cache, ownership."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def two_users(db):
    a = User.objects.create_user(username="owner_a", password="test-pass-123")
    b = User.objects.create_user(username="owner_b", password="test-pass-123")
    ca = Carrier.objects.create(name="A", owner=a)
    cb = Carrier.objects.create(name="B", owner=b)
    ta = Truck.objects.create(
        carrier=ca, equipment_type="dry_van", current_lat=32.7, current_lon=-97.3, mpg=6.5
    )
    tb = Truck.objects.create(
        carrier=cb, equipment_type="dry_van", current_lat=32.7, current_lon=-97.3, mpg=6.5
    )
    for t in (ta, tb):
        Driver.objects.create(
            truck=t,
            hos_hours_remaining=11,
            home_base_lat=32.7,
            home_base_lon=-97.3,
            preferred_markets=["TX"],
            no_go_markets=[],
        )
    start = timezone.now()
    load = Load.objects.create(
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
    return a, b, ta, tb, load


def _token(api, username):
    res = api.post(
        "/api/auth/token/",
        {"username": username, "password": "test-pass-123"},
        format="json",
    )
    assert res.status_code == 200
    return res.data["access"]


@pytest.mark.django_db
def test_unauthenticated_rank_401(api):
    assert api.post("/api/rank/?truck_id=1").status_code == 401


@pytest.mark.django_db
def test_cannot_rank_other_users_truck(api, two_users):
    a, b, ta, tb, load = two_users
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {_token(api, 'owner_a')}")
    res = api.post(f"/api/rank/?truck_id={tb.id}")
    assert res.status_code == 404


@pytest.mark.django_db
def test_rank_cache_hit_same_payload(api, two_users):
    a, b, ta, tb, load = two_users
    cache.clear()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {_token(api, 'owner_a')}")
    r1 = api.post(f"/api/rank/?truck_id={ta.id}")
    r2 = api.post(f"/api/rank/?truck_id={ta.id}")
    assert r1.status_code == 201
    assert r2.status_code in (200, 201)
    assert r1.data["score_run_id"] == r2.data["score_run_id"]
    assert r1.data["results"] == r2.data["results"]


@pytest.mark.django_db
def test_assignment_illegal_skip_and_terminal(api, two_users):
    a, b, ta, tb, load = two_users
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {_token(api, 'owner_a')}")
    created = api.post(
        "/api/assignments/", {"load": load.id, "truck": ta.id}, format="json"
    )
    assert created.status_code == 201
    aid = created.data["id"]
    assert api.patch(f"/api/assignments/{aid}/", {"status": "delivered"}, format="json").status_code == 400
    for st in ("accepted", "dispatched", "delivered"):
        assert api.patch(f"/api/assignments/{aid}/", {"status": st}, format="json").status_code == 200
    assert api.patch(f"/api/assignments/{aid}/", {"status": "offered"}, format="json").status_code == 400


@pytest.mark.django_db
def test_health_public(api):
    assert api.get("/api/health/").status_code == 200
