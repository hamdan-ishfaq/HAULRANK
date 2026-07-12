"""Optional Celery tasks — scheduled compliance poll.

Run locally (needs Redis + celery installed):
  celery -A config worker -l info
  celery -A config beat -l info

Free-tier Render can skip workers and use cron:
  python manage.py poll_compliance
"""

from __future__ import annotations

import logging

logger = logging.getLogger("haulrank.compliance")

try:
    from celery import shared_task
except ImportError:  # pragma: no cover — celery optional until installed

    def shared_task(*_args, **_kwargs):
        def deco(fn):
            return fn

        return deco


@shared_task(name="apps.compliance.tasks.poll_compliance")
def poll_compliance_task():
    from apps.compliance.service import poll_all_drivers

    summary = poll_all_drivers(dry_run=False)
    logger.info(
        "celery compliance poll checked=%s changed=%s",
        summary["checked"],
        summary["changed"],
    )
    return {"checked": summary["checked"], "changed": summary["changed"]}
