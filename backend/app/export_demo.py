"""Export the engines' stored output for one source as a static data file for the demo page.

Run from the backend folder with the venv active:
    python -m app.export_demo --out ../docs/data.js
Run quality-check, care-gap-check and recommend first, so there is something to export.
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.synthetic_generator import REFERENCE_DATE
from app.db.models import (
    CareGapFinding,
    Condition,
    DataQualityFinding,
    Encounter,
    Observation,
    Person,
    Recommendation,
    ScreeningEvent,
)
from app.db.session import get_session_factory
from app.services.rule_loader import load_rules

LABEL = ("DEMONSTRATION: 100% fictional data and placeholder rules. "
         "Not an Abu Dhabi guideline and not clinical advice.")

# The demo is served from the docs/ root (GitHub Pages), so data.js must sit beside index.html.
DEFAULT_EXPORT_PATH = "../docs/data.js"


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _day(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).date().isoformat() if moment is not None else None


def _group(db: Session, model, source: str, *order):
    groups = defaultdict(list)
    for row in db.scalars(select(model).where(model.source_system == source).order_by(*order)):
        groups[row.person_id].append(row)
    return groups


def build_export(db: Session, source: str, evaluated_on: date) -> dict:
    """Export stored output; the reported evaluation date comes from the stored rows."""
    people = db.scalars(
        select(Person).where(Person.source_system == source).order_by(Person.source_record_id)
    ).all()
    encounters = _group(db, Encounter, source, Encounter.encounter_date, Encounter.id)
    observations = _group(db, Observation, source, Observation.observed_at, Observation.id)
    screenings = _group(db, ScreeningEvent, source, ScreeningEvent.id)
    conditions = _group(db, Condition, source, Condition.id)
    quality = _group(db, DataQualityFinding, source, DataQualityFinding.rule_code, DataQualityFinding.id)
    gaps = _group(db, CareGapFinding, source, CareGapFinding.rule_id, CareGapFinding.id)
    recs = _group(db, Recommendation, source, Recommendation.pathway_code, Recommendation.id)

    stored_dates = {
        value
        for model in (CareGapFinding, DataQualityFinding, Recommendation)
        for value in db.scalars(select(model.evaluated_on).where(model.source_system == source).distinct())
    }
    if len(stored_dates) > 1:
        dates = ", ".join(sorted(d.isoformat() for d in stored_dates))
        raise ValueError(
            f"Stored output for source '{source}' has mixed evaluation dates: {dates}. "
            "Rerun quality-check, care-gap-check and recommend with the same --date before exporting."
        )
    evaluated_on = next(iter(stored_dates), evaluated_on)

    out = []
    for p in people:
        pid = p.person_id
        out.append({
            "id": p.source_record_id,
            "dob": _iso(p.date_of_birth),
            "sex": p.sex_recorded,
            "language": p.preferred_language,
            "area": p.area_code,
            "status": p.status.value,
            "family_history": p.family_history_state.value,
            "encounters": [
                {"id": str(e.id), "date": _iso(e.encounter_date), "type": e.encounter_type, "status": e.status.value}
                for e in encounters[pid]
            ],
            "observations": [
                {"id": str(o.id), "date": _day(o.observed_at), "type": o.observation_type,
                 "state": o.value_state.value,
                 "value": float(o.value_numeric) if o.value_numeric is not None else None,
                 "unit": o.unit, "encounter_id": str(o.encounter_id) if o.encounter_id else None}
                for o in observations[pid]
            ],
            "screenings": [
                {"id": str(s.id), "type": s.screening_type, "status": s.result_status.value,
                 "due": _iso(s.due_date), "completed": _iso(s.completed_on)}
                for s in screenings[pid]
            ],
            "conditions": [
                {"context": c.context.value, "code": c.condition_code, "label": c.condition_label,
                 "status": c.status.value, "onset": _iso(c.onset_date)}
                for c in conditions[pid]
            ],
            "dq": [
                {"rule": f.rule_code, "severity": f.severity.value, "field": f.field_name,
                 "state": f.field_state.value if f.field_state else None, "message": f.message,
                 "subject_table": f.subject_table, "subject_id": str(f.subject_id)}
                for f in quality[pid]
            ],
            "gaps": [
                {"rule_id": g.rule_id, "rule_version": g.rule_version, "service_type": g.service_type,
                 "outcome": g.outcome.value, "message": g.message, "due": _iso(g.due_date),
                 "last": _iso(g.last_completed_on), "age": g.age_years, "evidence": g.evidence}
                for g in gaps[pid]
            ],
            "recs": [
                {"id": str(r.id), "kind": r.kind.value, "pathway_code": r.pathway_code,
                 "pathway_title": r.pathway_title, "rule_id": r.rule_id, "rule_version": r.rule_version,
                 "priority": r.priority.value, "status": r.status.value, "reasons": r.priority_reasons,
                 "uncertainty": r.uncertainty, "review_required": r.review_required_reason,
                 "evidence": r.evidence}
                for r in recs[pid]
            ],
        })

    return {
        "meta": {
            "source": source,
            "evaluated_on": evaluated_on.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "rule_set": "demo_rules_v1",
            "label": LABEL,
        },
        "rules": [
            {"rule_id": r.rule_id, "version": r.version, "title": r.title, "service_type": r.service_type,
             "status": r.status, "min_age": r.min_age_years, "max_age": r.max_age_years,
             "interval_days": r.interval_days, "lead_days": r.lead_days, "grace_days": r.grace_days,
             "source": r.source}
            for r in load_rules()
        ],
        "people": out,
    }


def _date_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as problem:
        raise argparse.ArgumentTypeError(f"invalid date '{text}': expected YYYY-MM-DD") from problem


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.export_demo")
    parser.add_argument("--source", default="synthetic")
    parser.add_argument("--date", type=_date_arg,
                        help="Evaluation date, YYYY-MM-DD (synthetic defaults to its reference date)")
    parser.add_argument("--out", default=DEFAULT_EXPORT_PATH)
    args = parser.parse_args()
    evaluated_on = args.date if args.date is not None else (
        REFERENCE_DATE if args.source == "synthetic" else date.today())

    with get_session_factory()() as db:
        data = build_export(db, args.source, evaluated_on)

    people = data["people"]
    n_recs = sum(len(p["recs"]) for p in people)
    if not people or not n_recs:
        raise SystemExit("Nothing to export. Run: quality-check, care-gap-check, then "
                         "python -m app.workflow_cli recommend")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.HETUVIA_DATA=" + json.dumps(data, separators=(",", ":")) + ";", encoding="utf-8")
    print(f"Exported {len(people)} people and {n_recs} recommendations to {out} "
          f"({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
