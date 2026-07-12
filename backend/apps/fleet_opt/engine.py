"""Fleet-wide load assignment via Hungarian algorithm."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from apps.scoring.engine import LoadInput, TruckInput, rank_loads

INFEASIBLE = 1e6


@dataclass(frozen=True)
class FleetAssignment:
    truck_id: int
    load_id: int
    score: float


def optimize_fleet(
    trucks: list[TruckInput],
    loads: list[LoadInput],
    diesel_usd_per_gal: float,
) -> list[FleetAssignment]:
    if not trucks or not loads:
        return []

    n_t, n_l = len(trucks), len(loads)
    cost = np.full((n_t, n_l), INFEASIBLE)

    for i, truck in enumerate(trucks):
        ranked = {r.load_id: r.overall for r in rank_loads(truck, loads, diesel_usd_per_gal)}
        for j, load in enumerate(loads):
            if load.id in ranked:
                cost[i, j] = -ranked[load.id]  # maximize score → minimize negative

    row_idx, col_idx = linear_sum_assignment(cost)
    out: list[FleetAssignment] = []
    used_loads: set[int] = set()
    for r, c in zip(row_idx, col_idx):
        if cost[r, c] >= INFEASIBLE / 2:
            continue
        load_id = loads[c].id
        if load_id in used_loads:
            continue
        used_loads.add(load_id)
        out.append(
            FleetAssignment(
                truck_id=trucks[r].id,
                load_id=load_id,
                score=float(-cost[r, c]),
            )
        )
    return out
