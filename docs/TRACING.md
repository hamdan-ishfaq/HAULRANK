# Complete tracing guide (Vercel + Render)

When the UI only says “Login failed,” you are missing the signal. Logs live in **three places**. Use all three.

```
Browser Console/Network  →  Render Logs (Django)  →  Sentry (optional crashes)
```

---

## 1. Immediate diagnosis (do this before changing code)

### A. Browser (frontend)

1. Open your Vercel site.
2. Right-click → **Inspect** → **Network**.
3. Check **Preserve log**.
4. Click **Sign in**.
5. Find the request to `/api/auth/token/`.

| What you see | Meaning |
|--------------|---------|
| No `/api/auth/token/` row at all | JS never called the API (wrong build / crash before fetch) |
| Request URL is `http://127.0.0.1:8000/...` | `VITE_API_BASE` missing at **Vercel build** time — fix env + **Redeploy** |
| Status `(failed)` / CORS error in Console | Request blocked in browser — Render may show **nothing**. Fix `CORS_ALLOWED_ORIGINS` on Render to exact Vercel origin |
| Status `401` | Wrong password or demo user missing (`seed_demo` not run) |
| Status `429` | Auth throttle — wait ~1 min |
| Status `500` | Django crashed — open Render Logs for stack trace |

Also check **Console** for `[HaulRank API]` lines (after the tracing deploy below).

### B. Render (backend)

1. Render dashboard → **haulrank-api** → **Logs**.
2. Click Sign in again while watching Logs.

| Render shows | Meaning |
|--------------|---------|
| Nothing when you click Login | Browser never reached Django (CORS / wrong host / cold start still waking — wait 60s and retry) |
| `rid=... method=POST path=/api/auth/token/ status=401` | Django got it; credentials rejected |
| `status=500` + traceback | Server bug — copy the `rid=` and traceback |
| `DisallowedHost` | Add hostname to `DJANGO_ALLOWED_HOSTS` |

Warm the API first:

```bash
curl https://YOUR-API.onrender.com/api/health/
```

---

## 2. What we added in the codebase

| Layer | What | Where you see it |
|-------|------|------------------|
| Request trace | Every HTTP hit logs `rid`, method, path, status, ms, Origin | Render **Logs** |
| Exception log | Handled + unhandled API errors with `rid` | Render **Logs** |
| Login UI | Shows real status (401/429/500/network) + `API_BASE` on the page | Browser |
| Browser console | `[HaulRank API]` network/error objects | DevTools Console |
| Sentry (optional) | Crash dashboard + email | sentry.io |

Match a failed login: copy `X-Request-ID` / `rid=` from the UI/Network headers and search that string in Render Logs.

---

## 3. Deploy the tracing changes

```bash
cd ~/HaulRank
git checkout main
git pull
# (or push the commit from this session)
git push origin main
```

Render auto-redeploys from `main`. Vercel: **Redeploy** the frontend so the clearer login errors ship.

Confirm:

```bash
curl -s -D - -o /dev/null -X POST https://YOUR-API.onrender.com/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"wrong"}'
# Look for X-Request-ID in response headers
# Render Logs should show status=401 for that path
```

---

## 4. Optional: Sentry (crash dashboard)

1. Sign up at [sentry.io](https://sentry.io) → create a **Django** project.
2. Copy the **DSN**.
3. Render → Environment → add:
   ```
   SENTRY_DSN=https://...@o....ingest.sentry.io/...
   SENTRY_ENVIRONMENT=production
   SENTRY_TRACES_SAMPLE_RATE=0.2
   ```
4. Save (redeploy). Force a test 500 if needed; it should appear in Sentry within seconds.

`sentry-sdk` is already in `backend/requirements.txt`. Init runs only when `SENTRY_DSN` is set ([`production.py`](../backend/config/settings/production.py)).

---

## 5. Checklist for “Login failed” with no detail

1. Warm API: `curl .../api/health/`
2. Network tab: what URL + status for `/api/auth/token/`?
3. Login page footer: does **API:** show your Render URL or localhost?
4. Render Logs: any `haulrank.request` line for that click?
5. If CORS: set  
   `CORS_ALLOWED_ORIGINS=https://YOUR-APP.vercel.app`  
   (exact, https, no trailing slash) and redeploy API.
6. If 401 after seed: Render start command must include `python manage.py seed_demo`.

---

## 6. Where logs are generated (map)

| Event | Generated in | Stored / viewed in |
|-------|----------------|--------------------|
| Click Sign in | Browser JS | Console (client only) |
| `fetch` to API | Browser | Network tab |
| Django receives request | `RequestTraceMiddleware` | Render Logs (`stdout`) |
| JWT reject / validation | DRF + our exception handler | Render Logs |
| Unhandled crash | exception handler + Sentry | Render Logs + Sentry |
| Cold start | Render platform | Logs delay 30–60s first hit |
