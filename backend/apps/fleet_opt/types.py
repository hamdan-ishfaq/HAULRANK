"""Fleet optimization types and shared utility matrix (Hungarian + MIP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from apps.scoring.engine import LoadInput, TruckInput, rank_loads

INFEASIBLE = 1e6
NAN = float("nan")

BASE_CONSTRAINTS = [
    "one load per truck",
    "one truck per load",
    "exclude equipment mismatch",
    "exclude HOS-infeasible pairs (deadhead+transit > remaining HOS)",
]


@dataclass(frozen=True)
class FleetAssignment:
    truck_id: int
    load_id: int
    score: float


@dataclass
class OptimizeResult:
    assignments: list[FleetAssignment]
    objective_value: float
    solver: Literal["hungarian", "mip"]
    constraints_summary: list[str]
    baseline_comparison: dict[str, Any] = field(default_factory=dict)
    locked_assignments: list[dict[str, Any]] = field(default_factory=list)


def build_utility_matrix(
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
) -> np.ndarray:
    """Return U[t,l] = overall score, or NaN if hard-infeasible."""
    n_t, n_l = len(trucks), len(loads)
    U = np.full((n_t, n_l), NAN)
    if not trucks or not loads:
        return U
    for i, truck in enumerate(trucks):
        ranked = {r.load_id: r.overall for r in rank_loads(truck, loads, diesel_usd_per_gal)}
        for j, load in enumerate(loads):
            if load.id in ranked:
                U[i, j] = ranked[load.id]
    return U


def constraints_summary(*, locked_count: int = 0) -> list[str]:
    lines = list(BASE_CONSTRAINTS)
    if locked_count:
        lines.append(
            "locked brownfield assignments fixed (committed accepted/dispatched)"
        )
    return lines


def locked_dicts(locked_pairs: list[tuple[int, int]]) -> list[dict[str, Any]]:
    return [{"truck_id": t, "load_id": l} for t, l in locked_pairs]


def index_maps(
    trucks: list[TruckInput], loads: list[LoadInput]
) -> tuple[dict[int, int], dict[int, int]]:
    return (
        {t.id: i for i, t in enumerate(trucks)},
        {l.id: j for j, l in enumerate(loads)},
    )


def objective_of(assignments: list[FleetAssignment]) -> float:
    return round(sum(a.score for a in assignments), 6)


def compare_baseline(
    *,
    chosen_solver: str,
    chosen_obj: float,
    hungarian_obj: float,
    locked_count: int,
    same_edges: bool,
) -> dict[str, Any]:
    if chosen_solver == "hungarian":
        return {
            "hungarian_objective": hungarian_obj,
            "matches": True,
            "reason": "solver is the Hungarian baseline; MIP not run",
        }
    matches = abs(chosen_obj - hungarian_obj) < 1e-6
    if matches and same_edges:
        reason = (
            "Identical utilities and hard constraints; "
            "both solvers selected the same total utility."
        )
    elif matches:
        reason = (
            "MIP and Hungarian selected different edges with equal total utility."
        )
    elif locked_count:
        reason = (
            f"MIP fixed {locked_count} locked pairs; "
            "free residual assignment differs from unconstrained Hungarian."
        )
    else:
        reason = (
            "MIP and Hungarian produced different total utilities "
            "under the same hard constraints."
        )
    return {
        "hungarian_objective": hungarian_obj,
        "matches": matches,
        "reason": reason,
    }
