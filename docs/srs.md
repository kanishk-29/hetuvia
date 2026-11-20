# Software Requirements Specification (SRS)

## HETUVIA — Preventive Care Coordination Prototype

| Item | Value |
|---|---|
| Document version | 1.0 |
| Status | As-built baseline specification |
| Date | 2026-11-20 |
| Baseline commit | `5a6d9d7` — `demo: static HETUVIA demo page and export command` |
| Repository | `https://github.com/kanishk-29/hetuvia.git` |
| Scope | Backend engines, CLI workflows, persistence, static demo, health API and thin frontend |
| Supersedes | Empty placeholders `docs/product_scope.md`, `docs/api_contract.md`, `docs/rule_catalogue.md` |
| Intended audience | Product owner, developers, testers, reviewers, demonstrators |

> **Safety notice.** HETUVIA is a demonstration prototype. All data is fictional and all rules and pathways are labelled `DEMONSTRATION`. It is not an Abu Dhabi guideline, not clinical advice, and must not be used with identifiable patient data or to make clinical decisions.

---

## 1. Introduction

### 1.1 Purpose

This SRS defines the functional and non-functional requirements of HETUVIA as implemented at the baseline commit. It is the maintained specification for the repository and replaces the empty scope, API-contract and rule-catalogue placeholder documents. It also records which capabilities are explicitly out of scope so that the demonstration is not mistaken for a clinical product.

### 1.2 Scope

| Classification | Capabilities |
|---|---|
| **Implemented (M)** | Synthetic population generation; CSV import with validation and quarantine; 10 data-quality rules; versioned demonstration care-gap rules; care-gap judgement with evidence; recommendation generation and priority; human review with audit trail; static demo export and UI; health API; 125 automated tests |
| **Planned (P)** | Backend outreach decision service referenced as “Chunk 10” in `docs/care_gap_rules.md`; real cited guideline source required before any rule can become `approved`; replacement of placeholder frontend with full application |
| **Out of scope (O)** | Real patient data, EHR/FHIR integration, clinical risk scoring, automated outreach delivery, appointment booking against a real system, authentication/authorisation, unit conversion, person matching by name or demographics |

Priority legend used in Section 3: **M** = mandatory for the current prototype and implemented in the baseline; **P** = planned and not yet implemented; **O** = explicitly out of scope.

### 1.3 Definitions

| Term | Meaning in HETUVIA |
|---|---|
| **Source system** | Logical namespace for imported or generated records, for example `synthetic` or `csv_import`. |
| **Source record ID** | Identifier supplied by the source. A person is identified only by `(source_system, source_record_id)`. |
| **Data state** | Explicit state of a value: `present`, `explicitly_absent`, `unknown`, `not_collected`, `not_applicable` or `stale`. |
| **Information gap** | Missing or unreliable information. Represented by a DQ finding and/or a `not_assessable` care-gap verdict; never treated as a negative clinical finding. |
| **Care gap** | A service that is `overdue` or `due` under a rule. `not_assessable` is stored for attention but is not a care gap. |
| **Pathway** | A demonstration action proposal mapped from a rule outcome: a service pathway or the information-resolution pathway. |
| **Outreach priority** | Work-queue ordering (`contact_now`, `review_data_first`, `routine`). It is not clinical urgency. |
| **Derived finding** | DQ or care-gap row recomputed from source records on every run; never edited manually. |
| **Recommendation** | Persistent proposed pathway. Human decisions and history are never deleted; unresolved needs become `closed` and can be `reopened`. |

### 1.4 References

- `README.md` — setup, CLI quick start and repository notes.
- `backend/rules/demo_rules_v1.json` — the only shipped rule set.
- `docs/care_gap_rules.md` — care-gap outcome definitions and safety notes.
- `docs/dq_rule_catalogue.md` — data-quality rule catalogue, version `demo-1`.
- `docs/import_format.md` — CSV column and validation contract.
- `docs/data_dictionary.md` — synthetic population and planted-gap answer key.
- `docs/demo/index.html`, `docs/demo/data.js` — static demo and generated payload.
- Commit history `b372add` through `5a6d9d7` (13 commits, chunks 1–6b and 8 plus demo).

---

## 2. Overall description

### 2.1 Product perspective

HETUVIA is a backend-centred prototype with three presentation surfaces:

1. **CLI workflows** are the primary operator interface. They load data, run engines, review recommendations and export the demo payload.
2. **FastAPI service** currently exposes a single health endpoint used by the thin Next.js page.
3. **Static demo** (`docs/demo/index.html`) reads `data.js` and renders work queues, person detail, simulated review/outreach, insights and an in-browser audit log. It requires no running backend.

The engines are separated into pure functions (`dq_rules.py`, `care_gap_engine.py`, `recommendation_engine.py`) and persistence orchestrators (`dq_runner.py`, `care_gap_runner.py`, `recommendation_runner.py`). This keeps decisions deterministic and testable without a database.

### 2.2 User classes

| User class | Needs | Interface |
|---|---|---|
| Demonstration visitor | Explore a fictional population and understand safeguards without clinical risk | `docs/demo/index.html` |
| Data operator | Seed or import data, run checks, inspect reports, reset a source | `python -m app.cli` |
| Clinical reviewer | See proposed pathways with evidence and record approve/defer/reject decisions | `python -m app.workflow_cli review`, demo review screen (simulated) |
| Developer / tester | Reproducible fixtures, pure rule functions, automated verification | Pytest suite, Alembic migrations, documented CLI |
| Rule curator | Add or version labelled demonstration rules with a citable source before approval | `backend/rules/demo_rules_v1.json`, rule loader |

### 2.3 Operating environment

| Component | Baseline |
|---|---|
| Language/runtime | Python 3.11+; validated on 3.13.9 |
| Backend | FastAPI 0.162.5, Starlette 1.10.0, SQLAlchemy 2.1.8, Pydantic 2.14.3, Alembic 1.20.1, psycopg 3.3.9, pytest 9.2.0 |
| Database | PostgreSQL 16 (Docker Compose service `db`, development credentials `hetuvia` / `hetuvia_dev`) |
| Frontend | Next.js 16.4.6, React 19.3.0, Tailwind CSS 4.3.3 |
| Static demo | Plain HTML/CSS/JavaScript; `docs/.nojekyll` permits GitHub Pages hosting |
| Configuration | `backend/.env` from `.env.example`; CORS default `http://localhost:3000` |

### 2.4 Constraints and assumptions

1. The database must be reachable via `DATABASE_URL` before CLI commands or database tests run.
2. Synthetic evaluation defaults to the fixed reference date `2026-11-01`; other sources default to `date.today()` unless `--date` is supplied.
3. `backend/requirements.txt` is UTF-8 without a BOM; install with pip from the file as-is.
4. The frontend instruction file `frontend/AGENTS.md` must be followed when writing frontend code: consult the Next.js 16.4.6 guides under `frontend/node_modules/next/dist/docs/` first. No frontend code is changed by this SRS.
5. The committed `.env.example` contains development-only credentials; no production secret is committed.
6. The static demo is a presentation of exported results, not a live client of the API.

### 2.5 Governing principles

- **Explicit missingness.** Blank or unknown values are recorded as states, never coerced to a negative or normal value.
- **Provenance and explainability.** Every verdict carries the rule identity, version, status, source and the facts used.
- **Determinism.** The same facts, rule version and evaluation date always produce the same verdict.
- **Human-in-the-loop.** No recommendation is actionable for outreach until a reviewer approves it.
- **Non-clinical labelling.** Rules, pathways and the demo banner repeat that the content is a demonstration placeholder.
- **Append-only history.** Human decisions and system lifecycle changes are recorded in `audit_events`; resets do not erase them.

---

## 3. Functional requirements

### FR-1 Data provisioning and import

- **FR-1.1 — M — Synthetic seeding.** The system shall generate a deterministic linked fictional population using `seed` (default 42) and `people` (default 300), with source system `synthetic`, fixed reference date `2026-11-01`, stable UUID identities and all ten documented planted gap kinds: `weight_unknown`, `height_not_collected`, `stale_bp`, `completed_screening_no_date`, `screening_due_date_unknown`, `family_history_unknown`, `family_history_not_collected`, `no_encounters`, `missing_dob`, `missing_language`.  
  *Acceptance:* Re-running `seed` with the same parameters reproduces the same population and the CLI prints planted counts per kind.

- **FR-1.2 — M — CSV ingestion.** The system shall accept a folder containing any of `people.csv`, `encounters.csv`, `observations.csv`, require UTF-8 with a header row, and load them in fixed order people → encounters → observations.  
  *Acceptance:* A folder with no recognised file raises `FileNotFoundError`; sample files in `backend/sample_import/` import successfully.

- **FR-1.3 — M — Validation and quarantine.** The system shall validate every row and write rejected or skipped rows to `import_rejections` with file name, row number, reason code, reason detail and the raw row. Missing required header columns shall be rejected with reason `missing_columns` at row 0. Validation shall enforce ISO dates not in the future and not before 1900; explicit data states; a numeric positive value only when `value_state = present`; accepted units `cm`, `kg`, `mmHg` checked but never converted; and valid encounter statuses.  
  *Acceptance:* Invalid rows never reach domain tables; `import_batches` records read/loaded/skipped/rejected counts.

- **FR-1.4 — M — Source identity and deduplication.** The system shall match records only by `(source_system, source_record_id)`. Rows with a duplicate source ID inside one file shall be rejected; rows already imported from the same source shall be skipped and left unchanged; encounters and observations referencing unknown or cross-person source IDs shall be rejected.  
  *Acceptance:* No merge is performed using name, date of birth, address or any other demographic attribute.

- **FR-1.5 — M — Import atomicity.** The importer shall flush but not commit; the CLI commits only after a successful run so an unexpected error rolls back the whole batch.  
  *Acceptance:* A failed run leaves no partially loaded batch.

- **FR-1.6 — M — Source reset.** The system shall provide `reset-source <name>` and `reset-synthetic` to delete all records loaded by one source.  
  *Acceptance:* Domain and derived rows for that source are removed; `audit_events` rows remain.

### FR-2 Data-quality evaluation

- **FR-2.1 — M — Pure DQ engine.** The system shall evaluate immutable person snapshots with pure functions in `app/services/dq_rules.py`, producing finding drafts without database or side effects.

- **FR-2.2 — M — DQ rule catalogue.** The system shall implement DQ-001 through DQ-010 exactly as described in Section 5.1 and `docs/dq_rule_catalogue.md`, with severities `info`, `warning` and `error`.

- **FR-2.3 — M — Missing-data safety.** The engine shall report unknown, not-collected and stale values as gaps. It shall never turn a missing value into a negative finding or into evidence that everything is fine.

- **FR-2.4 — M — Staleness parameter.** DQ-006 shall apply only to `systolic_blood_pressure` and shall use a demonstration staleness limit of 730 days from the evaluation date. Staleness is derived from the reading date, not stored as a value state.

- **FR-2.5 — M — DQ persistence.** `run_quality_check` shall delete existing DQ findings for the source, evaluate all people, store each finding with rule code/version, severity, subject table and ID, field name, field state, message and evaluation date, and return a summary by rule and severity. The caller commits.

- **FR-2.6 — M — Answer-key verification.** The test suite shall grade DQ findings against the synthetic population’s planted gap answer key to verify that each planted kind is detected.  
  *Acceptance:* `backend/tests/test_dq_grading.py` passes.

### FR-3 Care-gap evaluation

- **FR-3.1 — M — Rule loading and sync.** The system shall load and validate `demo_rules_v1.json`, then upsert rules into `guideline_rules` keyed by `(rule_id, version)` before evaluating a source.

- **FR-3.2 — M — Pure care-gap judge.** The system shall evaluate one person’s facts against one rule with a pure function returning one of `overdue`, `due`, `up_to_date`, `not_eligible` or `not_assessable`, plus a message and evidence dictionary.

- **FR-3.3 — M — Eligibility order.** Evaluation shall apply checks in this order: rule effective date; `inactive_person` exclusion; missing date of birth; age range; completed-service matching. Missing date of birth shall produce `not_assessable`; out-of-range age, inactive status or an out-of-effect rule shall produce `not_eligible`.

- **FR-3.4 — M — Completed service handling.** Only screening events with `result_status = completed` count as completions. Completions dated after the evaluation date are ignored and counted in evidence. `declined`, `missed` and `pending` events never count as completed; deciding whether to contact someone who declined is a planned outreach decision (P), not a care-gap decision.

- **FR-3.5 — M — Due date calculation.** If dated completions exist, the next due date is the latest completion date plus `interval_days`. Otherwise the person is due from the later of their eligibility date (`date_of_birth + min_age_years`) and the rule’s `effective_from`.

- **FR-3.6 — M — Outcome thresholds.** With `due` as the calculated date: `overdue` when `evaluated_on > due + grace_days`; `due` when `evaluated_on >= due - lead_days`; otherwise `up_to_date`.

- **FR-3.7 — M — Not-assessable override.** `not_assessable` shall be returned when a matching completed service has no completion date, and shall also override an `overdue`/`due` result when an undated completion might be more recent. This is an information gap, not a care gap.

- **FR-3.8 — M — Evidence.** Every stored verdict shall include evidence containing rule ID, version, status and source; evaluation date; date of birth; person status; computed age; basis; next due date; last completion date; and counts of undated and ignored future completions.

- **FR-3.9 — M — Care-gap persistence.** The runner shall replace only `overdue`, `due` and `not_assessable` findings for the source. `up_to_date` and `not_eligible` are counted in the summary but not stored. The caller commits.

### FR-4 Recommendations, priority and review

- **FR-4.1 — M — Service pathway mapping.** For `overdue` or `due` findings whose rule ID is in `SERVICE_PATHWAYS`, the system shall propose the mapped demonstration service pathway. Baseline mapping: `DEMO-WCV` → `DEMO-PATHWAY-WCV` / “Well-Child Visit (demonstration)”; `DEMO-ADULT-SCREEN` → `DEMO-PATHWAY-ADULT` / “Adult Comprehensive Screening (demonstration)”.

- **FR-4.2 — M — Information pathway.** When a `not_assessable` care-gap finding or a blocking DQ finding (`DQ-001`, `DQ-003`) exists, the system shall propose one `DEMO-PATHWAY-INFO` information recommendation that gathers the missing information before a service decision.

- **FR-4.3 — M — Outreach priority.** `overdue` service recommendations shall be `contact_now`, `due` service recommendations `routine`, and information recommendations `review_data_first`. A person’s queue category is the most urgent of their open recommendations. Every recommendation shall store an explicit statement that outreach priority is not clinical urgency, plus uncertainty and review-required text.

- **FR-4.4 — M — Recommendation lifecycle.** Recommendations are unique by `(source_system, person_id, pathway_code, rule_id)`. Re-running shall update existing rows, close rows whose need disappeared, and reopen previously closed rows whose need returned with a fresh review. Recommendations are never deleted.

- **FR-4.5 — M — Human review.** New and reopened recommendations shall start `pending_review`. A reviewer may `approve`, `defer` or `reject` only when the current status is `pending_review` or `deferred`; a reviewer name is required; a note is required for `defer` and `reject`.

- **FR-4.6 — M — Audit of decisions and lifecycle.** Every review decision and system reopen/close shall write an `audit_events` row with actor, role, action, object type/ID, person ID, timestamp and detail.

- **FR-4.7 — O — Outreach execution.** The backend shall not send messages, book real appointments or decide contact actions from declined screenings. The static demo may simulate these interactions locally.

### FR-5 Rule management

- **FR-5.1 — M — Labelled rule file.** The shipped rule set shall be a JSON file containing `rule_set`, `label` and at least one rule. Each rule requires ID, version, title, service type, status, age range, interval, lead/grace days, exclusions, effective dates and a source description.

- **FR-5.2 — M — Validation.** The loader shall use Pydantic validation to enforce non-empty identifiers, non-negative or positive numeric fields, `max_age_years >= min_age_years`, `effective_to >= effective_from`, unique `(rule_id, version)` pairs and a source string of at least 10 characters.

- **FR-5.3 — M — Approval guard.** The loader shall accept only `status = demonstration`. A rule marked `approved` shall be refused until a confirmed, cited source exists.

- **FR-5.4 — M — Versioned persistence.** Rules shall be upserted by `(rule_id, version)` and never edited in place under a new meaning. A new rule meaning requires a new version row.

### FR-6 Static demo export and presentation

- **FR-6.1 — M — Export preconditions.** `export_demo` shall export one source only when at least one person and at least one recommendation exist; otherwise it shall exit with instructions to run quality-check, care-gap-check and recommend first.

- **FR-6.2 — M — Payload.** The export shall contain `meta` (source, evaluation date, generation timestamp, `rule_set = demo_rules_v1` and the demonstration warning label), the loaded `rules`, and a `people` array with nested encounters, observations, screenings, conditions, DQ findings, care-gap findings and recommendations including evidence.

- **FR-6.3 — M — Output format.** The exporter shall write compact UTF-8 JSON to `docs/demo/data.js` prefixed with `window.HETUVIA_DATA=` and suffixed with `;`.

- **FR-6.4 — M — Demo views.** `docs/demo/index.html` shall render: overview, work queue, person detail, recommendation review, outreach and appointments, community insights, audit log, and about/safeguards. It shall support filtering by area, priority, kind and status and searching by person ID.

- **FR-6.5 — M — Simulation boundary.** Review decisions, consent confirmation, appointment choices and the demo audit log are stored in browser `localStorage`, keyed to the generated-data signature. They are demonstrations only and do not persist to the API or database.

- **FR-6.6 — M — Static hosting.** The demo shall run from local files or any static server; `docs/.nojekyll` supports GitHub Pages. The page shall display a visible demonstration/fictional-data label.

### FR-7 API and thin frontend

- **FR-7.1 — M — FastAPI application.** The system shall expose a FastAPI app titled from `settings.app_name`, with CORS origins from configuration, allowed methods `GET` and `POST`, and all headers allowed.

- **FR-7.2 — M — Health endpoint.** The system shall expose exactly one API route, `GET /api/v1/health`, returning `{"status":"ok","service":"hetuvia-api"}`.

- **FR-7.3 — M — Frontend health check.** The Next.js page shall call the health endpoint once on mount using `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) and display `checking...`, `OK` or `unreachable`.

- **FR-7.4 — O — Clinical API.** No patient, finding, recommendation or review endpoints are provided in the baseline.

### FR-8 Reporting and traceability

- **FR-8.1 — M — Summaries.** Quality, care-gap and recommendation runs shall print human-readable summaries with counts by rule, severity, outcome or priority as applicable.

- **FR-8.2 — M — Person reports.** `quality-report` and `care-gap-report` shall show one person’s findings, messages and evidence, addressed by `(source, source_record_id)`.

- **FR-8.3 — M — Provenance.** Domain records shall carry `source_system`, `source_record_id`, `recorded_at`, `verification` and `imported_at`. Enum values are stored as text with database CHECK constraints.

- **FR-8.4 — M — Durable audit.** `audit_events` has no foreign keys so source resets cannot delete history. The table is append-only at the application level.

---

## 4. Data requirements

### 4.1 Logical schema

| Table | Purpose | Key constraints / notes |
|---|---|---|
| `people` | Person demographics and family-history state | UUID PK; unique `(source_system, source_record_id)`; nullable DOB means unknown; provenance fields |
| `family_relationships` | Directed links between people | Relationship type from `RelationshipType` |
| `encounters` | Visit events | Linked to person; status scheduled/completed/cancelled/no_show; provenance |
| `conditions` | Personal or family-history conditions | `ConditionContext`, `ConditionStatus`; codes starting `DEMO-` are placeholders |
| `observations` | Height, weight and systolic BP readings | Value state, numeric value, unit and optional encounter link |
| `screening_events` | Due/completed screening events | Screening type, due date, result status, completion date |
| `guideline_rules` | Versioned rules | Unique `(rule_id, version)`; status demonstration/approved; effective dates |
| `import_batches` | Receipt per import run | Status running/completed/failed; row counts; timestamps |
| `import_rejections` | Quarantined rows | Batch FK, file name, row number, reason code/detail, raw JSON row |
| `data_quality_findings` | Derived DQ findings | Subject table/ID, field, rule code/version, severity, field state |
| `care_gap_findings` | Derived care-gap verdicts | Rule ID/version, outcome, due/last dates, age, message, evidence JSON |
| `recommendations` | Proposed pathways and review state | Unique `(source_system, person_id, pathway_code, rule_id)`; status, reviewer fields, evidence JSON |
| `audit_events` | Append-only history | Actor, role, action, object type/ID, person ID, detail JSON; no FKs |

Six Alembic revisions create these tables in sequence: `d8f0e1b1b28e` → `283d73fe447e` → `a2ff5238c20f` → `3233e4718e78` → `8ae5e64e1283` → `4547c4c46435`.

### 4.2 Enumerations

| Enumeration | Values |
|---|---|
| `DataState` | `present`, `explicitly_absent`, `unknown`, `not_collected`, `not_applicable`, `stale` |
| `Verification` | `verified`, `reported`, `estimated`, `missing` |
| `PersonStatus` | `active`, `inactive` |
| `EncounterStatus` | `scheduled`, `completed`, `cancelled`, `no_show` |
| `ScreeningStatus` | `pending`, `completed`, `declined`, `missed` |
| `ConditionContext` / `ConditionStatus` | `personal`, `family_history` / `active`, `resolved`, `inactive` |
| `Severity` | `info`, `warning`, `error` |
| `RuleStatus` | `demonstration`, `approved` |
| `CareGapOutcome` | `overdue`, `due`, `up_to_date`, `not_eligible`, `not_assessable` |
| `RecommendationKind` | `service`, `information` |
| `OutreachPriority` | `contact_now`, `review_data_first`, `routine` |
| `RecommendationStatus` | `pending_review`, `approved`, `deferred`, `rejected`, `closed` |
| `ImportStatus` | `running`, `completed`, `failed` |

### 4.3 Missing-data semantics

| Situation | Required behaviour |
|---|---|
| Blank DOB in CSV | Stored as `NULL`, reported as `DQ-001`; care gap `not_assessable` |
| Family history blank in CSV | Rejected; the state must be explicit |
| Measurement state unknown/not collected | Stored with state and no value; reported as `DQ-005` |
| Screening marked completed without date | Reported as `DQ-007` and can force care gap `not_assessable` |
| Screening without due date | Reported as `DQ-008`; not converted to “not due” |
| Old BP reading | Reported as `DQ-006` using the 730-day demonstration parameter; original value retained |
| Conflicting dates | Reported as `DQ-010` with severity `error` |

---

## 5. Rules and decision logic

### 5.1 Data-quality rules (version `demo-1`)

| Code | Finds | Severity |
|---|---|---|
| DQ-001 | Date of birth missing | warning |
| DQ-002 | Preferred language or area missing | info |
| DQ-003 | Family history `unknown`, `not_collected` or `stale` | warning |
| DQ-004 | Family-history state contradicts its entries | error |
| DQ-005 | Measurement recorded as `unknown` or `not_collected` | warning |
| DQ-006 | Latest systolic BP reading older than 730 days | warning |
| DQ-007 | Screening completed but completion date missing | warning |
| DQ-008 | Screening has no due date | info |
| DQ-009 | No encounters on file | info |
| DQ-010 | Event before birth or observation date differing from encounter date | error |

### 5.2 Demonstration care-gap rules

| Rule ID | Version | Ages | Interval | Lead | Grace | Exclusion | Effective from |
|---|---|---:|---:|---:|---:|---|---|
| `DEMO-WCV` | 1 | 0–17 | 365 days | 60 days | 30 days | `inactive_person` | 2021-01-01 |
| `DEMO-ADULT-SCREEN` | 1 | 30–74 | 730 days | 60 days | 30 days | `inactive_person` | 2021-01-01 |

Both rules are labelled `DEMONSTRATION` with source text explicitly stating they are placeholders, not an Abu Dhabi guideline.

### 5.3 Care-gap decision sequence

```text
rule in effect on evaluation date?
    no  -> not_eligible
yes: inactive person excluded?
    yes -> not_eligible
missing date of birth?
    yes -> not_assessable
age within rule range?
    no  -> not_eligible
collect completed, dated (<= evaluation date) and undated matching services
dated completion exists -> due = last completion + interval
no dated completion       -> due = max(DOB + min age, effective_from)
is there any undated completion? -> not_assessable
evaluated_on > due + grace -> overdue
evaluated_on >= due - lead  -> due
otherwise                   -> up_to_date
```

### 5.4 Recommendation and review state model

```text
new / reopened -> pending_review
pending_review -> approved | deferred | rejected
deferred       -> approved | deferred | rejected
need resolved  -> closed (row retained)
need returns   -> pending_review (reopened, audited)
```

An `approved` recommendation is required before the demo presents outbound outreach as available. Priority never substitutes for clinical review.

---

## 6. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Determinism | Seeded generation and pure engines shall produce identical outputs for the same inputs, rule version and evaluation date. |
| NFR-2 | Explainability | Every stored care-gap finding and recommendation shall contain machine-readable evidence; person reports shall show the human-readable message. |
| NFR-3 | Safety | Missing data shall never be coerced; `not_assessable` shall remain distinct from care gaps; demonstration labels shall appear in rules, exports and the demo. |
| NFR-4 | Testability | Maintain the 125-test baseline. Each new rule, validator or workflow shall add focused tests; pure rule logic shall be testable without a database. |
| NFR-5 | Performance | The 300-person seed, three-engine workflow and demo export shall complete interactively on a local PostgreSQL instance. The current full test suite completes in about 71 seconds. |
| NFR-6 | Maintainability | Keep rule definitions in data, keep pure logic separate from persistence orchestration, and keep CLI entry points thin. |
| NFR-7 | Privacy and security | Use only fictional data. No authentication, authorisation or PHI safeguards are implemented; do not deploy this baseline with real patient data. Development DB credentials and localhost-only CORS are intentional. |
| NFR-8 | Compatibility | Python 3.11+ and PostgreSQL 16 are the supported backend baseline; Next.js 16.4.6 guides under `frontend/node_modules/next/dist/docs/` govern frontend changes. |
| NFR-9 | Accessibility and clarity | The demo shall use readable labels, visible warnings and keyboard-accessible form controls; role permissions and demo-only localStorage state shall be stated in the UI. |
| NFR-10 | Observability | Run summaries and `audit_events` shall provide a trace of what ran, what changed and who decided. |

---

## 7. External interfaces

### 7.1 Command-line interface

All commands run from `backend/` with the virtual environment active.

| Command | Key arguments | Output |
|---|---|---|
| `python -m app.cli seed` | `--seed`, `--people` | Seeded counts and planted-gap counts |
| `python -m app.cli import-csv` | directory, `--source` | Import report by file |
| `python -m app.cli quality-check` | `--source`, `--date` | DQ summary |
| `python -m app.cli quality-report` | source record ID, `--source` | Person DQ report |
| `python -m app.cli care-gap-check` | `--source`, `--date` | Care-gap summary |
| `python -m app.cli care-gap-report` | source record ID, `--source` | Person care-gap report |
| `python -m app.cli reset-source` / `reset-synthetic` | source name | Deletion confirmation |
| `python -m app.workflow_cli recommend` | `--source`, `--date` | Created/updated/reopened/closed and open-priority counts |
| `python -m app.workflow_cli review` | ID, `--decision`, `--reviewer`, `--note` | New recommendation status |
| `python -m app.export_demo` | `--source`, `--date`, `--out` | Exported people/recommendation counts and file size |

### 7.2 HTTP interface

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/health` | None | `200` with `{"status":"ok","service":"hetuvia-api"}` |

### 7.3 CSV interface

| File | Required header columns |
|---|---|
| `people.csv` | `source_record_id`, `date_of_birth`, `sex_recorded`, `preferred_language`, `area_code`, `family_history_state` |
| `encounters.csv` | `source_record_id`, `person_source_id`, `encounter_type`, `encounter_date`, `status` |
| `observations.csv` | `source_record_id`, `person_source_id`, `encounter_source_id`, `observation_type`, `value`, `unit`, `value_state`, `observed_at` |

### 7.4 Static demo data contract

```text
window.HETUVIA_DATA = {
  meta:   { source, evaluated_on, generated_at, rule_set, label },
  rules:  [ { rule_id, version, title, service_type, status, min_age, max_age,
              interval_days, lead_days, grace_days, source } ],
  people: [ { id, dob, sex, language, area, status, family_history,
              encounters[], observations[], screenings[], conditions[],
              dq[], gaps[], recs[] } ]
};
```

---

## 8. Verification and acceptance

### 8.1 Test strategy

| Layer | Approach |
|---|---|
| Pure rules | Unit tests for all DQ rules, care-gap outcomes, rule-file validation and recommendation mapping |
| Import | Row validation tests, importer integration tests and quarantine assertions |
| Persistence | Migration-backed tests using the real PostgreSQL test database |
| Workflows | Runner tests for replace/close/reopen behaviour and audit writes |
| API | FastAPI `TestClient` health test |
| Answer key | Grading tests that confirm planted synthetic gaps are detected |

### 8.2 Baseline result

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
# 125 passed, 1 warning in ~71s
```

The warning is a Starlette deprecation notice about `httpx` with `starlette.testclient`; it does not affect results. Tests require the PostgreSQL service from `docker-compose.yml`.

### 8.3 Requirement traceability

| Requirement area | Primary implementation | Primary tests |
|---|---|---|
| FR-1 | `adapters/synthetic_generator.py`, `adapters/csv_adapter.py`, `services/csv_importer.py`, `services/import_validation.py` | `test_synthetic_population.py`, `test_csv_import.py`, `test_import_validation.py`, `test_import_tables.py` |
| FR-2 | `services/dq_rules.py`, `services/dq_runner.py` | `test_dq_rules.py`, `test_dq_grading.py`, `test_dq_table.py` |
| FR-3 / FR-5 | `rules/demo_rules_v1.json`, `services/rule_loader.py`, `services/care_gap_engine.py`, `services/care_gap_runner.py` | `test_rule_loader.py`, `test_care_gap_engine.py`, `test_care_gap_runner.py`, `test_care_gap_tables.py` |
| FR-4 | `services/pathways.py`, `services/recommendation_engine.py`, `services/recommendation_runner.py`, `services/review.py`, `services/audit.py` | `test_recommendation_engine.py`, `test_recommendation_runner.py` |
| FR-6 | `app/export_demo.py`, `docs/demo/index.html`, `docs/demo/data.js` | Export command preconditions; manual demo smoke check |
| FR-7 | `app/main.py`, `api/v1/health.py`, `frontend/app/page.tsx`, `frontend/lib/api/health.ts` | `test_health.py` |
| NFR-1 / NFR-3 | Pure engines and `db/enums.py` CHECK constraints | DQ grading, care-gap engine, database tests |

### 8.4 Acceptance scenarios

1. **Deterministic seed.** Seed twice with seed 42 and 300 people; identities, planted counts and later findings are identical.
2. **Bad CSV row is quarantined.** A row with a future date or blank family-history state appears in `import_rejections` and not in `people`.
3. **No coercion.** A person with `weight_unknown` has DQ-005 and no fabricated weight value.
4. **Undated completion is not a gap.** A completed screening with no date produces `not_assessable`, never `overdue`.
5. **Priority is not urgency.** An overdue service recommendation is `contact_now` but still `pending_review` and carries the non-urgency statement.
6. **Human decision is durable.** After review, status and reviewer fields change and an `audit_events` row is written.
7. **Need resolution keeps history.** Re-running after the gap disappears closes the recommendation rather than deleting it; recurrence reopens it with a new audit entry.
8. **Demo is self-contained.** Opening `docs/demo/index.html` with `data.js` present renders without API calls; browser-local review state does not alter the database.

---

## 9. Current limitations and exclusions

1. Rules and pathways are invented placeholders; no clinical guideline has been confirmed or cited.
2. No real patient data, consent record, contact preference or EHR integration exists. The demo asks a human to confirm consent as a scripted step.
3. No authentication or authorisation; reviewer identity is a free-text name.
4. No backend outreach decision, message delivery or real appointment booking. The demo simulates these in `localStorage`.
5. Only one HTTP endpoint exists; there is no clinical API.
6. The Next.js frontend is a health-status scaffold, not a user application.
7. CSV units are validated but never converted; unknown units cause rejection.
8. People are never merged by demographic similarity.
9. The demo entry point is `docs/demo/index.html`; earlier revisions also contained an unrelated template and a duplicate demo filename.
10. `docs/product_scope.md`, `docs/api_contract.md` and `docs/rule_catalogue.md` remain empty placeholders; this SRS is authoritative.

---

## 10. Roadmap inferred from repository history

| Status | Item | Evidence |
|---|---|---|
| Done | Chunks 1–6b: foundation, database, population, import, DQ engines, care-gap engines, reports and tests | Commits `b372add`–`1a22f34` |
| Done | Chunk 8: pathways, priority, recommendations, review and audit log | Commit `5c41733` |
| Done | Static demo and export command | Commit `5a6d9d7` |
| Planned (P) | Chunk 10 outreach decision service | `docs/care_gap_rules.md` line 12 |
| Planned (P) | Approved, cited rules replacing demonstration placeholders | `docs/care_gap_rules.md`, `rule_loader.py` approval guard |
| Planned (P) | Full frontend consuming clinical APIs | Current scaffold in `frontend/app/page.tsx` |
| Not found | A commit labelled chunk 7 is absent from history | `git log --oneline` |

---

## Appendix A — Commit history

| Date | Commit | Subject |
|---|---|---|
| 2026-11-12 | `b372add` | chunk 1: project foundation |
| 2026-11-13 | `5412ebf` | chunk 2a: postgres in docker and db session |
| 2026-11-13 | `f52bcda` | chunk 2: core tables, migrations, people repository |
| 2026-11-14 | `de2f2ba` | chunk 3a: conditions, screening events, family history state |
| 2026-11-14 | `2107fc6` | chunk 3: seeded synthetic population and seed cli |
| 2026-11-15 | `207fced` | chunk 4a: import tables, uniqueness, row validation |
| 2026-11-15 | `56bff08` | chunk 4b: csv adapter, importer, quarantine and import report |
| 2026-11-15 | `ad01e0d` | chunk 5a: data quality findings table and rules |
| 2026-11-16 | `e217275` | chunk 5b: data quality runner, reports and answer-key grading |
| 2026-11-16 | `01c44ac` | chunk 6a: care gap rules file, loader and judge |
| 2026-11-16 | `1a22f34` | chunk 6b: care gap runner, reports and database tests |
| 2026-11-19 | `5c41733` | chunk 8: pathways, priority, recommendations, review and audit log |
| 2026-11-20 | `5a6d9d7` | demo: static HETUVIA demo page and export command |

All commits are on `main`, which tracks `origin/main`; there are no tags, stashes or additional local branches.

## Appendix B — Demo snapshot

Current `docs/demo/data.js`, regenerated after aligning the synthetic generator with the shipped rules:

| Metric | Value |
|---|---|
| Source | `synthetic` |
| Evaluated on | 2026-11-01 |
| Generated at | 2026-11-20T10:24:55+00:00 |
| Rule set | `demo_rules_v1` (2 rules) |
| People | 300 |
| Recommendations | 198 — 141 service, 57 information; all `pending_review` |
| Care-gap findings | 173 — 132 `overdue`, 32 `not_assessable`, 9 `due` |
| DQ findings | 309 |
| DQ breakdown | DQ-001 12, DQ-002 15, DQ-003 40, DQ-005 139, DQ-006 52, DQ-007 15, DQ-008 19, DQ-009 17 |
| DQ rules with no findings | DQ-004, DQ-010 |
