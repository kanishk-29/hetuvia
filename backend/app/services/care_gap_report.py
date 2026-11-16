from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.enums import CareGapOutcome
from app.db.models import CareGapFinding, Person
from app.services.care_gap_runner import CareGapSummary

BANNER = "DEMONSTRATION RULES: placeholders for software testing. Not an Abu Dhabi guideline and not clinical advice."
OUTCOME_ORDER = ("overdue", "due", "up_to_date", "not_eligible", "not_assessable")
OUTCOME_RANK = {CareGapOutcome.OVERDUE: 0, CareGapOutcome.DUE: 1, CareGapOutcome.NOT_ASSESSABLE: 2}


def format_care_gap_summary(summary: CareGapSummary) -> str:
    lines = [
        BANNER,
        "",
        f"Care-gap check for source '{summary.source_system}' evaluated on {summary.evaluated_on}",
        f"  people checked: {summary.people}",
        f"  rule evaluations: {summary.evaluations}",
        f"  findings stored (overdue, due, not assessable): {summary.stored_findings}",
        "",
    ]
    for rule_id, counts in summary.by_rule_outcome.items():
        lines.append(f"{rule_id}:")
        lines += [f"  {outcome}: {counts.get(outcome, 0)}" for outcome in OUTCOME_ORDER]
        gaps = counts.get("overdue", 0) + counts.get("due", 0)
        lines.append(f"  -> care gaps (overdue + due): {gaps}; "
                     f"information gaps (not assessable): {counts.get('not_assessable', 0)}")
    return "\n".join(lines)


def format_care_gap_person_report(db: Session, source_system: str, source_record_id: str) -> str:
    person = db.scalars(select(Person).where(
        Person.source_system == source_system, Person.source_record_id == source_record_id)).first()
    if person is None:
        raise LookupError(f"No person '{source_record_id}' in source '{source_system}'")

    lines = [
        BANNER, "",
        f"Person {source_record_id} ({person.person_id})",
        f"  source: {source_system}",
        f"  date of birth: {person.date_of_birth or '[unknown - not recorded]'}",
        f"  status: {person.status.value}",
    ]
    stored = db.scalar(select(func.count()).select_from(CareGapFinding)
                       .where(CareGapFinding.source_system == source_system))
    if not stored:
        lines += ["", "No care-gap findings are stored for this source yet. Run: python -m app.cli care-gap-check"]
        return "\n".join(lines)

    findings = sorted(
        db.scalars(select(CareGapFinding).where(CareGapFinding.person_id == person.person_id)),
        key=lambda f: (OUTCOME_RANK[f.outcome], f.rule_id),
    )
    if not findings:
        lines += ["", "No stored findings: for every rule in effect on the run date this person is "
                      "up to date or not eligible."]
        return "\n".join(lines)

    lines += ["", f"Findings (evaluated on {findings[0].evaluated_on}):"]
    for f in findings:
        ev = f.evidence
        age = f.age_years if f.age_years is not None else "unknown"
        lines.append(f"  [{f.outcome.value}] {f.rule_id} v{f.rule_version} ({f.service_type})")
        lines.append(f"    {f.message}")
        lines.append(f"    facts: age {age}, born {ev.get('date_of_birth') or 'unknown'}, "
                     f"last completed {f.last_completed_on or 'never'}, "
                     f"next due {f.due_date or 'not computed'}, "
                     f"completed-without-date {ev.get('undated_completed_count', 0)}")
        if ev.get("reason"):
            lines.append(f"    reason: {ev['reason']}")
        lines.append(f"    rule status: {ev.get('rule_status')}; source: {ev.get('rule_source')}")
    return "\n".join(lines)