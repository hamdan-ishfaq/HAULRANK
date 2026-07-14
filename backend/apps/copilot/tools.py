"""Copilot tool schemas — deterministic engines only (no free-form logistics math)."""

from __future__ import annotations

from typing import Any

from apps.backhaul.engine import best_chain_for_top_outbounds
from apps.copilot.service import apply_filters, _normalize_filters
from apps.fleet_opt.engine import run_optimize
from apps.scoring.engine import LoadInput, TruckInput, rank_loads

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "rank_loads",
            "description": (
                "Rank loads for the active truck using the deterministic scoring engine. "
                "Optional filters narrow the board."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dest_region": {"type": "string"},
                    "equipment": {
                        "type": "string",
                        "enum": ["dry_van", "reefer", "flatbed"],
                    },
                    "min_net": {"type": "number"},
                    "prefer_backhaul": {"type": "boolean"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_fleet",
            "description": (
                "Assign loads across the whole carrier fleet using Hungarian or OR-Tools "
                "CP-SAT MIP. Honors brownfield locked assignments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "solver": {
                        "type": "string",
                        "enum": ["mip", "hungarian"],
                        "description": "Default mip",
                    }
                },
            },
        },
    },
]

TOOL_SYSTEM = (
    "You are a dispatcher copilot. Call tools to get deterministic ranking or fleet "
    "optimization results. Narrate ONLY tool JSON — never invent load IDs, rates, or "
    "feasibility. Prefer optimize_fleet for whole-fleet assignment; rank_loads for "
    "single-truck search."
)


def make_tool_executor(
    *,
    truck: TruckInput,
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel: float,
    locked_pairs: list[tuple[int, int]] | None = None,
):
    locked_pairs = locked_pairs or []

    def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "rank_loads":
            filters = _normalize_filters(
                {
                    k: args[k]
                    for k in (
                        "dest_region",
                        "equipment",
                        "min_net",
                        "prefer_backhaul",
                    )
                    if k in args and args[k] is not None
                }
            )
            filtered = apply_filters(loads, filters)
            limit = int(args.get("limit") or 10)
            ranked = rank_loads(truck, filtered, diesel)[: max(1, min(limit, 20))]
            pair = None
            if filters.get("prefer_backhaul"):
                pair = best_chain_for_top_outbounds(truck, filtered, diesel)
            return {
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
                "constraints_summary": [
                    "equipment match",
                    "HOS feasibility",
                    "deterministic rank_loads overall",
                ],
            }

        if name == "optimize_fleet":
            solver = str(args.get("solver") or "mip")
            result = run_optimize(
                trucks,
                loads,
                diesel,
                solver=solver,
                locked_pairs=locked_pairs,
            )
            return {
                "solver": result.solver,
                "objective_value": result.objective_value,
                "assignments": [
                    {
                        "truck_id": a.truck_id,
                        "load_id": a.load_id,
                        "score": a.score,
                    }
                    for a in result.assignments
                ],
                "constraints_summary": result.constraints_summary,
                "locked_assignments": result.locked_assignments,
                "baseline_comparison": result.baseline_comparison,
            }

        return {"error": f"unknown tool {name}"}

    return execute
