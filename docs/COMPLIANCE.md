# Continuous compliance (Sentinel-echo)

HaulRank’s reliability gate was a one-shot score check at rank time. This module
turns that into a **polled state machine** inspired by Spotter Sentinel:

- **Deterministic rules only** — no LLM, no auto-accept/auto-assign.
- **Eligibility revoke only** — `suspended` blocks rank + new assignments;
  `restricted` gates high-value loads (≥ $2000), same bar as the old score gate.
- **States:** `clear` → `watch` → `restricted` → `suspended` (strictest wins).

## How to run the poll

```bash
# One-shot (Render cron / local / seed_demo already calls this)
cd backend && .venv/bin/python manage.py poll_compliance
.venv/bin/python manage.py poll_compliance --dry-run -v2

# System health (includes compliance section)
python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app

# API (own fleet only)
POST /api/compliance/poll/
GET  /api/compliance/
```

## Optional Celery

Scoped learning use case — scheduled poll every 15 minutes when Redis + workers
are available. Free-tier Render can skip workers and use cron instead.

```bash
pip install celery   # already in requirements.txt
celery -A config worker -l info
celery -A config beat -l info
```

Set `CELERY_TASK_ALWAYS_EAGER=1` in tests if you invoke the task inline.

## Code map

| Piece | Path |
|-------|------|
| Pure rules | `apps/compliance/engine.py` |
| Persist transitions | `apps/compliance/service.py` |
| Management command | `apps/compliance/management/commands/poll_compliance.py` |
| Celery task | `apps/compliance/tasks.py` |
| Driver fields | `Driver.compliance_*` on `apps/fleet/models.py` |
| Gates | `apps/scoring/views.py`, `apps/assignments/serializers.py` |
