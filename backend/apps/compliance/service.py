"""Apply continuous compliance polls to Driver rows."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.compliance.engine import evaluate_compliance
from apps.fleet.models import Driver

logger = logging.getLogger("haulrank.compliance")


def verdict_for_driver(driver: Driver):
    return evaluate_compliance(
        driver.hos_violations_90d,
        driver.inspection_pass_rate,
        driver.on_time_pct,
    )


def apply_verdict(driver: Driver, *, dry_run: bool = False) -> dict[str, Any]:
    verdict = verdict_for_driver(driver)
    prev = driver.compliance_state or "clear"
    changed = prev != verdict.state
    entry = {
        "at": timezone.now().isoformat(),
        "from": prev,
        "to": verdict.state,
        "score": verdict.score,
        "reasons": list(verdict.reasons),
    }
    result = {
        "driver_id": driver.pk,
        "truck_id": driver.truck_id,
        "from": prev,
        "to": verdict.state,
        "changed": changed,
        "score": verdict.score,
        "reasons": list(verdict.reasons),
    }
    if dry_run or not changed:
        if not dry_run:
            # still refresh checked_at / reason even if state unchanged
            Driver.objects.filter(pk=driver.pk).update(
                compliance_reason="; ".join(verdict.reasons),
                compliance_checked_at=timezone.now(),
            )
        return result

    history = list(driver.compliance_history or [])
    history.append(entry)
    # keep last 50 transitions
    history = history[-50:]
    Driver.objects.filter(pk=driver.pk).update(
        compliance_state=verdict.state,
        compliance_reason="; ".join(verdict.reasons),
        compliance_checked_at=timezone.now(),
        compliance_history=history,
    )
    logger.info(
        "compliance transition truck=%s %s→%s score=%s reasons=%s",
        driver.truck_id,
        prev,
        verdict.state,
        verdict.score,
        list(verdict.reasons),
    )
    return result


@transaction.atomic
def poll_all_drivers(*, dry_run: bool = False, owner=None) -> dict[str, Any]:
    """Re-evaluate drivers. Idempotent. Never auto-dispatches.

    If owner is set, only that carrier owner's fleet is polled (API path).
    Management command / Celery omit owner and poll everyone.
    """
    qs = Driver.objects.select_related("truck").order_by("id")
    if owner is not None:
        qs = qs.filter(truck__carrier__owner=owner)
    rows = []
    changed = 0
    for driver in qs:
        row = apply_verdict(driver, dry_run=dry_run)
        rows.append(row)
        if row["changed"]:
            changed += 1
    return {
        "checked": len(rows),
        "changed": changed,
        "dry_run": dry_run,
        "results": rows,
    }
