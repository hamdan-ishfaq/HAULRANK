# HaulRank — Complete Handoff

**Status:** Feature-complete, **publicly deployed**, and **system-verified**.  
**Owner / author:** Muhammad Hamdan Ishfaq (`hamdan-ishfaq@users.noreply.github.com`)  
**Repo:** https://github.com/hamdan-ishfaq/HAULRANK  
**Tip (as of this handoff):** `e19a134` on `main` / `develop`  
**Verified:** 2026-07-12 — live system E2E **133 passed / 0 failed**

---

## 0. One-page summary

HaulRank is a Spotter AI–aligned capstone: transparent load scoring and dispatch ranking for small carriers. Scores are **deterministic pure Python**. The LLM only **parses intent** or **narrates stored numbers**. Continuous compliance (Sentinel-echo) **revokes eligibility** on rules — it never auto-dispatches.

| Surface | URL |
|---------|-----|
| **UI** | https://haulrank.vercel.app/ |
| **API** | https://haulrank-pdmh.onrender.com |
| **Health** | https://haulrank-pdmh.onrender.com/api/health/ |
| **Demo login** | `demo` / `demo-pass-123` |

**Infra (free tier):** Neon Postgres · Upstash Redis · Render (Docker API) · Vercel (Vite UI)

**Single health command:**

```bash
python3 scripts/e2e_punish.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app
```

Warm the API first after idle (`curl …/api/health/`) — Render free sleeps ~15 min.

---

## 1. What you are handing off

### Product thesis

At FFC the author traced how a fertilizer order becomes truck movement, allocation, and billing — real freight, real audit trail. HaulRank applies that document-flow discipline to load ranking: every score is reproducible, every assignment has a state, and AI never invents the number.

### Scope shipped

| Layer | What shipped |
|-------|----------------|
| **MVP** | JWT auth, fleet CRUD, synthetic load board, deterministic rank + Redis cache, grounded top-3 explain, assignment state machine + history |
| **Tier 2** | Backhaul trip-chain (net `$/hr`), NL copilot → same engine, weather risk (Open-Meteo; optional `WEATHER_DEMO`) |
| **Tier 3** | Fleet Hungarian + OR-Tools CP-SAT MIP, continuous compliance (Sentinel-echo), rate z-scores, analytics; copilot tool-calling over rank/optimize |
| **Ops / harden** | Adversarial-audit remediation, request tracing, opaque 500s, brutal live E2E, free-tier deploy |

### Hard product invariants

1. **Scoring is deterministic** — no LLM in the score path (`apps/scoring/engine.py`).
2. **LLM is grounded** — explain narrates stored breakdowns; copilot uses tool-calling (`rank_loads` / `optimize_fleet`) or filter→engine→narrate; invented load IDs are rejected / templated away.
3. **Compliance is monitoring, not autonomy** — poll updates state; gates eligibility only; never auto-accepts or moves freight.
4. **Load board is synthetic** — seeded openly; no fake live DAT/TMS.

---

## 2. Live deployment

| Piece | Service | Notes |
|-------|---------|--------|
| Postgres | Neon | Pooled `DATABASE_URL` |
| Redis | Upstash | `rediss://` URL; rank cache |
| API | Render Web Service | Root `backend/`, Docker, free |
| UI | Vercel | Root `frontend/`, `VITE_API_BASE` → API |

### Production settings (must stay true)

- `DJANGO_SETTINGS_MODULE=config.settings.production` (forces `DEBUG=False`)
- `DJANGO_DEBUG=0`
- `CORS_ALLOWED_ORIGINS=https://haulrank.vercel.app` (exact origin)
- Start command includes migrate + seed + gunicorn `--timeout 60 --workers 2`

See [docs/DEPLOY.md](docs/DEPLOY.md).

### Health contract

```json
{
  "status": "ok",
  "service": "haulrank-api",
  "features": ["request_trace", "opaque_500", "compliance_sentinel"]
}
```

### Cold starts

Render free sleeps after ~15 minutes idle. First request can take 30–60s. Always warm `/api/health/` before a demo or recruiter click.

---

## 3. Definition of Done (final)

### MVP

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 50–100 loads, 3–5 trucks with distinct HOS/market profiles | **Met** | Seed: 5 trucks, ~56+ loads + dedicated Dallas↔Houston backhaul pair |
| `/api/rank/` ranked, cached, factor-scored; cached repeat fast | **Met** | Live E2E cached ~600ms (cold network); same `score_run_id` |
| HOS-infeasible loads excluded (not just penalized) | **Met** | Unit + E2E on Austin (4h HOS) truck |
| Top-3 LLM explain grounded in score breakdown | **Met** | Live E2E; fallback narration if OpenRouter times out |
| Assignment chain + audit trail | **Met** | offered→accepted→dispatched→delivered; illegal skip 400 |
| Live deployed URL, free infra | **Met** | Vercel + Render URLs above |
| README FFC → HaulRank framing | **Met** | `README.md` |

### Tier 2

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Backhaul pair beats best single on ≥1 seeded scenario | **Met** | Metric: net `$/hr`; API returns `best_pair` only when `beats_best_single` |
| Copilot ≥3 NL styles; never invents loads/numbers | **Met** | Live E2E adversarial prompts; `load_id ∈ allowed_load_ids` |
| ≥1 load weather-risk with real/mocked reason | **Met** | Open-Meteo when severe; `WEATHER_DEMO=1` forces chip |

### Tier 3

| Feature | Why | Status |
|---------|-----|--------|
| Fleet optimize | One load per truck; Hungarian baseline + CP-SAT MIP; brownfield locks | Unit + E2E · [docs/FLEET_MIP.md](docs/FLEET_MIP.md) |
| Continuous compliance | Polled `clear\|watch\|restricted\|suspended`; eligibility only | Live §12 E2E + `docs/COMPLIANCE.md` |
| Rate benchmark | Z-score vs seeded lane history | Unit + rank field |
| Analytics summary | Post-dispatch KPIs without charting deps | Live E2E |

### Security / reliability gates (post-audit)

| Gate | Status |
|------|--------|
| Opaque JSON 500s when `DEBUG=False` | Met |
| Rank cache fingerprints scored fields (+ compliance state) | Met |
| Loads read-only for non-staff | Met |
| One active assignment per load (+ race-tested) | Met (8/8 concurrent trials) |
| Auth throttle | Met (`auth` 10/min) |
| Redis soft-fail | Met |
| Assignment HOS/equipment + compliance gates | Met |
| Request IDs (`X-Request-ID`) | Met on live |
| System E2E single entry | Met — `scripts/e2e.py` |

---

## 4. Architecture

```
Browser (Vercel)
  React + Vite + MUI
       │  JWT (SimpleJWT)
       ▼
API (Render / Gunicorn)
  Django + DRF
       │
  ┌────┼──────────────────────────────┐
  ▼    ▼              ▼               ▼
Neon  Upstash      OpenRouter      Open-Meteo
Postgres Redis     (explain/       (weather;
                   copilot)         optional EIA diesel)
       │
  Pure Python engines (no LLM):
    scoring · backhaul · fleet_opt · rates · reliability · compliance
```

### Backend apps (`backend/apps/`)

| App | Role |
|-----|------|
| `accounts` | Register + JWT |
| `fleet` | Carrier / Truck / Driver (+ reliability + compliance fields) |
| `loads` | Synthetic board (staff write; demo read) |
| `scoring` | Rank API, cache, score runs / breakdowns |
| `explain` | Top-3 grounded narration (+ deterministic LLM fallback) |
| `assignments` | State machine + history + uniqueness race lock |
| `backhaul` | Trip-chain search (net `$/hr`) |
| `copilot` | NL → tools/filters → engine → grounded narrate |
| `weather` | Annotate rank rows (`clear` / `severe` / `unavailable`) |
| `fleet_opt` | Hungarian + OR-Tools CP-SAT MIP; brownfield locks |
| `rates` | Lane history + z-score benchmark |
| `analytics` | Summary KPIs |
| `compliance` | Sentinel-echo poll + state machine |

### Frontend (`frontend/src/`)

| File | Role |
|------|------|
| `pages/LoginPage.tsx` | Login; surfaces status + `API_BASE` on failure |
| `pages/DispatchPage.tsx` | Truck select, rank, explain, copilot, fleet opt, compliance chip |
| `components/AssignmentBoard.tsx` | Offer → deliver board |
| `api/client.ts` | Typed fetch client |

### Key pure-engine paths

| Concern | Path |
|---------|------|
| Score formula | `backend/apps/scoring/engine.py` · [docs/scoring-formula.md](docs/scoring-formula.md) |
| Rank API | `backend/apps/scoring/views.py` |
| Backhaul | `backend/apps/backhaul/engine.py` |
| Fleet opt | `backend/apps/fleet_opt/engine.py` |
| Reliability score | `backend/apps/fleet/reliability.py` |
| Compliance rules | `backend/apps/compliance/engine.py` |
| LLM client | `backend/integrations/llm_client.py` (12s timeout) |
| Request trace | `backend/config/middleware.py` |
| Opaque errors | `backend/config/exception_handler.py` |

More: [docs/architecture.md](docs/architecture.md), [docs/api.md](docs/api.md).

---

## 5. Scoring model (dispatcher-facing)

```
overall =
    0.30 * rate_per_mile_score
  + 0.25 * (1 - deadhead_penalty)   # inverted in formula docs
  + 0.20 * fuel_efficiency_score
  + 0.15 * hos_feasibility
  + 0.10 * market_preference_score
```

Factors are min-max normalized 0–1 within the current batch before weighting.

**Hard exclusions (not soft penalties):**

- Equipment mismatch
- HOS infeasible: `deadhead_hours + est_transit_hours > hos_hours_remaining`
- Non-physical inputs (`miles <= 0`, `rate_usd < 0`)

**Rank enrichments:**

- Weather annotation on rows
- Rate z-score benchmark vs seeded lane history
- Compliance gate: drop high-value loads when state is `restricted` (or weak reliability defense-in-depth)
- Optional `best_pair` when backhaul beats best single on **net USD per hour**

**Cache:** Redis key fingerprints truck inputs + load scored fields + diesel + `compliance_state` (TTL ~120s). Soft-fails if Redis blips.

---

## 6. Continuous compliance (Sentinel-echo)

Full detail: [docs/COMPLIANCE.md](docs/COMPLIANCE.md).

### States (strictest wins)

| State | Dispatch | High-value (≥ $2000) |
|-------|----------|----------------------|
| `clear` | Yes | Yes |
| `watch` | Yes | Yes (badge elevated) |
| `restricted` | Yes | **No** |
| `suspended` | **No** (rank 403) | **No** |

### Signals (synthetic on Driver)

- `hos_violations_90d`
- `inspection_pass_rate`
- `on_time_pct`
→ `reliability_score` + `compliance_state` / `compliance_reason` / `compliance_history`

### How state is updated

```bash
# Management (local / Render cron / seed_demo)
.venv/bin/python manage.py poll_compliance -v2

# API (own fleet)
POST /api/compliance/poll/
GET  /api/compliance/
```

Optional Celery beat (15m) when Redis + workers available — Compose profile `celery`. Free Render can skip workers and cron the management command.

### Seed expectation after poll

| Profile | Typical state |
|---------|----------------|
| Dallas | `clear` |
| Houston (1 HOS viol) | `watch` |
| Austin (weak compliance) | `restricted` |
| OKC / Memphis | `clear` |

---

## 7. Demo data (`seed_demo`)

| Truck | Equipment | HOS | Pref / no-go | Compliance signals |
|-------|-----------|-----|--------------|--------------------|
| Dallas | dry_van | 14h | TX,OK / NY | Strong (backhaul-feasible) |
| Houston | reefer | 8h | TX | Mild viol → watch |
| OKC | flatbed | 11h | OK,TX | Strong |
| Austin | dry_van | 4h | TX | Weak → restricted |
| Memphis | dry_van | 9h | TN,GA | Strong |

Also seeds ~50+ lane loads, a dedicated Dallas↔Houston round-trip pair, lane rate history, then runs `poll_compliance`.

```bash
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py seed_demo --flush   # clean board
```

---

## 8. API map

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/health/` | GET | no | Liveness + feature flags |
| `/api/auth/register/` | POST | no | User + carrier |
| `/api/auth/token/` | POST | no | JWT access/refresh |
| `/api/auth/token/refresh/` | POST | no | Refresh |
| `/api/trucks/` | CRUD | yes | Fleet (+ driver, reliability, compliance) |
| `/api/loads/` | GET (POST/PATCH staff) | yes | Synthetic board |
| `/api/rank/?truck_id=` | POST | yes | Rank + enrichments + optional `best_pair` |
| `/api/rank/{id}/explain/` | POST | yes | Top-3 grounded narration |
| `/api/assignments/` | GET/POST/PATCH | yes | Status chain |
| `/api/assignments/{id}/history/` | GET | yes | Audit |
| `/api/copilot/` | POST | yes | NL → tools/filters → engine → narrate |
| `/api/fleet/optimize/?solver=` | POST | yes | Multi-truck `mip` (default) or `hungarian` |
| `/api/analytics/summary/` | GET | yes | KPIs |
| `/api/compliance/` | GET | yes | Fleet compliance snapshot |
| `/api/compliance/poll/` | POST | yes | One poll cycle (own fleet) |

**Rank notes:**

- `best_pair.combined_score` is **net USD per hour**, not the 0–1 overall.
- Payload includes `compliance_state` when eligible; `403` + reason when `suspended`.

---

## 9. Environment variables

| Variable | Required | Notes |
|----------|----------|--------|
| `DJANGO_SECRET_KEY` | prod yes | Strong random |
| `DJANGO_DEBUG` | prod `0` | Never `1` on public |
| `DJANGO_SETTINGS_MODULE` | prod | `config.settings.production` |
| `DJANGO_ALLOWED_HOSTS` | prod yes | Render hostname |
| `DATABASE_URL` | yes | Neon pooled / Compose / sqlite |
| `REDIS_URL` | prod yes | Upstash; empty local → LocMem |
| `CORS_ALLOWED_ORIGINS` | yes | Exact Vercel origin(s) |
| `OPENROUTER_API_KEY` | explain/copilot | Prefer set in prod |
| `OPENROUTER_MODEL` | no | Default `openai/gpt-4o-mini` |
| `EIA_API_KEY` | no | Else diesel fallback $3.80 |
| `OPENWEATHER_API_KEY` | no | Backup only |
| `WEATHER_DEMO` | no | `1` forces severe chip |
| `SENTRY_DSN` | no | Optional crash reporting |
| `CELERY_*` | no | Optional compliance beat |

**Never commit `.env`.** See [docs/credentials.md](docs/credentials.md).

Local `.env` tip: use only `KEY=value` lines. Non-assignment notes (`neon = …`) print `Invalid line` warnings and can leak secrets into logs — keep notes out of `.env`.

---

## 10. Local runbook

### Docker (recommended)

```bash
cp .env.example .env   # OPENROUTER_API_KEY at minimum
docker compose up --build
```

- UI: http://localhost:5173/
- API: http://localhost:8000/api/health/

Compose overrides DB/Redis. Optional Celery:

```bash
docker compose --profile celery up worker beat
```

### Without Docker (WSL: no bare `python`)

```bash
cd backend
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver 0.0.0.0:8000
# other terminal
cd frontend && npm install && npm run dev
```

---

## 11. Verification (canonical)

### Unit tests

```bash
cd backend && .venv/bin/python -m pytest -q
# ~68 tests collected (scoring, remediation, compliance, weather, fleet_opt, …)
```

### System health (one command — brutal + compliance)

```bash
# Local
python3 scripts/e2e.py http://127.0.0.1:8000 http://127.0.0.1:5173

# Live
python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app

make e2e
make e2e-live
```

Aliases: `scripts/e2e_brutal.py`, `scripts/e2e_full.py` → same suite.

**Suite sections:** health · CORS · auth/JWT abuse · DEBUG leak probes · fleet ACL · rank/cache/HOS · assignment HOS/double-offer/illegal transitions · concurrent race (8 trials) · explain grounding · adversarial copilot · fleet opt · analytics · frontend shell · continuous compliance.

**Latest live result:** `PASSED 133  FAILED 0` · `SYSTEM E2E: ALL PASSED` (2026-07-12).

### Compliance-only smoke

```bash
cd backend
.venv/bin/python manage.py poll_compliance -v2
.venv/bin/python -m pytest apps/compliance/ -q
```

### Frontend build

```bash
cd frontend && npm run build
```

---

## 12. Demo script (5–7 minutes)

1. Warm API: `curl https://haulrank-pdmh.onrender.com/api/health/`
2. Open https://haulrank.vercel.app/ → `demo` / `demo-pass-123`
3. Select **Dallas dry_van** → **Rank loads** — show factor chips; second Rank is cached
4. Show **best round-trip** if present (Dallas↔Houston seeded)
5. **Explain top 3** — narration cites stored factors (or grounded fallback)
6. Note **compliance chip** on truck selector (Austin = restricted)
7. Rank Austin → high-value loads gated; attempt high-$ assign → 400
8. Copilot: *"dry van that nets at least 2000"* and *"Muéstrame cargas a Texas"*
9. Offer → accept → dispatch → deliver; show history
10. **Optimize fleet** + analytics panel

**Talk track:** scoring/ranking problem; AI only explains or parses; Sentinel-shaped compliance without autonomy; free-tier live URL.

---

## 13. Ops / debugging

Full guide: [docs/TRACING.md](docs/TRACING.md).

| Signal | Where |
|--------|--------|
| `X-Request-ID` / `rid=` in logs | Render Logs + response header |
| Login failure detail + `API_BASE` | Login page UI |
| `[HaulRank API]` | Browser console |
| CORS / cold start | Network tab + Render Logs |
| Optional Sentry | `SENTRY_DSN` |

Adversarial audit history + remediations: [docs/ADVERSARIAL_AUDIT.md](docs/ADVERSARIAL_AUDIT.md).

---

## 14. Known limitations (honest)

- Load board is **synthetic** — no live DAT/TMS.
- Fleet MIP is a **small BIP assignment** over ranking utilities — not factory-layout LP, Omniverse, or production OR at scale.
- Brownfield locked assignments (`seed_demo --brownfield`) are a **planning analogy** for residual capacity beside a committed plan — not a digital twin / facility geometry / production-line integration.
- Copilot tool-calling is a thin OpenRouter tools loop — **not** LangGraph.
- Calm weather → no severe chip unless Open-Meteo reports severe or `WEATHER_DEMO=1`.
- First rank can be slow when weather annotates many loads; **cached** repeats are fast.
- OpenRouter cold/slow → explain uses **deterministic grounded fallback** (still cites stored numbers).
- Render free **sleeps**; warm before demos.
- MUI bundle is large (~900KB) — fine for demo, not Lighthouse-optimized.
- Repeated E2E runs create many delivered assignments; re-seed with `--flush` for a clean board.
- Auth throttle may yield 429 after burst tests — wait ~1 minute.
- Celery beat is optional; free Render typically uses on-demand / cron poll.

---

## 15. Git / branching / authorship

```
main (releases / deploy)  ←  develop  ←  feature/<module>
```

- Commits authored as **Muhammad Hamdan Ishfaq** / `hamdan-ishfaq@users.noreply.github.com` only
- **No** AI co-author trailers
- Do not commit `.env` or secrets

Recent milestone commits:

| Commit | Topic |
|--------|--------|
| `e19a134` | Explain LLM timeout hardening + gunicorn timeout |
| `862b6b3` | Sentinel continuous compliance + unified `scripts/e2e.py` |
| `4ea393d` | Brutal live E2E + request-id hardening |
| `23413d9` | Request tracing / login errors / optional Sentry |
| `79c4337` | Free-tier deploy guide |
| `22e62c7` | Adversarial audit harden for public deploy |
| `12eaa4b` | Tier 3 complete |

---

## 16. Doc index

| Doc | Purpose |
|-----|---------|
| [README.md](README.md) | Project intro + quick start |
| [HANDOFF.md](HANDOFF.md) | **This document** — complete handoff |
| [HaulRank_PRD.md](HaulRank_PRD.md) | Product requirements |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Neon / Upstash / Render / Vercel |
| [docs/FLEET_MIP.md](docs/FLEET_MIP.md) | Hungarian + CP-SAT MIP assignment |
| [docs/COMPLIANCE.md](docs/COMPLIANCE.md) | Sentinel-echo state machine |
| [docs/TRACING.md](docs/TRACING.md) | Debug login / CORS / logs |
| [docs/ADVERSARIAL_AUDIT.md](docs/ADVERSARIAL_AUDIT.md) | Hostile audit + remediations |
| [docs/scoring-formula.md](docs/scoring-formula.md) | Score weights |
| [docs/architecture.md](docs/architecture.md) | System sketch |
| [docs/api.md](docs/api.md) | API notes |
| [docs/credentials.md](docs/credentials.md) | Secrets hygiene |

---

## 17. Handoff checklist (receiver)

- [ ] Clone repo; confirm `main` at `e19a134` or newer
- [ ] Open live UI; login `demo` / `demo-pass-123` (warm API first)
- [ ] Run `python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app` → expect ALL PASSED
- [ ] Read [docs/COMPLIANCE.md](docs/COMPLIANCE.md) and [docs/DEPLOY.md](docs/DEPLOY.md)
- [ ] Confirm Render env still has `DJANGO_DEBUG=0`, production settings, CORS = Vercel origin
- [ ] Confirm OpenRouter key present if LLM narrations (vs fallback) are required for a live interview
- [ ] Know re-seed: Render shell or redeploy start command runs `seed_demo`
- [ ] Know authorship rule before any commit

---

## 18. Ready status

| Gate | Result |
|------|--------|
| Unit tests | **Collected / passing** (~68) |
| Live system E2E | **133 / 0 ALL PASSED** |
| Public UI + API | **Live** |
| DoD (MVP + Tier 2 + Tier 3) | **Met** |
| Audit remediations | **Met** |
| Continuous compliance | **Met + live-verified** |

**This handoff is complete.** The system is deployed, documented, and verifiable with one command.
