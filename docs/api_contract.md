# API contract

The HTTP interface is specified in [the SRS](srs.md) section 7.2. The backend is FastAPI under `backend/app/api/v1/`.

| Method | Path | Response |
|---|---|---|
| GET | `/api/v1/health` | `200` with `{"status":"ok","service":"hetuvia-api"}` |
| GET | `/api/v1/summary` | `200` with aggregate counts and the demonstration label |
| GET | `/api/v1/people` | `200` with `items` and `meta`; filters: `source`, `status`, `search`, `limit`, `offset` |
| GET | `/api/v1/people/{person_id}` | `200` with one person, or `404` |
| GET | `/api/v1/care-gap-findings` | `200` with `items` and `meta`; filters: `source`, `person_id`, `outcome`, `limit`, `offset` |
| GET | `/api/v1/data-quality-findings` | `200` with `items` and `meta`; filters: `source`, `person_id`, `rule_code`, `limit`, `offset` |
| GET | `/api/v1/recommendations` | `200` with `items` and `meta`; filters: `source`, `person_id`, `status`, `priority`, `limit`, `offset` |
| GET | `/api/v1/audit-events` | `200` with `items` and `meta`; filters: `action`, `person_id`, `limit`, `offset` |

All operator endpoints are read-only. Clinical action endpoints (review, import, reset) are out of scope until authentication and authorisation exist. Response schemas are defined in `backend/app/api/v1/schemas.py`.

The Next.js console consumes this API through `frontend/lib/api/operator.ts`. The static demo at `docs/index.html` is separate and reads generated data files only.
