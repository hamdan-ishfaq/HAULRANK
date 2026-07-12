# Credentials & deployment

## Required for full local “majesty”

| Key | Used for | Free signup | Without it |
|-----|----------|-------------|------------|
| `OPENROUTER_API_KEY` | Explain + Copilot | https://openrouter.ai/keys | Explain/Copilot return 503 |
| `OPENWEATHER_API_KEY` | Live weather risk | https://home.openweathermap.org/api_keys (Free) | Demo “severe” flag on top load still works |
| `EIA_API_KEY` | Weekly US diesel $ | https://www.eia.gov/opendata/register.php | Fixed fallback $3.80/gal |

Default LLM model: `openai/gpt-4o-mini` via OpenRouter (cheap, good at JSON). Override with `OPENROUTER_MODEL` if you want (e.g. `google/gemini-2.0-flash-001`).

## Do you need deployment?

**Yes for the Spotter application** — PRD Definition of Done requires a live URL. Local Docker is enough to develop/demo to yourself; the résumé/application needs a public link.

Suggested $0 stack (after local works):

1. **Neon** — Postgres → `DATABASE_URL`
2. **Upstash** — Redis → `REDIS_URL`
3. **Railway or Render** — Django (`web`) + env vars from `.env.example`
4. **Vercel** — `frontend/` with `VITE_API_BASE=https://your-api…`

Not required for coding: Kubernetes, paid load-board APIs, ELD hardware.
