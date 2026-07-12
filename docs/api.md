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
| `/api/copilot/` | POST | yes | NL → filters → engine → narrate |
| `/api/fleet/optimize/` | POST | yes | Multi-truck Hungarian assignment |
| `/api/analytics/summary/` | GET | yes | Fleet KPIs |

`best_pair.combined_score` = net USD/hour. Returned only when it beats the top single on that same metric.
