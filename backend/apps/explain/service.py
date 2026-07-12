"""Grounded LLM explanations — narrate stored scores only."""

from __future__ import annotations

import json

from apps.scoring.models import ScoreBreakdown, ScoreRun
from integrations import llm_client

SYSTEM = (
    "You explain trucking load scores. Use ONLY the JSON numbers given. "
    "Do not invent rates, miles, or scores. One short paragraph."
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
        text = llm_client.complete(SYSTEM, json.dumps(payload))
        row.explanation_text = text
        row.save(update_fields=["explanation_text"])
    return rows
