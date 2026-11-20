# HETUVIA

**Preventive care coordination prototype — 100% fictional data, demonstration rules only.**

HETUVIA loads a synthetic (or CSV-supplied) population, checks record quality, evaluates care gaps against versioned rules, proposes pathways for **human review**, and publishes an interactive static demo. It is a software prototype for testing workflow and safeguards — **not an Abu Dhabi guideline, not clinical advice, and not a system for real patient data.**

> [!WARNING]
> Every rule and pathway in this repository is labelled `DEMONSTRATION` and was invented for software testing. The loader refuses to mark a rule `approved` until a confirmed, cited source exists. Do not use HETUVIA to make clinical decisions or with identifiable patient information.

---

## What this repository contains

| Area | Location | Purpose |
|---|---|---|
| Backend domain, engines, CLI | [`backend/app/`](backend/app/) | Data models, CSV/synthetic adapters, data-quality and care-gap engines, recommendation engine, review service, audit log, demo exporter |
| Rules | [`backend/rules/demo_rules_v1.json`](backend/rules/demo_rules_v1.json) | The only shipped rule set: two demonstration screening rules |
| Database | [`backend/migrations/`](backend/migrations/) | Six Alembic revisions creating 13 tables |
| Tests | [`backend/tests/`](backend/tests/) | 125 automated tests, including answer-key grading of planted data gaps |
| Static demo | [`docs/demo/`](docs/demo/) | `indexx.html` + generated `data.js` — the actual HETUVIA demo UI |
| Thin frontend | [`frontend/`](frontend/) | Minimal Next.js health-status page (scaffold only) |
| Documentation | [`docs/`](docs/) | Software requirements, rule catalogues, import format, data dictionary |

The authoritative specification is **[docs/srs.md](docs/srs.md)**. It documents the as-built baseline at commit `5a6d9d7`.

---

## Processing pipeline

```text
seed / import-csv
        │
        ▼
quality-check ─────► data_quality_findings
        │
        ▼
care-gap-check ────► guideline_rules + care_gap_findings
        │
        ▼
recommend ─────────► recommendations (all pending_review)
        │
        ▼
review ────────────► audit_events (approve / defer / reject)
        │
        ▼
export_demo ───────► docs/demo/data.js ──► docs/demo/indexx.html
```

Core safety rules enforced in code:

- Records are matched **only** by `(source_system, source_record_id)`. Names, dates of birth and addresses are never used to merge people.
- Missing values stay missing (`unknown`, `not_collected`, `stale`, `explicitly_absent`). They are never converted to “no” or “normal”.
- Missing date of birth or an undated completed service yields `not_assessable` — an information gap, not a care gap.
- Outreach priority is a coordination order, **not clinical urgency**. Every recommendation requires human review before outreach.
- Decision inputs and outputs carry evidence and provenance so a verdict can be explained later.

---

## Quick start (Windows / PowerShell)

### 1. Prerequisites

- Docker Desktop (for the local PostgreSQL 16 container), or an existing PostgreSQL instance
- Python 3.11+ (the validated environment uses Python 3.13.9)
- Node.js 20+ (only needed for the optional Next.js page)

### 2. Start the database and install backend dependencies

```powershell
docker compose up -d db

cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

The default `DATABASE_URL` is:

```text
postgresql+psycopg://hetuvia:hetuvia_dev@localhost:5432/hetuvia
```

These are development-only credentials matching `docker-compose.yml`.

### 3. Create the schema

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Migration chain: `d8f0e1b1b28e` → `283d73fe447e` → `a2ff5238c20f` → `3233e4718e78` → `8ae5e64e1283` → `4547c4c46435`.

### 4. Load data and run the engines

```powershell
# Deterministic fictional population: seed 42, 300 people, fixed reference date 2026-11-01
.\.venv\Scripts\python.exe -m app.cli seed --seed 42 --people 300

# Or import your own CSV folder (people.csv / encounters.csv / observations.csv)
.\.venv\Scripts\python.exe -m app.cli import-csv ..\backend\sample_import --source csv_import

.\.venv\Scripts\python.exe -m app.cli quality-check --source synthetic
.\.venv\Scripts\python.exe -m app.cli care-gap-check --source synthetic
.\.venv\Scripts\python.exe -m app.workflow_cli recommend --source synthetic
```

The built-in sample CSVs live in [`backend/sample_import/`](backend/sample_import/). Format details are in [`docs/import_format.md`](docs/import_format.md).

### 5. Inspect and review

```powershell
.\.venv\Scripts\python.exe -m app.cli quality-report SYN-0007 --source synthetic
.\.venv\Scripts\python.exe -m app.cli care-gap-report SYN-0007 --source synthetic

# Use a recommendation ID printed/stored from the previous step
.\.venv\Scripts\python.exe -m app.workflow_cli review <recommendation-id> `
  --decision approve --reviewer "Demo Reviewer" --note "Checked demonstration evidence"
```

Valid decisions: `approve`, `defer`, `reject`. A note is required for `defer` and `reject`. Every decision is written to `audit_events`.

### 6. Regenerate the static demo

```powershell
.\.venv\Scripts\python.exe -m app.export_demo --source synthetic --out ..\docs\demo\data.js
```

Then open **`docs/demo/indexx.html`** in a browser, or serve the `docs/` folder with any static server:

```powershell
py -m http.server 8001 --directory docs
# visit http://localhost:8001/demo/indexx.html
```

`docs/.nojekyll` makes the folder usable with GitHub Pages. The demo keeps review/outreach interactions in the browser (`localStorage`) only; they do not write back to PostgreSQL.

### 7. Run the API and thin frontend

```powershell
# terminal 1 — from backend/
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# terminal 2 — from frontend/
npm install
npm run dev
```

The API currently exposes only `GET /api/v1/health` → `{"status":"ok","service":"hetuvia-api"}`. The Next.js page displays that status. Set `NEXT_PUBLIC_API_URL` if the API is not at `http://localhost:8000`.

### 8. Run the tests

```powershell
# from the repository root
.\test.ps1

# or from backend/
.\.venv\Scripts\python.exe -m pytest -q
```

Baseline: **125 passed** (one non-fatal Starlette/httpx deprecation warning). Tests require the PostgreSQL instance to be running because several tests exercise real migrations and persistence.

---

## CLI reference

| Command | Description |
|---|---|
| `python -m app.cli seed [--seed 42] [--people 300]` | Generate the deterministic fictional population and print planted-gap counts |
| `python -m app.cli import-csv <dir> [--source csv_import]` | Import/validate CSVs; bad rows are quarantined in `import_rejections` |
| `python -m app.cli quality-check [--source synthetic] [--date YYYY-MM-DD]` | Replace DQ findings for one source with a fresh evaluation |
| `python -m app.cli quality-report <source_record_id> [--source synthetic]` | Show one person’s fields and DQ findings |
| `python -m app.cli care-gap-check [--source synthetic] [--date YYYY-MM-DD]` | Sync rules and replace care-gap findings for one source |
| `python -m app.cli care-gap-report <source_record_id> [--source synthetic]` | Show one person’s care-gap verdicts with evidence |
| `python -m app.cli reset-source <name>` / `reset-synthetic` | Delete everything loaded by one source; audit events survive |
| `python -m app.workflow_cli recommend [--source synthetic] [--date YYYY-MM-DD]` | Create/update/reopen/close recommendations |
| `python -m app.workflow_cli review <id> --decision <d> --reviewer <name> [--note <text>]` | Record a human decision |
| `python -m app.export_demo [--source synthetic] [--date ...] [--out ../docs/demo/data.js]` | Export stored output as `window.HETUVIA_DATA` for the static demo |

Run these from `backend/` with the virtual environment active.

---

## Documentation

- [SRS — software requirements specification](docs/srs.md) ← start here for the full specification
- [Care-gap rules](docs/care_gap_rules.md)
- [Data-quality rule catalogue](docs/dq_rule_catalogue.md)
- [CSV import format](docs/import_format.md)
- [Data dictionary](docs/data_dictionary.md)
- [Demonstration rule set](backend/rules/demo_rules_v1.json)
- [Demo data contract / generated file](docs/demo/data.js)

The files `docs/product_scope.md`, `docs/api_contract.md` and `docs/rule_catalogue.md` are historical empty placeholders; the SRS is the maintained specification.

---

## Development history

The repository was built incrementally, one commit per chunk:

| Date | Commit | Delivered |
|---|---|---|
| 2026-11-12 | `b372add` | Project foundation (chunk 1) |
| 2026-11-13 | `5412ebf`, `f52bcda` | PostgreSQL in Docker, DB session, core tables, migrations, people repository (chunk 2 / 2a) |
| 2026-11-14 | `de2f2ba`, `2107fc6` | Conditions, screening events, family-history state; seeded synthetic population and seed CLI (chunk 3 / 3a) |
| 2026-11-15 | `207fced`, `56bff08`, `ad01e0d` | Import tables/validation; CSV adapter, importer, quarantine, reports; DQ findings and rules (chunk 4a / 4b / 5a) |
| 2026-11-16 | `e217275`, `01c44ac`, `1a22f34` | DQ runner, answer-key grading, reports; care-gap rule loader/judge; runner, reports, DB tests (chunk 5b / 6a / 6b) |
| 2026-11-19 | `5c41733` | Pathways, priority, recommendations, review and audit log (chunk 8) |
| 2026-11-20 | `5a6d9d7` | Static HETUVIA demo and export command |

`docs/care_gap_rules.md` refers to a future **Chunk 10 outreach decision**; the current static demo simulates outreach in the browser, but no backend outreach-decision service exists yet.

---

## Repository notes

- The real demo is **`docs/demo/indexx.html`**. `docs/demo/index.html` is an unrelated LearnVault template left in the folder and references missing `style.css` / `script.js`.
- `backend/requirements.txt` is UTF-16LE with a BOM. `pip` reads it, but editors may display it incorrectly if opened as plain UTF-8.
- `frontend/AGENTS.md` is generated by `next dev`. When writing frontend code, follow it: read the relevant Next.js 16.4.6 guide under `frontend/node_modules/next/dist/docs/` first. This README/SRS work does not modify frontend code.
- No `.env` with real secrets is committed; `backend/.env` may exist locally and matches `.env.example`.
