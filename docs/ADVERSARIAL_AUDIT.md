# HaulRank Adversarial Audit Report

**Date:** 2026-07-12  
**Mode:** Hostile pre-launch (security + correctness). Green unit/E2E suite treated as non-evidence.  
**Target:** Live Docker stack at `http://127.0.0.1:8000` + pure engine probes.  
**Patches:** None applied (report-only).

---

## 1. Auth & access control

### [Critical] Cross-tenant load board is fully mutable (IDOR)

**Reproduction:**
```bash
# Register attacker, login, PATCH any load id from GET /api/loads/
curl -s -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"attacker_X","password":"AttackerPass123!","carrier_name":"Evil"}'
# token for attacker, then:
curl -s -X PATCH http://127.0.0.1:8000/api/loads/1/ \
  -H "Authorization: Bearer $ATTACKER" -H 'Content-Type: application/json' \
  -d '{"rate_usd":99999}'
# → 200, rate_usd=99999
curl -s -X DELETE http://127.0.0.1:8000/api/loads/1/ \
  -H "Authorization: Bearer $ATTACKER"
# → 204
```
Observed live: attacker `attacker_1783843737` patched load `1` `330 → 99999`, then deleted it (`204`).

**Expected:** Loads are a shared synthetic board *or* per-carrier; mutation must not be open to every registered user without controls. At minimum DELETE/PATCH of board data used by other carriers’ ranking must be forbidden (or admin-only).

**Actual:** `LoadViewSet` uses `Load.objects.all()` with no owner scope. Any authenticated user can list/create/patch/delete every load that feeds every other user’s `/api/rank/` and `/api/copilot/`.

**Fix:** Make loads read-only for non-staff in demo mode, or scope mutations to a carrier-owned subset, or seed-only writes via management command. Never expose unrestricted `ModelViewSet` on the global board if registration is open.

---

### [Critical] `DJANGO_DEBUG=1` in Compose leaks DB password + settings on any 500

**Reproduction:**
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"demo-pass-123"}' | jq -r .access)
curl -s -X POST 'http://127.0.0.1:8000/api/rank/?truck_id=notanint' \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
# HTML 500; body contains:
# postgres://haulrank:haulrank@db:5432/haulrank
# plus SECRET_KEY / OPENROUTER / REDIS settings dump (~152KB)
```

**Expected:** Production/demo deploys never return Django debug pages; 500s are opaque JSON.

**Actual:** Compose sets `DJANGO_DEBUG: "1"`. Triggering `ValueError` on `truck_id` returns a full debug page including **Postgres credentials**.

**Fix:** `DJANGO_DEBUG=0` for any shared/deployed environment; add exception handler returning `{"detail":"..."}`; never deploy this Compose file as-is.

---

### [High] No rate limiting / lockout on `/api/auth/token/`

**Reproduction:** 10 consecutive bad passwords in ~1.4s, all `401`, no backoff/lock:
```text
codes [401×10] elapsed 1.416s — no lockout/rate-limit observed
```

**Expected:** Throttling (e.g. DRF `AnonRateThrottle`) and/or lockout for public deploy.

**Actual:** Unlimited online password guessing against `demo` / any user.

**Fix:** Add DRF throttling on token + register; consider progressive delay.

---

### [Medium] Registration is username-only (no email); password validators work

**Reproduction:** `password: "1"` → `400` with Django validators. SQL-ish username `demo' OR '1'='1'` → `401`.

**Expected / Actual:** Weak password blocked; SQLi login did not bypass. No email race to test.

**Fix:** None for SQLi/password. Email N/A by design.

---

### Tried / could not break

| Attack | Result |
|--------|--------|
| Unauthenticated call to every §7 route except health | All `401`; health `200` |
| Attacker ranks demo `truck_id` | `404 Truck not found` |
| JWT `alg: none`, malformed JWT, refresh-as-access | All `401` |
| Evil CORS `Origin: https://evil.example` | No `Access-Control-Allow-Origin` |
| HTTP trigger `seed_demo` (`/api/seed/`, etc.) | `404` / admin `403` |
| Secrets in frontend bundle | Grep: no `OPENROUTER`/`SECRET`/`API_KEY` |

---

## 2. Scoring engine

### [High] Negative / zero miles & negative rates produce nonsensical ranked scores (engine)

**Reproduction:**
```python
rank_loads(truck, [LoadInput(..., miles=-100, rate_usd=600)], 3.8)
# → n=1, rate_per_mile=[0.0], overall=0.75
rank_loads(truck, [LoadInput(..., miles=200, rate_usd=-500)], 3.8)
# → n=1, rate_per_mile=[-2.5], overall=0.75
```

**Expected:** Reject or exclude non-physical inputs; never present negative RPM as a scored load.

**Actual:** Engine treats `miles <= 0` as RPM `0.0` and still ranks; negative rate yields negative RPM and still ranks with a “normal” overall via min-max.

**Note:** API serializer blocks `miles <= 0` and `rate_usd < 0` on write — so HTTP create/patch is safer than the pure engine. Any path that bypasses the serializer (seed bug, admin, future import) corrupts rankings.

**Fix:** Guard in `rank_loads`: skip `miles <= 0` or `rate_usd < 0`; assert in seed.

---

### [Medium] HOS boundary uses `>` — exact equality is included

**Reproduction:** `hos_hours_remaining=5.0`, `est_transit_hours=5.0`, deadhead≈0 → load **included**; `5.0001` excluded.

**Expected:** Document whether `==` is feasible. FMCSA-style “remaining must cover” often uses `>=` exclude when equal is unsafe.

**Actual:** `deadhead_hours + est_transit_hours > hos` → equal allowed.

**Fix:** Product decision; document in formula doc. If exclusive needed: change to `>=`.

---

### Tried / could not break

| Attack | Result |
|--------|--------|
| Empty batch | `[]` |
| Single-load batch | overall `0.75` (all factors 1.0) — stable |
| 20× identical twins (ids 10,11) | Always order `(10, 11)` via `(-overall, load_id)` |
| 500 loads | Ranked in ~0.002s, no crash |
| Equipment `Dry_Van` / `dry_van ` / `DRY_VAN` | Mismatch excluded (case/whitespace sensitive) — intentional strictness |
| HOS `0` / negative | Empty result set |

---

## 3. Backhaul / trip-chain

### Hand verification (seeded Dallas↔Houston)

Independent calc for outbound `$720/240mi/4.5h` + return `$1250/240mi/4.5h`, mpg `6.5`, diesel `$3.80`, zero deadhead:

- `combined_score` hand = **187.7094017094017**
- Engine = **187.7094017094017** (delta `0.0`)
- `pair_beats_best_single` → `True` on that two-load set

**Could not break the $/hr math** on this scenario (no sign error / double-count found).

### [Medium] Return-leg deadhead can be excluded by radius float noise at “exactly 75”

Naive point construction at 75.0 mi produced `75.00000000000064` → **excluded** by `<= 75.0`. Careful construction at `74.999…` includes.

**Fix:** Use epsilon (`<= radius + 1e-6`) or round miles to 1 decimal before compare.

### Tried / could not break

| Attack | Result |
|--------|--------|
| Self-pair (only outbound in candidates) | `None` |
| Zero eligible returns | `None` |
| Crafted HOS-infeasible end-to-end pair (`total_hours > hos`) | **Could not produce** a returned pair that overruns HOS; filter blocked the attempts used |
| One eligible return in radius | Works when HOS/radius OK |

---

## 4. Copilot

### [Critical] Narration grounding is **not enforced** — invented loads/rates returned as 200

`allowed_load_ids` is computed and returned, but narration is never validated/stripped.

**Reproduction (deterministic mock):**
```python
# patch llm_client.complete → parse JSON, then narrate:
# "Load #9999 pays $50000 and beats everything. Also load 7 is fine."
out = run_copilot("loads to Texas", truck, [load_id=7], 3.8)
# out["narration"] still contains 9999 / $50000
# out["allowed_load_ids"] == [7]
# HTTP layer would return 200 unchanged
```

**Expected (DoD):** Copilot never returns a load/number it wasn’t handed by the engine.

**Actual:** Server will happily return fabricated narration. Live OpenRouter resisted 8 injection prompts (no invented load_ids observed), but **absence of enforcement ≠ safety**.

**Fix:** Post-process: reject (422) or rewrite narration if any load_id / numeric claim outside engine payload; or stop returning free-form LLM text and template from structured fields only.

---

### [High] `dest_region: "Texas"` matches substring against `"TX"` → empty board

**Reproduction:** Live copilot message `Muéstrame cargas a Texas con net mínimo 2000` → filters `{'dest_region': 'Texas', 'min_net': 2000}` → **0 results** though TX loads exist. Unit: `apply_filters(loads, {"dest_region":"Texas"})` → `0`.

**Expected:** “Texas” maps to `TX` / market normalization.

**Actual:** `"TEXAS" in "TX"` is false.

**Fix:** Alias map (`texas→TX`, etc.) or match on expanded market names.

---

### [Medium] Malformed filter value types → uncaught → 503, not 422

**Reproduction:** LLM returns `{"min_net":"not-a-number","dest_region":"TX"}` → `parse_filters` accepts → `float(min_net)` raises → view catches `Exception` → **503 Copilot unavailable**.

**Expected:** 422 validation error.

**Fix:** Schema-validate filter types after parse.

---

### Live injection battery (8 prompts)

Could **not** get live model to emit load `#9999` / `$50000` / `424242` in narration. Contradictory “Texas but not Texas” degraded to empty results (via Texas≠TX), not a hallucinated filter set with fake loads. Long `A*5000` and Spanish handled without crash. Markdown `extra_evil` key was stripped by the model before parse (no 422).

---

## 5. Weather

### [High] Provider failure fails open as “no risk” with empty reason (looks like a clean check)

**Reproduction:**
```python
# both providers return None
assess_route(...) → WeatherRisk(active=False, reason='', severity=0.0)
```

**Expected:** Distinguish `unchecked` vs `checked-clear` (DoD weather flag honesty).

**Actual:** Identical to calm weather. UI can show no chip as if verified safe.

**Fix:** Return `weather_status: "unavailable"|"clear"|"severe"`; never equate fail-open to clear.

---

### [Low] Weather cache TTL 3h — stale severe/clear possible

`CACHE_TTL = 60*60*3` on lat/lon midpoint. No request-level `WEATHER_DEMO` toggle (query/body ignored) — **good**.

---

## 6. Assignments

### [Critical] Concurrent accept of two offers on same load → two `accepted` winners

**Reproduction:**
```text
POST /api/assignments/ load=L truck=1 → 201 id=10
POST /api/assignments/ load=L truck=3 → 201 id=11   # second offer allowed
# parallel:
PATCH .../10/ {"status":"accepted"} → 200 accepted
PATCH .../11/ {"status":"accepted"} → 200 accepted
# GET assignments: both accepted on same load
```

**Expected:** At most one non-terminal assignment per load; accept must be transactional with row lock / unique constraint.

**Actual:** Validation only blocks if an assignment already in `accepted|dispatched|delivered`. Two `offered` rows race to `accepted` with no DB uniqueness.

**Fix:** `UniqueConstraint` on `load` where status in active set; `select_for_update` in `transition_to` / validate; or single assignment row per load.

---

### [High] Assignment API bypasses HOS exclusion

**Reproduction:** Created load with `est_transit_hours=20`, assigned to Austin truck (`hos≈4`) via `POST /api/assignments/` → **201**.

**Expected:** If product claims HOS hard-exclude, dispatch path must not accept infeasible pairs (or must warn prominently).

**Actual:** Rank excludes; assignment does not check HOS/equipment.

**Fix:** Reuse feasibility check in `AssignmentSerializer.validate`.

---

### [Medium] Failed transitions do not append to `status_history`

Illegal `offered→delivered` → `400`; history unchanged (only successful transitions logged). Fine if “state audit”; weak if “attempt audit.”

---

## 7. Fleet optimize / reliability / rates

### Tried / could not break

| Attack | Result |
|--------|--------|
| More trucks than loads / more loads than trucks | No crash; no duplicate loads in unit probe |
| Reliability exactly `0.55` | Eligible (`>=`); `0.549` blocked |
| Benchmark `[]` / single sample | `typical`, `z_score=0` (no div/0) |

Concurrent fleet+rank consistency: not fully race-tested under load; cache staleness already dominates consistency risk.

---

## 8. Cache (Redis)

### [Critical] Rank cache keyed only by `(truck_id, hash(load_ids))` — rate edits served as fresh

**Reproduction:**
```text
POST /api/rank/?truck_id=1 → score_run_id=19, top load 66 rate_per_mile≈5.208
PATCH /api/loads/66/ {"rate_usd": 12.5}   # 99% cut
POST /api/rank/?truck_id=1 → same score_run_id=19, same overall/rpm for load 66
```

**Expected:** Invalidate on load/truck mutation, or include content hash (rates, miles, HOS, etc.) in cache key.

**Actual:** Stale scores for up to TTL **120s**, confidently returned as current ranking.

**Fix:** Key must include payload fingerprint of scored fields; or `cache.delete` on Load/Truck save signals; or disable cache until invalidation exists.

---

### [High] Redis down → rank **500** (hard fail) + debug HTML

**Reproduction:** `docker compose stop redis` then `POST /api/rank/` → `ConnectionError` 500 debug page.

**Expected:** Documented degrade to LocMem/in-process or 503 JSON without secrets.

**Actual:** Crash path; combined with DEBUG, credential leak.

**Fix:** Soft-fail cache get/set; `DEBUG=0`.

---

## 9. Infra / env

| Check | Result |
|-------|--------|
| `seed_demo` HTTP | Not routed |
| CORS | Locked to configured origins (evil origin denied) |
| Client bundle secrets | Not found |
| `WEATHER_DEMO` request injection | Not honored (env-only) |
| Compose `DJANGO_DEBUG=1` | **Unsafe for any non-local exposure** (see Critical above) |
| Default `SECRET_KEY` fallback in settings | `dev-insecure-change-me` if env missing — harden for prod |

---

## DoD claims vs reality

| Claim | Audit result |
|-------|----------------|
| Rank cached & correct | **Disproved** — stale after load mutation |
| HOS-infeasible excluded | **Partial** — true for rank; **false** for assignments |
| Copilot never invents loads/numbers | **Disproved** as an invariant (no enforcement); live model resisted samples |
| Weather risk meaningful | **Weak** — fail-open indistinguishable from clear |
| Ready for public free-tier URL | **No** — IDOR + DEBUG leaks + assignment race + stale cache |

---

## Verdict

**Not ready for public deploy, and not ready to put in front of a hiring manager as a “secure multi-user demo” without fixing the Criticals.** The scoring formula and backhaul `$/hr` math held up under direct attack; JWT truck-scoping and CORS also held. What failed are the systems around the formula: **anyone can rewrite the board**, **rank cache lies after edits**, **two trucks can accept the same load**, and **DEBUG Compose will hand an attacker the database password on a bad `truck_id`**.

**Single highest-priority fix:** Turn off DEBUG and stop shipping credential-leaking 500s, **in the same change** lock down load mutations (read-only board) and fix rank cache invalidation/fingerprint — those three are what turn a local capstone into a publicly exploitable toy.
