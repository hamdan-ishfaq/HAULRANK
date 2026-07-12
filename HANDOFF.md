# HaulRank — Handoff (pre-deploy)

**Status:** Feature-complete **locally**. Verified with unit + live E2E. **Public deploy URL is the only open DoD item** — next step after you approve this handoff.

**Verified:** 2026-07-12 · pytest + `python3 scripts/e2e.py` (brutal + compliance)

---

## 1. What you are handing off

HaulRank is a transparent load-scoring / dispatch-ranking app for small carriers (Spotter AI–aligned capstone).

| Layer | What shipped |
|-------|----------------|
| **MVP** | JWT auth, fleet CRUD, load board, deterministic rank + Redis cache, grounded top-3 explain, assignment state machine + history |
| **Tier 2** | Backhaul trip-chain (`$/hr` net), NL copilot → same engine, weather risk (Open-Meteo; optional demo flag) |
| **Tier 3** | Fleet Hungarian assignment, continuous compliance state machine (Sentinel-echo), lane rate z-score flags, analytics summary |

**Invariant:** The LLM never invents scores — it only parses intent or narrates stored breakdowns.

Demo login: `demo` / `demo-pass-123`

---

## 2. Definition of Done checklist

### MVP

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 50–100 loads, 3–5 trucks with distinct HOS/market profiles | **Met** | Seed → 5 trucks, ~56+ loads (+ dedicated backhaul pair) |
| `/api/rank/` ranked, cached, factor-scored; repeat &lt; ~1s | **Met** | E2E cached ~0.02s |
| HOS-infeasible loads excluded (not just penalized) | **Met** | Unit + E2E on Austin (4h HOS) truck |
| Top-3 LLM explain grounded in score breakdown | **Met** | E2E explain count=3, load_ids ⊆ top-3 |
| Assignment chain + audit trail | **Met** | offered→accepted→dispatched→delivered; illegal skip 400 |
| Live deployed URL, free infra | **Not yet** | Local only by design; deploy is next |
| README FFC → HaulRank framing | **Met** | `README.md` lead paragraph |

### Tier 2

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Backhaul pair beats best single on ≥1 seeded scenario | **Met** | Same metric: net `$/hr`. Seeded Dallas↔Houston dry_van pair; API only returns `best_pair` when `beats_best_single` |
| Copilot ≥3 NL styles; never invents loads/numbers | **Met** | E2E 3 prompts; every result `load_id ∈ allowed_load_ids` |
| ≥1 load weather-risk with real/mocked reason | **Met** | Open-Meteo live when severe; `WEATHER_DEMO=1` forces chip (verified in E2E) |

### Tier 3

| Feature | Why (one line) | Status |
|---------|----------------|--------|
| Fleet optimize | One load per truck, globally max utility (Hungarian) | E2E + unit |
| Reliability / compliance | Weak drivers gated; polled `clear|watch|restricted|suspended` state machine | Unit + rank/assign gates · `docs/COMPLIANCE.md` |
| Rate benchmark | Z-score vs seeded lane history flags below/above market | Unit + rank field |
| Analytics summary | Post-dispatch KPIs without a charting dependency | E2E |

---

## 3. Verification commands (run these before deploy)

```bash
# Unit / edge cases
cd backend && .venv/bin/python -m pytest -q

# Frontend production build
cd frontend && npm run build

# Live stack
cd .. && docker compose up --build -d

# ONE system-health suite (brutal + compliance) — local
python3 scripts/e2e.py http://127.0.0.1:8000 http://127.0.0.1:5173

# ONE system-health suite — live
python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app
```

**Latest system E2E covers:** health, CORS, auth/JWT abuse, DEBUG leak probes, fleet ACL, rank + cache + HOS, assignment races, explain grounding, adversarial copilot, fleet opt, analytics, frontend shell, continuous compliance.

Backend verify (venv — no bare `python` on WSL):

```bash
cd backend && .venv/bin/python manage.py migrate
.venv/bin/python manage.py poll_compliance -v2
.venv/bin/python -m pytest apps/compliance/ -q
```

---

## 4. Architecture (short)

```
React (Vite/MUI) ──JWT──► Django/DRF
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               Postgres    Redis     OpenRouter
                    │                   │
              Scoring engine      Explain / Copilot
              (pure Python)       (grounded only)
                    │
         Backhaul · Fleet-opt · Rates · Weather(Open-Meteo)
```

Key paths:

| Concern | Path |
|---------|------|
| Score formula | `backend/apps/scoring/engine.py` |
| Rank API | `backend/apps/scoring/views.py` |
| Backhaul | `backend/apps/backhaul/engine.py` |
| Copilot | `backend/apps/copilot/` |
| Fleet opt | `backend/apps/fleet_opt/engine.py` |
| Reliability | `backend/apps/fleet/reliability.py` |
| Continuous compliance | `backend/apps/compliance/` · `docs/COMPLIANCE.md` |
| Rates | `backend/apps/rates/models.py` |
| Weather | `backend/integrations/openweather.py` (Open-Meteo primary) |
| LLM | `backend/integrations/llm_client.py` |
| UI | `frontend/src/pages/DispatchPage.tsx` |
| PRD | `HaulRank_PRD.md` |

More detail: `docs/architecture.md`, `docs/scoring-formula.md`, `docs/api.md`.

---

## 5. Local runbook

### Docker (recommended)

```bash
cp .env.example .env   # fill OPENROUTER_API_KEY at minimum
docker compose up --build
```

- UI: http://localhost:5173/
- API: http://localhost:8000/api/health/

Compose always sets Postgres + Redis. Empty `REDIS_URL` in `.env` is fine — Compose overrides it.

### Without Docker

```bash
# .env: DATABASE_URL=sqlite:///db.sqlite3, REDIS_URL= empty → LocMem cache
cd backend && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
# other terminal
cd frontend && npm install && npm run dev
```

---

## 6. Environment variables

| Variable | Required | Notes |
|----------|----------|--------|
| `DJANGO_SECRET_KEY` | prod yes | Change for deploy |
| `DJANGO_DEBUG` | — | `0` in prod |
| `DJANGO_ALLOWED_HOSTS` | prod yes | API hostname(s) |
| `DATABASE_URL` | yes | Neon / Compose Postgres / sqlite local |
| `REDIS_URL` | prod yes | Upstash; empty locally → LocMem |
| `CORS_ALLOWED_ORIGINS` | yes | Frontend origin(s) |
| `OPENROUTER_API_KEY` | yes for explain/copilot | `openai/gpt-4o-mini` default |
| `OPENROUTER_MODEL` | no | Default `openai/gpt-4o-mini` |
| `EIA_API_KEY` | no | Else diesel fallback $3.80 |
| `OPENWEATHER_API_KEY` | no | Backup only; Open-Meteo is primary |
| `WEATHER_DEMO` | no | `1` forces severe chip on top load |

**Never commit `.env`.** See `docs/credentials.md`.

---

## 7. API map

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/health/` | GET | no | Liveness |
| `/api/auth/register/` | POST | no | Create user + carrier |
| `/api/auth/token/` | POST | no | JWT |
| `/api/auth/token/refresh/` | POST | no | Refresh |
| `/api/trucks/` | CRUD | yes | Fleet (+ embedded driver / reliability) |
| `/api/loads/` | CRUD | yes | Synthetic board |
| `/api/rank/?truck_id=` | POST | yes | Rank + `best_single` + optional `best_pair` |
| `/api/rank/{id}/explain/` | POST | yes | Top-3 grounded narration |
| `/api/assignments/` | GET/POST/PATCH | yes | Status chain |
| `/api/assignments/{id}/history/` | GET | yes | Audit |
| `/api/copilot/` | POST | yes | NL → filters → engine → narrate |
| `/api/fleet/optimize/` | POST | yes | Multi-truck assignment |
| `/api/analytics/summary/` | GET | yes | KPIs |
| `/api/compliance/` | GET | yes | Fleet compliance snapshot |
| `/api/compliance/poll/` | POST | yes | Run one poll cycle (own fleet) |

Rank `best_pair.combined_score` is **net USD per hour** (not the 0–1 overall score). Field `metric: "net_usd_per_hour"` and `beats_best_single: true` when returned.

---

## 8. Demo script (5 minutes)

1. Open http://localhost:5173/ → login `demo` / `demo-pass-123`.
2. Select **Dallas dry_van** truck → **Rank**. Show factor columns; note cache is instant on second click.
3. Expand / show **best pair** panel (Dallas↔Houston seeded chain).
4. **Explain** top 3 — narration cites the stored factors.
5. Optional: `WEATHER_DEMO=1` recreate web → re-rank → weather chip on top load.
6. Copilot: *"dry van that nets at least 2000"* and *"loads to Texas"*.
7. Offer → accept → dispatch → deliver one load; show history.
8. **Fleet optimize** + **Analytics** panels.

Talk track (PRD §16): scoring/ranking problem; AI only explains or parses; free-tier deploy target.

---

## 9. Deploy plan (free tier)

Do this only after you say go.

| Piece | Suggested free service |
|-------|------------------------|
| Postgres | [Neon](https://neon.tech) |
| Redis | [Upstash](https://upstash.com) |
| API | [Railway](https://railway.app) or [Render](https://render.com) (`backend/` Dockerfile) |
| Frontend | [Vercel](https://vercel.com) (`frontend/`, `VITE_API_BASE` → API URL) |

Checklist:

1. Create Neon DB + Upstash Redis; copy URLs into host env (not git).
2. Deploy API with **`DJANGO_SETTINGS_MODULE=config.settings.production`** (hard-codes `DEBUG = False`) **and** set `DJANGO_DEBUG=0` in Railway/Render env anyway. Do not rely on Compose defaults — Compose is local-only; the repo’s [`docker-compose.yml`](docker-compose.yml) already hardcodes `DJANGO_DEBUG: "0"` for local Docker so `.env`’s `DJANGO_DEBUG=1` cannot leak secrets.
3. Strong `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS` = Vercel origin, migrate + `seed_demo` on release.
3. Deploy frontend with `VITE_API_BASE=https://<api-host>`.
4. Smoke: `python3 scripts/e2e.py https://<api-host> https://<ui-host>`
5. Paste live URL into README / application.

---

## 10. Known limitations (honest)

- Load board is **synthetic** (stated in README) — no live DAT/TMS.
- Calm weather → no chip unless `WEATHER_DEMO=1` or Open-Meteo reports severe codes.
- First rank can be slow when weather annotates many loads (~5–15s); **cached** repeats are &lt;1s.
- OpenWeather keys often take hours to activate — do not block on them.
- MUI chunk is large (~900KB); fine for demo, not optimized for Lighthouse.
- E2E creates spare loads when the board is fully assigned — re-seed with `--flush` for a clean board: `python manage.py seed_demo --flush`.

---

## 11. Git / authorship

Commits must be authored as **Muhammad Hamdan Ishfaq** (`hamdan-ishfaq@users.noreply.github.com`). No AI co-author trailers. Repo: https://github.com/hamdan-ishfaq/HAULRANK

---

## 12. Ready for deploy?

| Gate | Result |
|------|--------|
| Unit + edge tests | **49 passed** |
| Live E2E full suite | **Passed** |
| Frontend build | **Passed** |
| DoD except public URL | **Met** |
| Public URL | **Pending your go-ahead** |

When you are ready, say **deploy** and we will wire Neon / Upstash / Railway|Render / Vercel and land the live URL.

---

## 13. Audit remediation (2026-07-12)

Addressed before public deploy (see [docs/ADVERSARIAL_AUDIT.md](docs/ADVERSARIAL_AUDIT.md)):

- [x] `DJANGO_DEBUG=0` in Compose + opaque JSON 500 handler; `truck_id` int coerce
- [x] Rank cache fingerprints truck + load scored fields + diesel
- [x] Loads read-only for non-staff
- [x] One active assignment per load (`UniqueConstraint` + `select_for_update`)
- [x] Copilot narration grounding enforced (template fallback)
- [x] Auth burst throttle (`auth` 10/min)
- [x] Redis `IGNORE_EXCEPTIONS` + soft-fail cache I/O
- [x] Assignment HOS/equipment feasibility check
- [x] `weather_status`: `clear` | `severe` | `unavailable`
