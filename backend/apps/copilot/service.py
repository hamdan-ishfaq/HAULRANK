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

# Normalize common region names to seed dest_market codes
REGION_ALIASES = {
    "TEXAS": "TX",
    "TX": "TX",
    "OKLAHOMA": "OK",
    "OK": "OK",
    "TENNESSEE": "TN",
    "TN": "TN",
    "GEORGIA": "GA",
    "GA": "GA",
    "ILLINOIS": "IL",
    "IL": "IL",
    "ARIZONA": "AZ",
    "AZ": "AZ",
}

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

_LOAD_ID_RE = re.compile(
    r"\bload(?:\s*#?\s*|\s+id\s+)?(\d+)\b|#(\d{3,})",
    re.IGNORECASE,
)


def _normalize_filters(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in FILTER_KEYS:
        if key not in data or data[key] is None:
            continue
        val = data[key]
        if key == "min_net":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError("min_net must be a number")
            out[key] = float(val)
        elif key == "prefer_backhaul":
            if not isinstance(val, bool):
                raise ValueError("prefer_backhaul must be a boolean")
            out[key] = val
        elif key == "equipment":
            if not isinstance(val, str):
                raise ValueError("equipment must be a string")
            out[key] = val
        elif key == "dest_region":
            if not isinstance(val, str):
                raise ValueError("dest_region must be a string")
            out[key] = val
        elif key == "deadline":
            out[key] = val
    return out


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
    return _normalize_filters(data)


def apply_filters(loads: list[LoadInput], filters: dict[str, Any]) -> list[LoadInput]:
    out = loads
    if eq := filters.get("equipment"):
        out = [l for l in out if l.equipment_type == eq]
    if region := filters.get("dest_region"):
        region_u = str(region).upper().strip()
        needle = REGION_ALIASES.get(region_u, region_u)
        out = [
            l
            for l in out
            if needle in l.dest_market.upper() or region_u in l.dest_market.upper()
        ]
    if "min_net" in filters:
        min_net = float(filters["min_net"])
        out = [l for l in out if l.rate_usd >= min_net]
    if filters.get("deadline"):
        try:
            deadline = datetime.fromisoformat(str(filters["deadline"]).replace("Z", "+00:00"))
            hours_left = max(
                1.0, (deadline - datetime.now(deadline.tzinfo)).total_seconds() / 3600
            )
            out = [l for l in out if l.est_transit_hours <= hours_left]
        except ValueError:
            pass
    return out


def _extract_load_ids(text: str) -> set[int]:
    found: set[int] = set()
    for m in _LOAD_ID_RE.finditer(text or ""):
        for g in m.groups():
            if g:
                found.add(int(g))
    return found


def _template_narration(engine_payload: dict[str, Any]) -> str:
    results = engine_payload.get("results") or []
    if not results:
        return "No loads matched the filters against the scoring engine."
    parts = []
    for row in results[:3]:
        parts.append(
            f"Load {row['load_id']} scores {row['overall']:.3f} "
            f"(${row['rate_per_mile']:.2f}/mi, {row['deadhead_miles']:.0f} mi deadhead)"
        )
    text = "Top matches from the engine: " + "; ".join(parts) + "."
    pair = engine_payload.get("best_pair")
    if pair:
        text += (
            f" Best pair: outbound {pair['outbound_id']} + return {pair['return_id']} "
            f"(combined {pair['combined_score']:.2f} net USD/hr)."
        )
    return text


def ground_narration(narration: str, allowed: set[int], engine_payload: dict[str, Any]) -> str:
    claimed = _extract_load_ids(narration)
    if claimed - allowed:
        return _template_narration(engine_payload)
    return narration


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
    if (
        filters.get("prefer_backhaul")
        or "backhaul" in message.lower()
        or "round" in message.lower()
    ):
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
    raw_narration = llm_client.complete(NARRATE_SYSTEM, json.dumps(engine_payload))
    allowed = {r.load_id for r in ranked}
    if pair:
        allowed.update({pair.outbound_id, pair.return_id})
    narration = ground_narration(raw_narration, allowed, engine_payload)
    return {
        "filters": filters,
        "results": engine_payload["results"],
        "best_pair": engine_payload["best_pair"],
        "narration": narration,
        "allowed_load_ids": sorted(allowed),
    }
