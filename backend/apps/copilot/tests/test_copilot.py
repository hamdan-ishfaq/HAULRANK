from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.copilot.service import apply_filters, parse_filters
from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load
from apps.scoring.engine import LoadInput

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(username="copilot", password="test-pass-123")
    carrier = Carrier.objects.create(name="Copilot Co", owner=user)
    truck = Truck.objects.create(
        carrier=carrier,
        equipment_type="dry_van",
        current_lat=32.7,
        current_lon=-97.3,
        mpg=6.5,
    )
    Driver.objects.create(
        truck=truck,
        hos_hours_remaining=14,
        home_base_lat=32.7,
        home_base_lon=-97.3,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    start = timezone.now()
    Load.objects.create(
        origin_lat=32.8,
        origin_lon=-96.8,
        dest_lat=29.7,
        dest_lon=-95.3,
        dest_market="TX",
        miles=240,
        rate_usd=2500,
        equipment_type="dry_van",
        pickup_window_start=start,
        pickup_window_end=start + timedelta(hours=6),
        est_transit_hours=5,
    )
    Load.objects.create(
        origin_lat=32.8,
        origin_lon=-96.8,
        dest_lat=35.4,
        dest_lon=-97.5,
        dest_market="OK",
        miles=200,
        rate_usd=500,
        equipment_type="reefer",
        pickup_window_start=start,
        pickup_window_end=start + timedelta(hours=6),
        est_transit_hours=4,
    )
    return user, truck


def test_apply_filters_dest_and_equipment():
    loads = [
        LoadInput(1, 0, 0, 1, 1, "TX", 100, 2000, "dry_van", 3),
        LoadInput(2, 0, 0, 1, 1, "OK", 100, 2000, "reefer", 3),
        LoadInput(3, 0, 0, 1, 1, "TX", 100, 100, "dry_van", 3),
    ]
    out = apply_filters(loads, {"dest_region": "TX", "equipment": "dry_van", "min_net": 1000})
    assert [l.id for l in out] == [1]


def test_parse_rejects_unknown_keys():
    with patch(
        "apps.copilot.service.llm_client.complete",
        return_value='{"dest_region":"TX","hack":true}',
    ):
        try:
            parse_filters("go to texas")
            assert False, "expected ValueError"
        except ValueError as e:
            assert "Unknown" in str(e)


@pytest.mark.django_db
def test_copilot_three_query_styles_grounded(api, setup):
    user, truck = setup
    token = api.post(
        "/api/auth/token/",
        {"username": "copilot", "password": "test-pass-123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")

    styles = [
        ('{"dest_region":"TX"}', "home to Texas by Friday"),
        ('{"min_net":2000}', "nets at least 2000"),
        ('{"equipment":"dry_van","prefer_backhaul":true}', "dry van backhaul"),
    ]

    for i, (parse_json, msg) in enumerate(styles):
        def complete(system, user_msg, _pj=parse_json, _i=i):
            if "Extract" in system or "filters" in system.lower():
                return _pj
            return f"Narration for style {_i} using only handed loads."

        with patch("apps.copilot.service.llm_client.complete", side_effect=complete):
            res = api.post(
                "/api/copilot/",
                {"message": msg, "truck_id": truck.id},
                format="json",
            )
        assert res.status_code == 200, res.data
        allowed = set(res.data["allowed_load_ids"])
        for row in res.data["results"]:
            assert row["load_id"] in allowed
