"""Copilot: LLM parses filters → deterministic engine → grounded narrate."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from apps.backhaul.engine import best_chain_for_top_outbounds
from apps.scoring.engine import LoadInput, TruckInput, rank_loads
from integrations import llm_client

FILTER_KEYS = {"dest_region", "deadline", "min_net", "equipment", "prefer_backhaul"}

PARSE_SYSTEM = (
    "Extract load-search filters as JSON only. Keys allowed: "
    "dest_region (string), deadline (ISO date or null), min_net (number or null), "
    "equipment (dry_van|reefer|flatbed or null), prefer_backhaul (bool). "
    "No other keys. No prose."
)

NARRATE_SYSTEM = (
    "Narrate the ranking results for a dispatcher. Use ONLY the provided JSON. "
    "Do not invent loads, rates, or scores. Short paragraph."
)


def parse_filters(message: str) -> dict[str, Any]:
    raw = llm_client.complete(PARSE_SYSTEM, message)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("Could not parse filters")
    data = json.loads(match.group())
    if not isinstance(data, dict):
        raise ValueError("Filters must be an object")
    unknown = set(data) - FILTER_KEYS
    if unknown:
        raise ValueError(f"Unknown filter keys: {sorted(unknown)}")
    return {k: data[k] for k in FILTER_KEYS if k in data and data[k] is not None}


def apply_filters(loads: list[LoadInput], filters: dict[str, Any]) -> list[LoadInput]:
    out = loads
    if eq := filters.get("equipment"):
        out = [l for l in out if l.equipment_type == eq]
    if region := filters.get("dest_region"):
        region_u = str(region).upper()
        out = [l for l in out if region_u in l.dest_market.upper()]
    if min_net := filters.get("min_net"):
        out = [l for l in out if l.rate_usd >= float(min_net)]
    # deadline: soft filter on est_transit — keep loads that could finish sooner
    if filters.get("deadline"):
        try:
            deadline = datetime.fromisoformat(str(filters["deadline"]).replace("Z", "+00:00"))
            hours_left = max(1.0, (deadline - datetime.now(deadline.tzinfo)).total_seconds() / 3600)
            out = [l for l in out if l.est_transit_hours <= hours_left]
        except ValueError:
            pass
    return out


def run_copilot(
    message: str,
    truck: TruckInput,
    loads: list[LoadInput],
    diesel: float,
) -> dict[str, Any]:
    filters = parse_filters(message)
    filtered = apply_filters(loads, filters)
    ranked = rank_loads(truck, filtered, diesel)[:10]
    pair = None
    if filters.get("prefer_backhaul") or "backhaul" in message.lower() or "round" in message.lower():
        pair = best_chain_for_top_outbounds(truck, filtered, diesel)

    engine_payload = {
        "filters": filters,
        "results": [
            {
                "load_id": r.load_id,
                "overall": r.overall,
                "rate_per_mile": r.rate_per_mile,
                "deadhead_miles": r.deadhead_miles,
            }
            for r in ranked
        ],
        "best_pair": (
            {
                "outbound_id": pair.outbound_id,
                "return_id": pair.return_id,
                "combined_score": pair.combined_score,
            }
            if pair
            else None
        ),
    }
    narration = llm_client.complete(NARRATE_SYSTEM, json.dumps(engine_payload))
    # Grounding: every load_id mentioned must exist in engine output
    allowed = {r.load_id for r in ranked}
    if pair:
        allowed.update({pair.outbound_id, pair.return_id})
    return {
        "filters": filters,
        "results": engine_payload["results"],
        "best_pair": engine_payload["best_pair"],
        "narration": narration,
        "allowed_load_ids": sorted(allowed),
    }
