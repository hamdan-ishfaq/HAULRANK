# Credentials & deployment

## REDIS_URL empty in `.env`?

**Normal.** With `docker compose`, Redis is set inside Compose as `redis://redis:6379/0` and overrides the empty local value. You do **not** need to paste a Redis URL for local Docker.

Without Docker, empty `REDIS_URL` → in-memory cache (fine for solo dev).

## Weather (no waiting on OpenWeather)

HaulRank uses **[Open-Meteo](https://open-meteo.com/)** by default — free, no signup, no activation delay, no GitHub key scrape needed.

Optional later:
- `OPENWEATHER_API_KEY` — used only if Open-Meteo fails (keys can take hours to activate)
- `WEATHER_DEMO=1` — force a severe chip on the top load for demos when skies are clear

## Keys you already have / may add

| Key | Status |
|-----|--------|
| `OPENROUTER_API_KEY` | Required for Explain + Copilot |
| `EIA_API_KEY` | Optional; live diesel $. Without it → $3.80 fallback |
| `OPENWEATHER_API_KEY` | Optional backup; Open-Meteo is primary |

## Deploy (when ready for Spotter live URL)

Neon Postgres + Upstash Redis + Railway/Render API + Vercel frontend. Not required to keep coding locally.
