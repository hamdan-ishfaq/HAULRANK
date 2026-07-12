# HaulRank — Product Requirements Document

**A transparent load-scoring and dispatch-ranking engine for small carriers, built to demonstrate Spotter AI's own product thesis using Django, DRF, and a lightweight AI explanation layer.**

Author: Muhammad Hamdan Ishfaq · Target: Spotter AI, Remote Backend Django Engineer (AI & Algorithmic Systems)
Status: Ready to build · Cost: $0 to build and deploy

---

## 1. Problem Statement

Small carriers and owner-operators (1–20 trucks) pick loads off load boards mostly by **eyeballing the rate**. That's the wrong number to optimize on its own:

- A $3.10/mile load with 180 miles of deadhead to pick up can net *less* than a $2.60/mile load with no deadhead.
- Fuel cost varies by region and week — a load through a high-diesel-price corridor quietly eats the margin.
- A load that looks great on rate can blow a driver's remaining Hours-of-Service (HOS), forcing an unplanned reset that kills the *next* load too.
- Dispatchers juggling multiple trucks re-do this mental math dozens of times a day, under time pressure, with no record of *why* a load was chosen — so nobody can audit or improve the decision later.

This is the exact gap Spotter AI's own product line (Spotter TMS, Spotter Extension's "Best Load" recommendations, Spotter Lens) is built to close in production. **HaulRank is a scoped-down, from-scratch version of that same problem**, solved with a transparent, explainable scoring engine instead of a black box — which is also a more honest and more interesting capstone than wrapping an API call in a UI.

## 2. Goals

1. Replace "pick by rate" with a **transparent, multi-factor score** a dispatcher can actually trust and audit.
2. Show real backend engineering: normalized relational schema, a documented scoring algorithm (not a hidden LLM call), a clean REST API, caching, and containerized local dev.
3. Add a **thin, honest AI layer on top of — not instead of — the deterministic scoring**, so the AI explains and helps query, but never decides the number.
4. Ship something demoable in a live URL with zero paid infrastructure.

### Non-goals (explicitly out of scope for the capstone)

- Real broker/load-board API integrations (synthetic seed data instead — stated openly, not disguised)
- Real ELD/HOS hardware integration
- Payments, invoicing, factoring
- React Native / mobile
- Kubernetes / GCP production deployment
- Multi-tenant auth complexity beyond basic JWT

## 3. Target User & Core User Story

**Persona:** A dispatcher or owner-operator with 1–10 trucks, checking a load board manually, who wants a fast, defensible answer to *"which of these loads should I take, and why?"*

**Core story:**
> As a dispatcher, I select a truck (with its current location, HOS hours remaining, and market preferences) and get back a ranked list of available loads, each with a numeric score and a visible breakdown of exactly what drove that score — plus a one-paragraph plain-English explanation of the top pick.

## 4. Where AI Actually Fits (and where it deliberately doesn't)

This is the part most capstones get wrong — bolting an LLM onto everything to look "AI-powered." HaulRank draws the line deliberately, because that line *is* the engineering judgment Spotter is hiring for:

| Layer | Owned by | Why |
|---|---|---|
| The score itself (rate/mi, deadhead, fuel, HOS fit, market fit) | **Deterministic weighted formula, in Django** | Money decisions need to be auditable and reproducible. A dispatcher needs to trust the number every time, not just when the model feels like it. This mirrors real scoring/ranking/decision-rule systems, which is literally the JD's core ask. |
| "Why is this the top load?" explanation | **LLM (Groq free tier), grounded in the score breakdown JSON** | The LLM is only ever asked to *narrate a number that already exists* — it's given the exact factor breakdown and told to explain it, not asked to invent a score. This is retrieval-grounded generation applied to structured data instead of documents — a direct, honest reuse of your Hermes/JurisGuard RAG-grounding experience, scoped correctly. |
| Natural-language load search ("show me loads to Texas under 2 days that don't blow my HOS") | **LLM → structured filter → same deterministic ranking engine** | The LLM's only job is parsing intent into filter parameters; ranking still runs through the same trusted formula. Delivered as Tier 2 Copilot. |
| Anomaly flag ("this rate is unusually low for this lane") | **Simple statistical z-score against seeded historical rates**, optionally narrated by the LLM | Cheap, defensible, and avoids pretending an LLM can detect fraud from a paragraph of context it doesn't have. Tier 3. |

This design is your interview answer to "tell me about the AI in this project": *the AI explains and assists, it never decides the money-relevant number.* That's a mature, hire-me answer for an "AI & Algorithmic Systems" backend role — it shows you understand the difference between a feature that uses AI and a feature that outsources judgment to it.

## 5. Spotter AI Alignment (say this explicitly in your application)

| Spotter AI product | What it does | HaulRank equivalent |
|---|---|---|
| Spotter Extension — "Best Load" recommendations, AI pricing analysis | Recommends best load to a dispatcher/broker inside their workflow | HaulRank's `/api/rank/` endpoint — same concept, built from scratch |
| Spotter TMS | Core dispatch/operations system of record | HaulRank's Carrier → Truck → Driver → Load → Assignment schema |
| Spotter's general thesis ("AI as buzzword vs. AI reducing real friction," per their marketing lead) | AI should remove friction, not decide everything | HaulRank's explicit deterministic-score / AI-explanation split (Section 4) |
| FFC internship (your own background) | Order-to-Cash / haulage allocation / document-flow discipline in live ERP | HaulRank's Assignment status chain: `offered → accepted → dispatched → delivered` mirrors FFC's `Order → Allocation → Shipment → Goods Issue → Billing` |

Put a short paragraph like this near the top of your project README — it's the single highest-leverage sentence in your whole application:

> "At FFC I traced how a fertilizer order becomes a truck movement, an allocation, and a billing document — real freight, real audit trail. HaulRank applies that same document-flow discipline to load ranking: every score is reproducible, every assignment has a state, and the AI layer only ever explains a number the backend already computed."

## 6. System Architecture

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
│  React + MUI UI  │────▶│  Django + DRF API         │────▶│  PostgreSQL      │
│  (Vercel/CF Pages)│     │  (Render/Railway)         │     │  (Neon/Supabase) │
└─────────────────┘     │                            │     └─────────────────┘
                         │  ┌──────────────────────┐  │
                         │  │ Scoring Engine        │  │     ┌─────────────────┐
                         │  │ (pure Python, tested) │  │────▶│  Redis (Upstash) │
                         │  └──────────────────────┘  │     │  score-run cache  │
                         │  ┌──────────────────────┐  │     └─────────────────┘
                         │  │ Explanation Service    │  │
                         │  │ → Groq API (free tier) │  │     ┌─────────────────┐
                         │  └──────────────────────┘  │────▶│  EIA Open Data   │
                         └──────────────────────────┘     │  (weekly diesel)  │
                                                            └─────────────────┘
```

## 7. Data Model (Django ORM)

```python
class Carrier(models.Model):
    name = models.CharField(max_length=120)

class Truck(models.Model):
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE)
    equipment_type = models.CharField(max_length=40)  # dry_van, reefer, flatbed
    current_lat = models.FloatField()
    current_lon = models.FloatField()
    mpg = models.FloatField(default=6.5)

class Driver(models.Model):
    truck = models.OneToOneField(Truck, on_delete=models.CASCADE)
    hos_hours_remaining = models.FloatField()
    home_base_lat = models.FloatField()
    home_base_lon = models.FloatField()
    preferred_markets = models.JSONField(default=list)   # ["TX","OK"]
    no_go_markets = models.JSONField(default=list)        # ["NYC","LA metro"]

class Load(models.Model):
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    dest_lat = models.FloatField()
    dest_lon = models.FloatField()
    dest_market = models.CharField(max_length=40)
    miles = models.FloatField()
    rate_usd = models.FloatField()
    equipment_type = models.CharField(max_length=40)
    pickup_window_start = models.DateTimeField()
    pickup_window_end = models.DateTimeField()
    est_transit_hours = models.FloatField()

class ScoreRun(models.Model):
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class ScoreBreakdown(models.Model):
    score_run = models.ForeignKey(ScoreRun, related_name="results", on_delete=models.CASCADE)
    load = models.ForeignKey(Load, on_delete=models.CASCADE)
    rate_per_mile_score = models.FloatField()
    deadhead_penalty = models.FloatField()
    fuel_efficiency_score = models.FloatField()
    hos_feasibility = models.FloatField()      # 0 if infeasible — hard filter, not just a penalty
    market_preference_score = models.FloatField()
    overall = models.FloatField()
    explanation_text = models.TextField(blank=True)  # filled lazily by LLM, only for top N

class Assignment(models.Model):
    load = models.ForeignKey(Load, on_delete=models.CASCADE)
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[
        ("offered", "Offered"), ("accepted", "Accepted"),
        ("dispatched", "Dispatched"), ("delivered", "Delivered"),
    ], default="offered")
    status_history = models.JSONField(default=list)  # audit trail, FFC-style
```

## 8. Scoring Algorithm

Pure, unit-tested Python — no LLM in this function, on purpose:

```
overall =
    0.30 * rate_per_mile_score        # normalized $/mile vs lane baseline
  + 0.25 * deadhead_penalty_inverted  # miles from truck's current location to origin
  + 0.20 * fuel_efficiency_score      # rate minus EIA regional diesel cost / truck mpg
  + 0.15 * hos_feasibility            # HARD FILTER: 0 if pickup+transit exceeds hours_remaining
  + 0.10 * market_preference_score    # +1 preferred market, -1 no-go market, 0 neutral
```

Each sub-score is normalized 0–1 against the current batch of loads before weighting, so the formula stays meaningful regardless of how rates vary week to week. `hos_feasibility = 0` removes a load from the ranked list entirely rather than just docking points — infeasible loads should never appear as "top pick."

## 9. API Surface (DRF)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/trucks/` | GET/POST | CRUD trucks + drivers |
| `/api/loads/` | GET/POST | CRUD load board (seeded) |
| `/api/rank/?truck_id=` | POST | Run scoring engine, return ranked loads + breakdown (cached in Redis per truck+load-batch hash) |
| `/api/rank/{score_run_id}/explain/` | POST | Lazily generate LLM explanation for top 3 results only (cost control) |
| `/api/assignments/` | POST/PATCH | Move a load through `offered → accepted → dispatched → delivered` |
| `/api/assignments/{id}/history/` | GET | Audit trail — the FFC document-flow parallel |
| `/api/copilot/` | POST | Tier 2: NL intent → filters → same engine → grounded narration |

## 10. Frontend (React + MUI) — MVP screens

1. **Truck selector** — dropdown, shows HOS hours remaining and current location
2. **Ranked load table** — MUI `DataGrid`, sortable, score shown as a progress bar, factor chips (rate/deadhead/fuel/HOS/market) color-coded
3. **"Why this load?"** — expandable panel per row showing the breakdown numbers + the LLM's one-paragraph explanation for top 3
4. **Assignment tracker** — simple Kanban-style status chain (offered → accepted → dispatched → delivered)

## 11. Fully Free Tech Stack

| Layer | Choice | Free tier notes |
|---|---|---|
| Backend | Django + Django REST Framework | Open source |
| DB | Neon or Supabase Postgres | Free tier covers this scale easily |
| Cache | Upstash Redis | Free tier, used to cache score runs by truck+load-batch hash |
| Fuel data | EIA Open Data API | Free API key, weekly regional diesel prices |
| Distance | Haversine / seeded lane miles | Avoids paid mapping APIs |
| Load data | Synthetic seed CSV, clearly labeled as synthetic in README | No paid load-board API needed |
| LLM explanation | Groq API free tier (Llama 3.1 8B) | Grounded one-paragraph explanations |
| Backend hosting | Render or Railway free tier | Auto-deploy from GitHub |
| Frontend hosting | Vercel or Cloudflare Pages free tier | Auto-deploy from GitHub |
| Local dev | Docker Compose (Django + Postgres + Redis) | Matches the JD's Docker bonus point directly |
| Auth | Django's built-in auth + DRF SimpleJWT | No paid auth provider needed |
| Weather (Tier 2) | OpenWeatherMap free tier | Disruption risk flag |

## 12. Differentiator Features (Tier 2 — build after MVP)

### 12.1 Backhaul / Trip-Chain Optimizer
For each candidate load, look up top return loads near destination (radius + HOS after first leg). Score combined round-trip. Model: `TripChain(outbound, return_load, combined_score, total_deadhead_miles)`.

### 12.2 AI Dispatcher Copilot
Chat endpoint: LLM parses filters → deterministic scoring/backhaul → LLM narrates returned results only. Never invents loads/rates.

### 12.3 Disruption-Aware ETA Risk Flag
OpenWeatherMap forecast at route midpoint; severe weather reduces HOS feasibility and shows a weather-risk chip.

## 13. Tier 3 — Optional Stretch Features

1. **Multi-Truck Fleet Optimization** — `scipy.optimize.linear_sum_assignment` on score_load cost matrix
2. **Rate Benchmarking** — z-score vs seeded 12-week lane history
3. **Driver Safety/Compliance Score** — Sentinel-echo synthetic reliability badge
4. **Analytics Dashboard** — Recharts over ScoreRun/Assignment history

Suggested order: 13.1 → 13.3 → 13.2 → 13.4.

## 14. Build Plan

| Days | Milestone |
|---|---|
| 1–2 | Django scaffold, models, migrations, admin, Docker Compose |
| 3–4 | Scoring engine unit-tested |
| 5 | DRF `/api/rank/`, seed data |
| 6 | Redis cache; Assignments + history |
| 7–8 | React + MUI dashboard |
| 9 | Groq explain top-3 |
| 10–11 | Deploy + README |
| 12 | MVP demo video |
| 13 | Tier 2 backhaul |
| 14 | Tier 2 copilot |
| 15 | Tier 2 weather |
| 16 | Re-demo + README pitch |
| 17+ | Tier 3 as time allows |

## 15. Definition of Done

### MVP
- [ ] 50–100 seeded loads, 3–5 trucks/drivers with distinct HOS/market profiles
- [ ] `/api/rank/` returns a ranked, cached, factor-scored list in under ~1s on repeat calls
- [ ] HOS-infeasible loads are excluded, not just penalized
- [ ] Top-3 loads have an LLM explanation grounded in their own score breakdown
- [ ] Assignment status chain works end-to-end with a visible audit trail
- [ ] Live deployed URL, no paid infrastructure
- [ ] README leads with the FFC → HaulRank framing paragraph from Section 5

### Tier 2
- [ ] Backhaul optimizer returns a combined-score pair that clearly beats the best single load on ≥1 seeded scenario
- [ ] Copilot answers ≥3 distinct NL query styles and never returns a load/number it wasn't handed by the scoring engine
- [ ] ≥1 seeded load shows a weather-risk flag with a real or realistically mocked forecast reason

### Tier 3 (optional)
- [ ] Each built feature works end-to-end and has a one-line README "why"

## 16. How to Talk About This in the Application / Interview

> "Spotter's product is fundamentally a scoring and ranking problem wearing a trucking-industry UI — best load, best driver, best route. HaulRank is my from-scratch version of that: a Django/DRF backend with a transparent, weighted scoring formula for rate, deadhead, fuel, and HOS feasibility; a backhaul optimizer that scores round-trip pairs instead of single loads to cut deadhead waste; a dispatcher copilot that parses natural-language questions into the same deterministic engine and narrates its real output; and a weather-aware disruption flag on delivery windows. The AI layer only ever explains or parses — it never invents the number a dispatcher is trusting with real money. Deployed end-to-end for free."
