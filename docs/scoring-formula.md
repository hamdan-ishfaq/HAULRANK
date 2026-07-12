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

HOS infeasible (`deadhead_hours + est_transit_hours > hos_hours_remaining`) → load is **excluded**.

Equipment mismatch → excluded.

Implementation: `backend/apps/scoring/engine.py`.
