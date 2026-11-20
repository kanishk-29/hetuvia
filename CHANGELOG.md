# Changelog

All notable changes to HETUVIA are documented here. The format follows Keep a Changelog conventions.

## [Unreleased]

### Added

- Read-only operator API endpoints for summary, people, care-gap findings, data-quality findings, recommendations and audit events.
- A Next.js operator console consuming the API, replacing the health-status-only page.
- Regression tests for rule-version immutability, export-date consistency, synthetic/rule alignment and the operator API.
- Short stubs for `docs/product_scope.md`, `docs/api_contract.md` and `docs/rule_catalogue.md` that point to the relevant SRS sections.
- `docs/demo/README.md` describing the demo entry point and data regeneration command.
- A HETUVIA-specific `frontend/README.md`, replacing the `create-next-app` boilerplate.

### Changed

- `docs/demo/index.html` is now the real HETUVIA demo. The previous unrelated LearnVault template and the duplicate `indexx.html` filename were removed.
- `backend/requirements.txt` was converted from UTF-16LE with BOM to UTF-8 without BOM. All pinned versions are unchanged.
- `README.md` was written as the main project guide.
- `docs/srs.md` was added as the as-built baseline specification for commit `5a6d9d7` and updated for the operator API and console.
- `docs/api_contract.md` now documents the read-only HTTP interface.

### Fixed

- `rule_loader.sync_rules` no longer silently edits an existing `(rule_id, version)` row; a changed rule payload must now bump the version.
- The static demo review screen now falls back to a reviewable recommendation when a deep link points to one that is already approved or completed.
- `export_demo` now reports the evaluation date actually stored in the findings and refuses to export mixed evaluation dates.
- The synthetic generator now uses calendar ages and only creates screening types covered by the shipped rules; `docs/demo/data.js` was regenerated.

## [Baseline] - 2026-11-20

- Commits `b372add` through `5a6d9d7` delivered the prototype described in `docs/srs.md`.
- 125 automated backend tests passing at the baseline.
