# API

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/health/` | GET | no | Liveness |
| `/api/auth/token/` | POST | no | JWT obtain |
| `/api/auth/token/refresh/` | POST | no | JWT refresh |
| `/api/trucks/` | GET/POST | yes | Fleet CRUD |
| `/api/loads/` | GET/POST | yes | Load board |
| `/api/rank/?truck_id=` | POST | yes | Rank loads |
| `/api/rank/{id}/explain/` | POST | yes | Top-3 Groq explain |
| `/api/assignments/` | GET/POST/PATCH | yes | Assignment chain |
| `/api/assignments/{id}/history/` | GET | yes | Audit trail |
| `/api/copilot/` | POST | yes | Tier 2 NL copilot |

Filled in as modules land.
