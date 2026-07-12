#!/usr/bin/env python3
"""Live E2E against a running API. Exit 0 only if MVP flows pass."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def must(cond: bool, msg: str):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"OK: {msg}")


def main():
    code, health = call("GET", "/api/health/")
    must(code == 200 and health.get("status") == "ok", "health")

    code, tokens = call(
        "POST",
        "/api/auth/token/",
        {"username": "demo", "password": "demo-pass-123"},
    )
    must(code == 200 and "access" in tokens, f"login (got {code} {tokens})")
    token = tokens["access"]

    code, trucks = call("GET", "/api/trucks/", token=token)
    must(code == 200 and isinstance(trucks, list) and len(trucks) >= 1, f"trucks list ({code})")
    truck_id = trucks[0]["id"]
    must(trucks[0].get("driver") is not None, "truck has driver")

    code, loads = call("GET", "/api/loads/", token=token)
    must(code == 200 and len(loads) >= 10, f"loads seeded ({len(loads) if isinstance(loads, list) else loads})")

    code, rank = call("POST", f"/api/rank/?truck_id={truck_id}", token=token)
    must(code in (200, 201) and rank.get("results") is not None, f"rank ({code})")
    must(len(rank["results"]) >= 1, "rank returns results")
    must("best_single" in rank, "best_single present")
    must("weather_risk" in rank["results"][0], "weather fields on rank rows")
    if pair := rank.get("best_pair"):
        must("outbound_id" in pair and "return_id" in pair, "best_pair shaped")
    else:
        print("NOTE: best_pair null for this truck (ok if no nearby returns)")
    score_run_id = rank["score_run_id"]
    code, existing = call("GET", "/api/assignments/", token=token)
    taken = {
        a["load"]
        for a in (existing if isinstance(existing, list) else [])
        if a.get("status") in ("accepted", "dispatched", "delivered", "offered")
    }
    load_id = next(
        (r["load_id"] for r in rank["results"] if r["load_id"] not in taken),
        None,
    )
    if load_id is None:
        # create a fresh load so assignment chain can still be verified on re-runs
        from datetime import datetime, timedelta, timezone

        start = datetime.now(timezone.utc)
        code, created_load = call(
            "POST",
            "/api/loads/",
            {
                "origin_lat": 32.8,
                "origin_lon": -96.8,
                "dest_lat": 29.7,
                "dest_lon": -95.3,
                "dest_market": "TX",
                "miles": 250,
                "rate_usd": 900,
                "equipment_type": "dry_van",
                "pickup_window_start": start.isoformat(),
                "pickup_window_end": (start + timedelta(hours=6)).isoformat(),
                "est_transit_hours": 5,
            },
            token=token,
        )
        must(code == 201, f"create spare load ({code})")
        load_id = created_load["id"]
    must(load_id is not None, "free load available to assign")

    # explain without GROQ key should 503 — still a valid guarded path
    code, expl = call("POST", f"/api/rank/{score_run_id}/explain/", token=token)
    must(code in (200, 503), f"explain endpoint reachable ({code})")

    code, assignment = call(
        "POST",
        "/api/assignments/",
        {"load": load_id, "truck": truck_id},
        token=token,
    )
    must(code == 201, f"create assignment ({code} {assignment})")
    aid = assignment["id"]

    for status in ("accepted", "dispatched", "delivered"):
        code, updated = call(
            "PATCH",
            f"/api/assignments/{aid}/",
            {"status": status},
            token=token,
        )
        must(code == 200 and updated["status"] == status, f"transition → {status}")

    code, hist = call("GET", f"/api/assignments/{aid}/history/", token=token)
    must(code == 200 and len(hist.get("history", [])) >= 4, "assignment history")

    # copilot without key → 503; with mock we'd need groq — just check auth/validation
    code, copilot = call(
        "POST",
        "/api/copilot/",
        {"truck_id": truck_id, "message": "loads to TX"},
        token=token,
    )
    must(code in (200, 422, 503), f"copilot reachable ({code})")

    print("\nE2E MVP PASSED against", BASE)


if __name__ == "__main__":
    main()
