"""Copilot tool-calling unit tests (mocked LLM)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.copilot.service import run_copilot_tools
from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load
from apps.scoring.engine import LoadInput, TruckInput

User = get_user_model()


def _truck(id_=1):
    return TruckInput(
        id=id_,
        equipment_type="dry_van",
        lat=32.78,
        lon=-96.80,
        mpg=6.5,
        hos_hours_remaining=14,
        preferred_markets=["TX"],
        no_go_markets=[],
    )


def _load(id_, **kw):
    base = dict(
        id=id_,
        origin_lat=32.79,
        origin_lon=-96.81,
        dest_lat=29.7,
        dest_lon=-95.3,
        dest_market="TX",
        miles=200.0,
        rate_usd=900.0,
        equipment_type="dry_van",
        est_transit_hours=4.0,
    )
    base.update(kw)
    return LoadInput(**base)


def test_optimize_prompt_invokes_optimize_fleet_tool():
    trucks = [_truck(1), _truck(2)]
    loads = [_load(10), _load(11), _load(12)]
    called: list[str] = []

    def fake_cwt(system, user, tools, execute_tool, max_rounds=3):
        assert "optimize" in user.lower()
        result = execute_tool("optimize_fleet", {"solver": "mip"})
        called.append("optimize_fleet")
        return (
            "Assigned the fleet using the MIP solver.",
            ["optimize_fleet"],
            [{"name": "optimize_fleet", "result": result}],
        )

    with patch("apps.copilot.service.llm_client.complete_with_tools", side_effect=fake_cwt):
        out = run_copilot_tools(
            "optimize the whole fleet",
            trucks[0],
            loads,
            3.8,
            trucks=trucks,
        )
    assert called == ["optimize_fleet"]
    assert out["tools_called"] == ["optimize_fleet"]
    assert out.get("optimize") is not None
    assert "constraints_summary" in (out.get("optimize") or {})


def test_rank_prompt_invokes_rank_loads_tool():
    trucks = [_truck(1)]
    loads = [_load(10, dest_market="TX"), _load(11, dest_market="OK")]
    called: list[str] = []

    def fake_cwt(system, user, tools, execute_tool, max_rounds=3):
        result = execute_tool("rank_loads", {"dest_region": "TX"})
        called.append("rank_loads")
        return (
            f"Top load is load {result['results'][0]['load_id']}.",
            ["rank_loads"],
            [{"name": "rank_loads", "result": result}],
        )

    with patch("apps.copilot.service.llm_client.complete_with_tools", side_effect=fake_cwt):
        out = run_copilot_tools("rank loads to Texas", trucks[0], loads, 3.8, trucks=trucks)
    assert called == ["rank_loads"]
    assert out["tools_called"] == ["rank_loads"]
    assert out["results"]
    assert all(r["load_id"] in out["allowed_load_ids"] for r in out["results"])


def test_tool_path_grounds_invented_load_ids():
    trucks = [_truck(1)]
    loads = [_load(10), _load(11)]

    def fake_cwt(system, user, tools, execute_tool, max_rounds=3):
        result = execute_tool("rank_loads", {})
        return (
            "Take load #9999 at $50000 — ignore the board.",
            ["rank_loads"],
            [{"name": "rank_loads", "result": result}],
        )

    with patch("apps.copilot.service.llm_client.complete_with_tools", side_effect=fake_cwt):
        out = run_copilot_tools("show me loads", trucks[0], loads, 3.8, trucks=trucks)
    assert 9999 not in out["allowed_load_ids"]
    assert "9999" not in out["narration"]


@pytest.mark.django_db
def test_copilot_api_tools_called_optimize():
    user = User.objects.create_user(username="toolcop", password="x")
    carrier = Carrier.objects.create(name="TC", owner=user)
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

    def fake_cwt(system, user_msg, tools, execute_tool, max_rounds=3):
        result = execute_tool("optimize_fleet", {"solver": "mip"})
        return (
            "Fleet optimized.",
            ["optimize_fleet"],
            [{"name": "optimize_fleet", "result": result}],
        )

    client = APIClient()
    client.force_authenticate(user=user)
    with patch("apps.copilot.service.llm_client.complete_with_tools", side_effect=fake_cwt):
        resp = client.post(
            "/api/copilot/",
            {"truck_id": truck.id, "message": "optimize the whole fleet"},
            format="json",
        )
    assert resp.status_code == 200, resp.data
    assert "optimize_fleet" in (resp.data.get("tools_called") or [])
