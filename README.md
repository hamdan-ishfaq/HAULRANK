# HaulRank

Transparent load-scoring and dispatch-ranking for small carriers — a scoped-down, from-scratch take on Spotter AI’s product thesis.

> At FFC I traced how a fertilizer order becomes a truck movement, an allocation, and a billing document — real freight, real audit trail. HaulRank applies that same document-flow discipline to load ranking: every score is reproducible, every assignment has a state, and the AI layer only ever explains a number the backend already computed.

## What it does

1. **Deterministic score** — rate/mi, deadhead, fuel (EIA), HOS feasibility, market fit (pure Python, unit-tested).
2. **Rank API** — ranked loads + factor breakdown, Redis-cached.
3. **Grounded explanations** — Groq narrates stored breakdowns for top 3 only (never invents the score).
4. **Assignments** — `offered → accepted → dispatched → delivered` with audit history.
5. **Tier 2** — backhaul trip-chain, dispatcher copilot (intent → same engine), weather risk flag.

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

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000/api/health/
- UI: http://localhost:5173 (when frontend container/dev server is up)

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Branches

`main` (releases) ← `develop` ← `feature/<module>`

## Product docs

See [HaulRank_PRD.md](HaulRank_PRD.md).
