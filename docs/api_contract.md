# API contract

This file was an empty placeholder. The current HTTP interface is defined in [the SRS](srs.md) section 7.2:

| Method | Path | Response |
|---|---|---|
| GET | `/api/v1/health` | `200` with `{"status":"ok","service":"hetuvia-api"}` |

No clinical API endpoints exist in the baseline. The command-line interface is specified in section 7.1 and the CSV input format in section 7.3 of the SRS. Clinical APIs are listed as out of scope in section 9.
