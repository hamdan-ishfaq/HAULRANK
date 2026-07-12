# Architecture

```
React (Vite/MUI) → Django/DRF → Postgres
                      ↓
               Scoring engine (pure Python)
                      ↓
     Redis cache | OpenRouter explain/copilot | EIA diesel | Open-Meteo weather
```

Tier 2: backhaul (same engine + `$/hr` net pair), copilot (parse → engine → narrate), weather risk.

Tier 3: fleet Hungarian assignment, reliability gate, lane z-score, analytics summary.

Invariant: LLM never writes scores.
