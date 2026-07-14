"""OR-Tools CP-SAT binary integer program for fleet load assignment.

BIP / MIP-style assignment — not LP relaxation of factory layout.
Decision vars: binary x[t,l]. Objective: maximize sum of ranking utilities.
"""

from __future__ import annotations

import numpy as np
from ortools.sat.python import cp_model

from apps.fleet_opt.types import (
    FleetAssignment,
    OptimizeResult,
    build_utility_matrix,
    constraints_summary,
    index_maps,
    locked_dicts,
    objective_of,
)
from apps.scoring.engine import LoadInput, TruckInput

SCALE = 10_000  # CP-SAT is integer; utilities are 0..1 floats


def solve_mip(
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
    locked_pairs: list[tuple[int, int]] | None = None,
) -> OptimizeResult:
    locked_pairs = locked_pairs or []
    empty = OptimizeResult(
        assignments=[],
        objective_value=0.0,
        solver="mip",
        constraints_summary=constraints_summary(locked_count=len(locked_pairs)),
        locked_assignments=locked_dicts(locked_pairs),
    )
    if not trucks or not loads:
        return empty

    U = build_utility_matrix(trucks, loads, diesel_usd_per_gal)
    truck_ix, load_ix = index_maps(trucks, loads)
    n_t, n_l = len(trucks), len(loads)

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}

    for i in range(n_t):
        for j in range(n_l):
            if np.isnan(U[i, j]):
                continue
            x[i, j] = model.NewBoolVar(f"x_{i}_{j}")

    # Ensure locked edges exist even if ranking marked NaN (committed brownfield)
    for tid, lid in locked_pairs:
        i, j = truck_ix.get(tid), load_ix.get(lid)
        if i is None or j is None:
            continue
        if (i, j) not in x:
            x[i, j] = model.NewBoolVar(f"x_lock_{i}_{j}")
            U[i, j] = 0.0

    if not x:
        return empty

    model.Maximize(sum(int(round(float(U[i, j]) * SCALE)) * x[i, j] for i, j in x))

    for i in range(n_t):
        vars_i = [x[i, j] for j in range(n_l) if (i, j) in x]
        if vars_i:
            model.Add(sum(vars_i) <= 1)

    for j in range(n_l):
        vars_j = [x[i, j] for i in range(n_t) if (i, j) in x]
        if vars_j:
            model.Add(sum(vars_j) <= 1)

    for tid, lid in locked_pairs:
        i, j = truck_ix.get(tid), load_ix.get(lid)
        if i is None or j is None or (i, j) not in x:
            continue
        model.Add(x[i, j] == 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        fixed = []
        for tid, lid in locked_pairs:
            i, j = truck_ix.get(tid), load_ix.get(lid)
            score = 0.0
            if i is not None and j is not None and not np.isnan(U[i, j]):
                score = float(U[i, j])
            fixed.append(FleetAssignment(truck_id=tid, load_id=lid, score=score))
        return OptimizeResult(
            assignments=fixed,
            objective_value=objective_of(fixed),
            solver="mip",
            constraints_summary=constraints_summary(locked_count=len(locked_pairs)),
            locked_assignments=locked_dicts(locked_pairs),
        )

    assignments: list[FleetAssignment] = []
    for (i, j), var in x.items():
        if solver.Value(var) == 1:
            score = float(U[i, j]) if not np.isnan(U[i, j]) else 0.0
            assignments.append(
                FleetAssignment(
                    truck_id=trucks[i].id,
                    load_id=loads[j].id,
                    score=score,
                )
            )

    return OptimizeResult(
        assignments=assignments,
        objective_value=objective_of(assignments),
        solver="mip",
        constraints_summary=constraints_summary(locked_count=len(locked_pairs)),
        locked_assignments=locked_dicts(locked_pairs),
    )
