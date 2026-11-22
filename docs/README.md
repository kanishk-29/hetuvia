# HETUVIA static demo

`index.html` is the demo entry point. It reads `data.js`, which is generated from the database.

## Regenerate the data file

Run the engines first, then export:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli quality-check --source synthetic
.\.venv\Scripts\python.exe -m app.cli care-gap-check --source synthetic
.\.venv\Scripts\python.exe -m app.workflow_cli recommend --source synthetic
.\.venv\Scripts\python.exe -m app.export_demo --source synthetic --out ..\docs\data.js
```

## View

From the repository root:

```powershell
py -m http.server 8001 --directory docs
# visit http://localhost:8001/
```

Or open `docs/index.html` directly in a browser.

## Safety and simulation boundary

All data is fictional and all rules are demonstration placeholders. Review decisions, consent confirmation, appointment choices and the demo audit log are stored in browser `localStorage` only. They do not write to the API or PostgreSQL.

The exported payload contract is specified in [the SRS](srs.md), section FR-6.
