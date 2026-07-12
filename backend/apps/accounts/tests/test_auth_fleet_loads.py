import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.fleet.models import Carrier

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="disp", password="test-pass-123")
    Carrier.objects.create(name="Demo Haul", owner=u)
    return u


@pytest.mark.django_db
def test_register_creates_carrier(api):
    res = api.post(
        "/api/auth/register/",
        {"username": "newco", "password": "StrongPass123!", "carrier_name": "New Co"},
        format="json",
    )
    assert res.status_code == 201
    assert Carrier.objects.filter(name="New Co").exists()


@pytest.mark.django_db
def test_token_and_trucks(api, user):
    token = api.post(
        "/api/auth/token/",
        {"username": "disp", "password": "test-pass-123"},
        format="json",
    )
    assert token.status_code == 200
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")

    create = api.post(
        "/api/trucks/",
        {
            "equipment_type": "dry_van",
            "current_lat": 32.7,
            "current_lon": -97.3,
            "mpg": 6.5,
            "driver": {
                "hos_hours_remaining": 8.0,
                "home_base_lat": 32.7,
                "home_base_lon": -97.3,
                "preferred_markets": ["TX"],
                "no_go_markets": [],
            },
        },
        format="json",
    )
    assert create.status_code == 201, create.data
    assert create.data["driver"]["hos_hours_remaining"] == 8.0

    bad_mpg = api.post(
        "/api/trucks/",
        {
            "equipment_type": "dry_van",
            "current_lat": 32.7,
            "current_lon": -97.3,
            "mpg": 0,
        },
        format="json",
    )
    assert bad_mpg.status_code == 400


@pytest.mark.django_db
def test_loads_validation(api, user):
    token = api.post(
        "/api/auth/token/",
        {"username": "disp", "password": "test-pass-123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    from django.utils import timezone
    from datetime import timedelta

    start = timezone.now()
    bad = api.post(
        "/api/loads/",
        {
            "origin_lat": 32.0,
            "origin_lon": -97.0,
            "dest_lat": 29.7,
            "dest_lon": -95.3,
            "dest_market": "TX",
            "miles": 0,
            "rate_usd": 1000,
            "equipment_type": "dry_van",
            "pickup_window_start": start.isoformat(),
            "pickup_window_end": (start + timedelta(hours=4)).isoformat(),
            "est_transit_hours": 5,
        },
        format="json",
    )
    assert bad.status_code == 400

    ok = api.post(
        "/api/loads/",
        {
            "origin_lat": 32.0,
            "origin_lon": -97.0,
            "dest_lat": 29.7,
            "dest_lon": -95.3,
            "dest_market": "TX",
            "miles": 250,
            "rate_usd": 800,
            "equipment_type": "dry_van",
            "pickup_window_start": start.isoformat(),
            "pickup_window_end": (start + timedelta(hours=4)).isoformat(),
            "est_transit_hours": 5,
        },
        format="json",
    )
    assert ok.status_code == 201, ok.data
