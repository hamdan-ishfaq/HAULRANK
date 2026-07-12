#!/usr/bin/env python3
"""Comprehensive live E2E against a running API. Exit nonzero on any failure."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
failures: list[str] = []


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
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def ok(cond: bool, msg: str):
    if cond:
        print(f"OK: {msg}")
    else:
        print(f"FAIL: {msg}")
        failures.append(msg)


def main():
    # --- health / auth ---
    code, health = call("GET", "/api/health/")
    ok(code == 200 and health.get("status") == "ok", "health")

    code, bad = call("POST", "/api/auth/token/", {"username": "demo", "password": "wrong"})
    ok(code == 401, "bad password rejected")

    code, tokens = call(
        "POST", "/api/auth/token/", {"username": "demo", "password": "demo-pass-123"}
    )
    ok(code == 200 and "access" in tokens, "demo login")
    token = tokens.get("access", "")

    code, _ = call("POST", "/api/rank/?truck_id=1")
    ok(code == 401, "rank requires auth")

    # --- seed shape ---
    code, trucks = call("GET", "/api/trucks/", token=token)
    ok(code == 200 and isinstance(trucks, list) and 3 <= len(trucks) <= 10, f"trucks count={len(trucks) if isinstance(trucks, list) else '?'}")
    ok(all(t.get("driver") for t in trucks), "every truck has driver")
    ok(
        any((t.get("driver") or {}).get("reliability_score") is not None for t in trucks),
        "reliability_score present",
    )
    truck_id = trucks[0]["id"]

    code, loads = call("GET", "/api/loads/", token=token)
    ok(code == 200 and isinstance(loads, list) and 50 <= len(loads) <= 120, f"loads count={len(loads) if isinstance(loads, list) else '?'}")

    # --- rank + cache timing ---
    t0 = time.perf_counter()
    code, rank1 = call("POST", f"/api/rank/?truck_id={truck_id}", token=token)
    t1 = time.perf_counter() - t0
    ok(code in (200, 201) and rank1.get("results") is not None, f"rank ({code})")
    ok(len(rank1.get("results", [])) >= 1, "rank non-empty")
    ok("best_single" in rank1, "best_single")
    ok("weather_risk" in rank1["results"][0], "weather field")
    ok("rate_benchmark" in rank1["results"][0], "rate_benchmark field")

    t0 = time.perf_counter()
    code, rank2 = call("POST", f"/api/rank/?truck_id={truck_id}", token=token)
    t2 = time.perf_counter() - t0
    ok(code in (200, 201), "rank cache call")
    ok(rank1["score_run_id"] == rank2["score_run_id"], "cache returns same score_run_id")
    ok(t2 < 1.0, f"cached rank under 1s ({t2:.3f}s)")
    print(f"  note: first rank {t1:.3f}s, cached {t2:.3f}s")

    # HOS exclusion: Austin truck (tight HOS) if present
    tight = next((t for t in trucks if (t.get("driver") or {}).get("hos_hours_remaining", 99) <= 4.5), None)
    if tight:
        code, r_tight = call("POST", f"/api/rank/?truck_id={tight['id']}", token=token)
        ok(code in (200, 201), "tight-HOS truck can rank")
        # long-haul loads should be fewer than full board
        ok(len(r_tight.get("results", [])) < len(loads), "HOS filters some loads")

    # backhaul — pair uses net $/hr (not the 0..1 overall score)
    pair_ok = False
    weather_flag = any(r.get("weather_risk") for r in rank1.get("results", []))
    for t in trucks:
        code, rr = call("POST", f"/api/rank/?truck_id={t['id']}", token=token)
        if any(r.get("weather_risk") for r in rr.get("results", [])):
            weather_flag = True
        bp = rr.get("best_pair")
        if bp and bp.get("beats_best_single"):
            pair_ok = True
            ok(
                bp["outbound_id"] != bp["return_id"] and bp["combined_score"] > 0,
                f"best_pair beats single (truck {t['id']}, metric={bp.get('metric')})",
            )
            break
    ok(pair_ok, "best_pair beats best single on ≥1 truck ($/hr)")
    if not weather_flag:
        print("  note: no live weather_risk (calm); set WEATHER_DEMO=1 for demo chip")
    else:
        ok(True, "weather_risk flag present on ≥1 load")
    score_run_id = rank1["score_run_id"]

    # --- explain grounded top-3 ---
    code, expl = call("POST", f"/api/rank/{score_run_id}/explain/", token=token)
    ok(code == 200, f"explain ({code})")
    exps = expl.get("explanations") or []
    ok(len(exps) == min(3, len(rank1["results"])), f"explain count={len(exps)}")
    top_ids = {r["load_id"] for r in rank1["results"][:3]}
    ok(all(e["load_id"] in top_ids for e in exps), "explain only top loads")
    ok(all(e.get("explanation_text") for e in exps), "explanation text non-empty")
    # second call idempotent
    code, expl2 = call("POST", f"/api/rank/{score_run_id}/explain/", token=token)
    ok(code == 200 and expl2.get("explanations") == exps, "explain idempotent")

    # --- assignments (loads are read-only; use ranked unassigned load) ---
    code, existing = call("GET", "/api/assignments/", token=token)
    taken = {
        a["load"]
        for a in (existing if isinstance(existing, list) else [])
        if a.get("status") in ("offered", "accepted", "dispatched")
    }
    load_id = next(
        (r["load_id"] for r in rank1["results"] if r["load_id"] not in taken),
        None,
    )
    ok(load_id is not None, "free ranked load available to assign")
    if load_id is None:
        print("FAIL: re-seed with: docker compose exec web python manage.py seed_demo --flush")
        failures.append("no free load")
        print()
        print(f"E2E FAILED: {len(failures)} checks")
        for f in failures:
            print(" -", f)
        sys.exit(1)

    # non-staff cannot mutate board
    code, _ = call("PATCH", f"/api/loads/{load_id}/", {"rate_usd": 1}, token=token)
    ok(code in (403, 405), f"loads read-only for demo user ({code})")

    code, assignment = call(
        "POST", "/api/assignments/", {"load": load_id, "truck": truck_id}, token=token
    )
    ok(code == 201, f"assignment create ({code})")
    aid = assignment["id"]
    code, bad_skip = call("PATCH", f"/api/assignments/{aid}/", {"status": "delivered"}, token=token)
    ok(code == 400, "illegal skip rejected")
    for st in ("accepted", "dispatched", "delivered"):
        code, updated = call("PATCH", f"/api/assignments/{aid}/", {"status": st}, token=token)
        ok(code == 200 and updated["status"] == st, f"→ {st}")
    code, hist = call("GET", f"/api/assignments/{aid}/history/", token=token)
    ok(code == 200 and len(hist.get("history", [])) >= 4, "assignment history length")

    # --- copilot 3 styles + grounding ---
    styles = [
        "loads to Texas",
        "dry van that nets at least 2000",
        "show me a backhaul round trip option",
    ]
    for msg in styles:
        code, cop = call(
            "POST", "/api/copilot/", {"truck_id": truck_id, "message": msg}, token=token
        )
        ok(code == 200, f"copilot '{msg}' ({code})")
        if code != 200:
            continue
        allowed = set(cop.get("allowed_load_ids") or [])
        for row in cop.get("results") or []:
            ok(row["load_id"] in allowed, f"grounded load {row['load_id']}")
        ok(bool(cop.get("narration")), "copilot narration")
        ok(isinstance(cop.get("filters"), dict), "copilot filters object")

    # --- fleet optimize ---
    code, fleet = call("POST", "/api/fleet/optimize/", token=token)
    ok(code == 200 and isinstance(fleet.get("assignments"), list), "fleet optimize")
    lids = [a["load_id"] for a in fleet.get("assignments", [])]
    ok(len(lids) == len(set(lids)), "fleet no duplicate loads")
    ok(len(fleet.get("assignments", [])) >= 1, "fleet ≥1 assignment")

    # --- analytics ---
    code, an = call("GET", "/api/analytics/summary/", token=token)
    ok(code == 200, "analytics summary")
    for key in (
        "revenue_by_truck",
        "acceptance_rate",
        "avg_deadhead_miles",
        "avg_score_all",
        "avg_score_accepted",
    ):
        ok(key in an, f"analytics.{key}")

    # --- frontend reachable (same host assumption) ---
    try:
        fe = urllib.request.urlopen("http://127.0.0.1:5173/", timeout=10)
        html = fe.read().decode()
        ok(fe.status == 200 and "HaulRank" in html, "frontend serves HaulRank")
    except Exception as e:
        ok(False, f"frontend reachable ({e})")

    print()
    if failures:
        print(f"E2E FAILED: {len(failures)} checks")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("E2E FULL SUITE PASSED against", BASE)


if __name__ == "__main__":
    main()
