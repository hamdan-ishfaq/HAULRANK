"""Fleet-wide load assignment — Hungarian baseline + shared dispatch."""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from apps.fleet_opt.types import (
    INFEASIBLE,
    FleetAssignment,
    OptimizeResult,
    build_utility_matrix,
    compare_baseline,
    constraints_summary,
    index_maps,
    locked_dicts,
    objective_of,
)
from apps.scoring.engine import LoadInput, TruckInput


def _apply_locks_to_matrix(
    U: np.ndarray,
    trucks: list[TruckInput],
    loads: list[LoadInput],
    locked_pairs: list[tuple[int, int]],
) -> tuple[np.ndarray, list[FleetAssignment]]:
    """Force locked pairs: fixed assignments + mask those trucks/loads from free solve."""
    truck_ix, load_ix = index_maps(trucks, loads)
    fixed: list[FleetAssignment] = []
    U2 = U.copy()
    for tid, lid in locked_pairs:
        i = truck_ix.get(tid)
        j = load_ix.get(lid)
        if i is None or j is None:
            continue
        score = float(U2[i, j]) if not np.isnan(U2[i, j]) else 0.0
        fixed.append(FleetAssignment(truck_id=tid, load_id=lid, score=score))
        # Mask entire row/col so residual Hungarian cannot use them
        U2[i, :] = np.nan
        U2[:, j] = np.nan
    return U2, fixed


def solve_hungarian(
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    locked_pairs: list[tuple[int, int]] | None = None,
) -> OptimizeResult:
    locked_pairs = locked_pairs or []
    if not trucks or not loads:
        return OptimizeResult(
            assignments=[],
            objective_value=0.0,
            solver="hungarian",
            constraints_summary=constraints_summary(locked_count=len(locked_pairs)),
            baseline_comparison=compare_baseline(
                chosen_solver="hungarian",
                chosen_obj=0.0,
                hungarian_obj=0.0,
                locked_count=len(locked_pairs),
                same_edges=True,
            ),
            locked_assignments=locked_dicts(locked_pairs),
        )

    U = build_utility_matrix(trucks, loads, diesel_usd_per_gal)
    U_free, fixed = _apply_locks_to_matrix(U, trucks, loads, locked_pairs)

    n_t, n_l = len(trucks), len(loads)
    cost = np.full((n_t, n_l), INFEASIBLE)
    for i in range(n_t):
        for j in range(n_l):
            if not np.isnan(U_free[i, j]):
                cost[i, j] = -U_free[i, j]

    row_idx, col_idx = linear_sum_assignment(cost)
    free: list[FleetAssignment] = []
    used_loads: set[int] = set()
    for r, c in zip(row_idx, col_idx):
        if cost[r, c] >= INFEASIBLE / 2:
            continue
        load_id = loads[c].id
        if load_id in used_loads:
            continue
        used_loads.add(load_id)
        free.append(
            FleetAssignment(
                truck_id=trucks[r].id,
                load_id=load_id,
                score=float(-cost[r, c]),
            )
        )

    assignments = fixed + free
    obj = objective_of(assignments)
    return OptimizeResult(
        assignments=assignments,
        objective_value=obj,
        solver="hungarian",
        constraints_summary=constraints_summary(locked_count=len(locked_pairs)),
        baseline_comparison=compare_baseline(
            chosen_solver="hungarian",
            chosen_obj=obj,
            hungarian_obj=obj,
            locked_count=len(locked_pairs),
            same_edges=True,
        ),
        locked_assignments=locked_dicts(locked_pairs),
    )


def optimize_fleet(
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    locked_pairs: list[tuple[int, int]] | None = None,
) -> list[FleetAssignment]:
    """Backward-compatible Hungarian entry — returns assignment list only."""
    return solve_hungarian(trucks, loads, diesel_usd_per_gal, locked_pairs).assignments


def run_optimize(
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    *,
    solver: str = "mip",
    locked_pairs: list[tuple[int, int]] | None = None,
) -> OptimizeResult:
    locked_pairs = locked_pairs or []
    solver = (solver or "mip").lower().strip()
    if solver not in ("mip", "hungarian"):
        solver = "mip"

    hun = solve_hungarian(trucks, loads, diesel_usd_per_gal, locked_pairs)
    if solver == "hungarian":
        return hun

    from apps.fleet_opt.mip_engine import solve_mip

    mip = solve_mip(trucks, loads, diesel_usd_per_gal, locked_pairs)
    hun_edges = {(a.truck_id, a.load_id) for a in hun.assignments}
    mip_edges = {(a.truck_id, a.load_id) for a in mip.assignments}
    mip.baseline_comparison = compare_baseline(
        chosen_solver="mip",
        chosen_obj=mip.objective_value,
        hungarian_obj=hun.objective_value,
        locked_count=len(locked_pairs),
        same_edges=hun_edges == mip_edges,
    )
    return mip
