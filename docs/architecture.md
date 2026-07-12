# Architecture

```
React (Vite/MUI) → Django/DRF → Postgres
                      ↓
               Scoring engine (pure Python)
                      ↓
            Redis cache | Groq explain | EIA diesel
```

Tier 2 adds backhaul (same engine twice), copilot (parse → engine → narrate), weather (OpenWeatherMap).

Invariant: LLM never writes scores.
