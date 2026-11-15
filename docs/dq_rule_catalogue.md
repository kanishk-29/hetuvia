# Data-quality rule catalogue (version demo-1)

Demonstration rules about completeness and consistency of records. They say nothing about health.
Severity: info = nice to have, warning = gap that blocks a decision, error = contradiction.
Staleness limit (730 days) is a demonstration parameter, not a clinical threshold.

| Code | What it finds | Severity |
|---|---|---|
| DQ-001 | Date of birth missing | warning |
| DQ-002 | Preferred language or area missing | info |
| DQ-003 | Family history unknown, not collected or stale | warning |
| DQ-004 | Family history state contradicts its entries | error |
| DQ-005 | Measurement recorded as unknown or not collected | warning |
| DQ-006 | Latest blood-pressure reading older than the staleness limit | warning |
| DQ-007 | Screening completed but completion date missing | warning |
| DQ-008 | Screening has no due date | info |
| DQ-009 | No encounters on file | info |
| DQ-010 | Event dated before birth, or observation date differs from its encounter | error |

A missing value is reported as a gap and never converted to a negative value.
