from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load
from apps.scoring.models import ScoreBreakdown, ScoreRun

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def ranked(db):
    user = User.objects.create_user(username="explainer", password="test-pass-123")
    carrier = Carrier.objects.create(name="Explain Co", owner=user)
    truck = Truck.objects.create(
        carrier=carrier,
        equipment_type="dry_van",
        current_lat=32.7,
        current_lon=-97.3,
        mpg=6.5,
    )
    Driver.objects.create(
        truck=truck,
        hos_hours_remaining=11,
        home_base_lat=32.7,
        home_base_lon=-97.3,
        preferred_markets=["TX"],
        no_go_markets=[],
    )
    start = timezone.now()
    loads = []
    for i in range(4):
        loads.append(
            Load.objects.create(
                origin_lat=32.8,
                origin_lon=-96.8,
                dest_lat=29.7,
                dest_lon=-95.3,
                dest_market="TX",
                miles=200 + i,
                rate_usd=700 + i * 50,
                equipment_type="dry_van",
                pickup_window_start=start,
                pickup_window_end=start + timedelta(hours=4),
                est_transit_hours=4,
            )
        )
    run = ScoreRun.objects.create(truck=truck, diesel_usd_per_gal=3.8)
    for i, load in enumerate(loads, start=1):
        ScoreBreakdown.objects.create(
            score_run=run,
            load=load,
            rate_per_mile_score=0.8,
            deadhead_penalty=0.2,
            fuel_efficiency_score=0.7,
            hos_feasibility=1.0,
            market_preference_score=1.0,
            overall=0.9 - i * 0.05,
            deadhead_miles=20,
            rate_per_mile=3.5,
            rank=i,
        )
    return user, run


@pytest.mark.django_db
def test_explain_top3_only_and_grounded(api, ranked):
    user, run = ranked
    token = api.post(
        "/api/auth/token/",
        {"username": "explainer", "password": "test-pass-123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")

    calls = []

    def fake_complete(system, user_msg):
        calls.append(user_msg)
        assert "0.85" in user_msg or "overall" in user_msg
        return f"Grounded explanation citing overall from payload."

    with patch("apps.explain.service.llm_client.complete", side_effect=fake_complete):
        res = api.post(f"/api/rank/{run.id}/explain/")
    assert res.status_code == 200, res.data
    assert len(res.data["explanations"]) == 3
    assert len(calls) == 3
    assert all(e["explanation_text"] for e in res.data["explanations"])

    # rank 4 never explained
    assert ScoreBreakdown.objects.get(score_run=run, rank=4).explanation_text == ""

    # idempotent — second call does not re-bill
    with patch("apps.explain.service.llm_client.complete", side_effect=fake_complete) as m:
        res2 = api.post(f"/api/rank/{run.id}/explain/")
    assert res2.status_code == 200
    assert m.call_count == 0


@pytest.mark.django_db
def test_explain_llm_failure_uses_grounded_fallback(api, ranked):
    user, run = ranked
    token = api.post(
        "/api/auth/token/",
        {"username": "explainer", "password": "test-pass-123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    with patch(
        "apps.explain.service.llm_client.complete",
        side_effect=RuntimeError("OPENROUTER_API_KEY not set"),
    ):
        ScoreBreakdown.objects.filter(score_run=run).update(explanation_text="")
        res = api.post(f"/api/rank/{run.id}/explain/")
    assert res.status_code == 200, res.data
    assert len(res.data["explanations"]) == 3
    text = res.data["explanations"][0]["explanation_text"]
    assert "overall" in text.lower() or "Rank #" in text
    assert str(res.data["explanations"][0]["overall"]) in text or "0." in text
