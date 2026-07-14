# HaulRank

Transparent load-scoring and dispatch-ranking for small carriers — a scoped-down, from-scratch take on Spotter AI’s product thesis.

> At FFC I traced how a fertilizer order becomes a truck movement, an allocation, and a billing document — real freight, real audit trail. HaulRank applies that same document-flow discipline to load ranking: every score is reproducible, every assignment has a state, and the AI layer only ever explains a number the backend already computed.

## What it does

1. **Deterministic score** — rate/mi, deadhead, fuel (EIA), HOS feasibility, market fit (pure Python, unit-tested).
2. **Rank API** — ranked loads + factor breakdown, Redis-cached.
3. **Grounded explanations** — Groq narrates stored breakdowns for top 3 only (never invents the score).
4. **Assignments** — `offered → accepted → dispatched → delivered` with audit history.
5. **Tier 2** — backhaul trip-chain, dispatcher copilot (intent → same engine), weather risk (Open-Meteo).
6. **Tier 3** — fleet Hungarian + OR-Tools CP-SAT MIP assignment, continuous compliance (Sentinel-echo), rate z-score flags, analytics; copilot tool-calling over rank/optimize.

Load board data is **synthetic** (seeded CSV/JSON), stated openly — no fake live DAT integration.

## Stack

| Layer | Choice |
|-------|--------|
| API | Django + DRF + SimpleJWT |
| DB / cache | Postgres + Redis |
| UI | React + Vite + MUI |
| Local | Docker Compose |

## Repo layout

```
backend/     Django apps (fleet, loads, scoring, …)
frontend/    React + MUI
docs/        architecture, formula, API notes
```

## Local dev

### Option A — Docker (recommended)

```bash
docker compose up --build
```

Then open:
- UI: http://localhost:5173/
- API: http://localhost:8000/api/health/

Login: `demo` / `demo-pass-123`

### Option B — without Docker

```bash
cp .env.example .env
cd backend && source .venv/bin/activate   # or: uv venv && uv pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
# other terminal:
cd frontend && npm install && npm run dev
```

### Post-deploy PUNISH E2E (one command)

Adversarial live suite: auth/CORS/JWT abuse, leak probes, rank/cache/HOS, assignment races (10 trials), explain grounding, copilot adversarial + optimize tool path, **MIP/Hungarian/brownfield locks**, compliance Sentinel, frontend shell.

```bash
# After push + Render/Vercel deploy — warm API first
curl -sS https://haulrank-pdmh.onrender.com/api/health/

python3 scripts/e2e_punish.py \
  https://haulrank-pdmh.onrender.com \
  https://haulrank.vercel.app

# Aliases
python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app
make e2e-live
```

Unit tests: `cd backend && .venv/bin/python -m pytest -q`

Handoff: [HANDOFF.md](HANDOFF.md). Fleet MIP: [docs/FLEET_MIP.md](docs/FLEET_MIP.md). Compliance: [docs/COMPLIANCE.md](docs/COMPLIANCE.md). Deploy: [docs/DEPLOY.md](docs/DEPLOY.md). Tracing: [docs/TRACING.md](docs/TRACING.md).

**Brownfield seed (locked accepted/dispatched pairs for residual fleet opt):**  
`cd backend && .venv/bin/python manage.py seed_demo --brownfield`  
Freight brownfield lock = planning analogy for inserting capacity beside a committed plan — not a digital twin / facility geometry.

## Branches

`main` (releases) ← `develop` ← `feature/<module>`

## Product docs

See [HaulRank_PRD.md](HaulRank_PRD.md).
