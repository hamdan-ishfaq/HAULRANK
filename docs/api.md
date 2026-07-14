# API

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/health/` | GET | no | Liveness |
| `/api/auth/register/` | POST | no | Register |
| `/api/auth/token/` | POST | no | JWT obtain |
| `/api/auth/token/refresh/` | POST | no | JWT refresh |
| `/api/trucks/` | CRUD | yes | Fleet (+ driver reliability) |
| `/api/loads/` | CRUD | yes | Load board |
| `/api/rank/?truck_id=` | POST | yes | Rank loads; `best_single`; optional `best_pair` |
| `/api/rank/{id}/explain/` | POST | yes | Top-3 grounded explain |
| `/api/assignments/` | GET/POST/PATCH | yes | Assignment chain |
| `/api/assignments/{id}/history/` | GET | yes | Audit trail |
| `/api/copilot/` | POST | yes | NL → filters/tools → engine → narrate (`tools_called` when optimize path) |
| `/api/fleet/optimize/?solver=` | POST | yes | Multi-truck assignment (`mip` default, or `hungarian`) |
| `/api/analytics/summary/` | GET | yes | Fleet KPIs |

`best_pair.combined_score` = net USD/hour. Returned only when it beats the top single on that same metric.

### Fleet optimize response

```json
{
  "solver": "mip",
  "objective_value": 2.41,
  "assignments": [{"truck_id": 1, "load_id": 10, "score": 0.8}],
  "constraints_summary": ["one load per truck", "..."],
  "baseline_comparison": {"hungarian_objective": 2.41, "matches": true, "reason": "..."},
  "locked_assignments": [{"truck_id": 1, "load_id": 10}]
}
```

See [FLEET_MIP.md](FLEET_MIP.md).
