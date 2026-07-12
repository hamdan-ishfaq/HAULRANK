"""Grounded LLM explanations — narrate stored scores only."""

from __future__ import annotations

import json
import logging

from apps.scoring.models import ScoreBreakdown, ScoreRun
from integrations import llm_client

logger = logging.getLogger("haulrank.explain")

SYSTEM = (
    "You explain trucking load scores. Use ONLY the JSON numbers given. "
    "Do not invent rates, miles, or scores. One short paragraph."
)


def grounded_fallback(payload: dict) -> str:
    """Deterministic narration from stored numbers — used when LLM times out/fails."""
    return (
        f"Rank #{payload['rank']} overall {payload['overall']:.2f} to {payload['dest_market']}: "
        f"${payload['rate_usd']:.0f} for {payload['miles']:.0f} mi "
        f"(${payload['rate_per_mile']:.2f}/mi, score {payload['rate_per_mile_score']:.2f}); "
        f"deadhead {payload['deadhead_miles']:.0f} mi (penalty {payload['deadhead_penalty']:.2f}); "
        f"fuel {payload['fuel_efficiency_score']:.2f}, HOS {payload['hos_feasibility']:.2f}, "
        f"market {payload['market_preference_score']:.2f}."
    )


def explain_top_n(score_run: ScoreRun, n: int = 3) -> list[ScoreBreakdown]:
    rows = list(score_run.results.select_related("load").order_by("rank")[:n])
    for row in rows:
        if row.explanation_text:
            continue
        payload = {
            "rank": row.rank,
            "overall": row.overall,
            "rate_per_mile": row.rate_per_mile,
            "rate_per_mile_score": row.rate_per_mile_score,
            "deadhead_miles": row.deadhead_miles,
            "deadhead_penalty": row.deadhead_penalty,
            "fuel_efficiency_score": row.fuel_efficiency_score,
            "hos_feasibility": row.hos_feasibility,
            "market_preference_score": row.market_preference_score,
            "dest_market": row.load.dest_market,
            "miles": row.load.miles,
            "rate_usd": row.load.rate_usd,
        }
        try:
            text = llm_client.complete(SYSTEM, json.dumps(payload))
        except Exception as exc:  # noqa: BLE001 — never stall dispatch UI on LLM
            logger.warning("explain LLM fallback load=%s: %s", row.load_id, exc)
            text = grounded_fallback(payload)
        row.explanation_text = text
        row.save(update_fields=["explanation_text"])
    return rows
