# Scoring formula

```
overall =
    0.30 * rate_per_mile_score
  + 0.25 * deadhead_penalty_inverted
  + 0.20 * fuel_efficiency_score
  + 0.15 * hos_feasibility
  + 0.10 * market_preference_score
```

Each continuous factor is min-max normalized 0–1 within the current batch before weighting.

**HOS:** infeasible when `deadhead_hours + est_transit_hours > hos_hours_remaining` (strict `>`). Equality is **included** as feasible — product decision, not a bug.

**Equipment** mismatch → excluded.

**Non-physical inputs:** `miles <= 0` or `rate_usd < 0` → excluded.

**Backhaul radius:** return origin must be `<= 75` mi from outbound dest. Floating-point construction of “exactly 75.0” can overshoot by ~1e-13 and be excluded; treat the boundary as approximate.

Implementation: `backend/apps/scoring/engine.py`, `backend/apps/backhaul/engine.py`.
