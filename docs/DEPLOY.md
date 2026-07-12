# Free-tier deploy (Neon + Upstash + Render + Vercel)

No credit card on this path. Render free web services sleep after ~15 minutes idle (30–60s cold start).

## Prerequisites

- Code on `main` at GitHub (`hamdan-ishfaq/HAULRANK`)
- OpenRouter API key
- Secret: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`

## Services

| Piece | Service | Notes |
|-------|---------|--------|
| Postgres | [Neon](https://neon.tech) | Use **pooled** `DATABASE_URL` |
| Redis | [Upstash](https://upstash.com) | Use `rediss://` URL |
| API | [Render](https://render.com) Web Service | Root: `backend`, Docker, Free |
| UI | [Vercel](https://vercel.com) | Root: `frontend` |

## Render env (required)

```
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated>
DJANGO_ALLOWED_HOSTS=<your-service>.onrender.com
DATABASE_URL=<Neon pooled URL>
REDIS_URL=<Upstash rediss:// URL>
CORS_ALLOWED_ORIGINS=https://<your-app>.vercel.app
OPENROUTER_API_KEY=<key>
OPENROUTER_MODEL=openai/gpt-4o-mini
WEATHER_DEMO=0
```

## Render start command

```sh
sh -c "python manage.py migrate --noinput && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
```

## Vercel

- Root Directory: `frontend`
- Env: `VITE_API_BASE=https://<your-service>.onrender.com` (no trailing slash)
- Rebuild after setting `VITE_API_BASE`

## Smoke

```bash
curl https://<api>.onrender.com/api/health/
# demo / demo-pass-123
```

Warm the API before sharing the link with a recruiter.
