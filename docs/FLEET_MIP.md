# Fleet assignment MIP (OR-Tools CP-SAT)

HaulRank keeps **Hungarian** (`scipy.optimize.linear_sum_assignment`) as a bipartite
baseline and adds an **OR-Tools CP-SAT** binary integer program for the same
one-to-one truck↔load assignment.

This is a **BIP / MIP-style assignment** over ranking utilities — **not** an LP
relaxation of factory layout, Omniverse optimization, or a production OR stack
at scale.

## Decision variables

Binary \(x_{t,l} = 1\) iff truck \(t\) is assigned load \(l\).

## Objective

Maximize \(\sum_{t,l} U_{t,l}\, x_{t,l}\) where \(U_{t,l}\) is the deterministic
`rank_loads` overall score for that pair (same scoring stack as `/api/rank/`).

## Hard constraints (minimum)

1. **One load per truck:** \(\sum_l x_{t,l} \le 1\)
2. **One truck per load:** \(\sum_t x_{t,l} \le 1\)
3. **Feasibility mask:** \(x_{t,l} = 0\) if equipment mismatch or HOS-infeasible
   (same `is_feasible` rules as ranking: deadhead hours + transit ≤ remaining HOS)
4. **Brownfield locks (optional):** for committed `accepted`/`dispatched` pairs,
   \(x_{t^*,l^*} = 1\) — residual demand only for free trucks/loads

The API returns these as human-readable `constraints_summary` so an assistant
cannot invent feasibility.

## API

```http
POST /api/fleet/optimize/?solver=mip
POST /api/fleet/optimize/   # body: {"solver":"hungarian"|"mip"}  default mip
```

Response includes `assignments`, `objective_value`, `solver`,
`constraints_summary`, `baseline_comparison` (Hungarian objective + match reason),
and `locked_assignments`.

## Code map

| Piece | Path |
|-------|------|
| Utility matrix | `apps/fleet_opt/types.py` |
| Hungarian | `apps/fleet_opt/engine.py` |
| CP-SAT MIP | `apps/fleet_opt/mip_engine.py` |
| Locks | `apps/fleet_opt/locks.py` |
| View | `apps/fleet_opt/views.py` |

## Brownfield seed

```bash
.venv/bin/python manage.py seed_demo --brownfield
```

Freight brownfield lock = analogy for inserting capacity beside a committed plan;
**not** a digital twin / facility geometry / production-line integration.

## Whiteboard (interview)

- Vars: binary \(x_{t,l}\)
- Max \(\sum U x\)
- Constraints: one-to-one + HOS/equipment mask (+ optional locks)
