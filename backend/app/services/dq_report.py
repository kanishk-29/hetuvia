from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.enums import Severity
from app.db.models import DataQualityFinding, Encounter, Person
from app.services.dq_rules import RULE_TITLES
from app.services.dq_runner import QualitySummary

SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def format_summary(summary: QualitySummary) -> str:
    lines = [
        f"Data-quality check for source '{summary.source_system}' evaluated on {summary.evaluated_on}",
        f"  people checked: {summary.people}",
        f"  people with at least one finding: {summary.people_with_findings}",
        f"  findings: {summary.findings}",
        "",
        "By severity:",
    ]
    lines += [f"  {name}: {summary.by_severity.get(name, 0)}" for name in ("error", "warning", "info")]
    lines += ["", "By rule:"]
    lines += [f"  {code} {RULE_TITLES.get(code, '')}: {count}" for code, count in summary.by_rule.items()]
    return "\n".join(lines)


def _field(label: str, value) -> str:
    # A blank is shown as unknown. It is never shown as "none" or "no".
    return f"  {label}: {value} [present]" if value else f"  {label}: [unknown - not recorded]"


def format_person_report(db: Session, source_system: str, source_record_id: str) -> str:
    person = db.scalars(select(Person).where(
        Person.source_system == source_system, Person.source_record_id == source_record_id)).first()
    if person is None:
        raise LookupError(f"No person '{source_record_id}' in source '{source_system}'")

    encounter_count = db.scalar(
        select(func.count()).select_from(Encounter).where(Encounter.person_id == person.person_id))
    lines = [
        f"Person {source_record_id} ({person.person_id})",
        f"  source: {source_system}",
        "",
        "Profile fields:",
        _field("date_of_birth", person.date_of_birth),
        _field("preferred_language", person.preferred_language),
        _field("area_code", person.area_code),
        f"  family_history_state: {person.family_history_state.value}",
        f"  encounters on file: {encounter_count}",
    ]

    stored_for_source = db.scalar(select(func.count()).select_from(DataQualityFinding)
                                  .where(DataQualityFinding.source_system == source_system))
    if not stored_for_source:
        lines += ["", "No findings are stored for this source yet. Run: python -m app.cli quality-check"]
        return "\n".join(lines)

    findings = sorted(
        db.scalars(select(DataQualityFinding).where(DataQualityFinding.person_id == person.person_id)),
        key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_code, f.field_name, str(f.subject_id)),
    )
    if not findings:
        lines += ["", "No findings. Every checked field is complete and consistent."]
    else:
        first = findings[0]
        lines += ["", f"Findings (evaluated on {first.evaluated_on}, rules {first.rule_version}):"]
        for f in findings:
            state = f.field_state.value if f.field_state else "conflict"
            lines.append(f"  [{f.severity.value}] {f.rule_code} {f.field_name} ({state}) on {f.subject_table}: {f.message}")
    return "\n".join(lines)