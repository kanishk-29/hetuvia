"""Run the care-gap rules over a stored population and keep the verdicts that need attention."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.enums import CareGapOutcome
from app.db.models import CareGapFinding, Person, ScreeningEvent
from app.services.care_gap_engine import evaluate_person
from app.services.care_gap_types import PersonCareFacts, RuleDefinition, ServiceEvent
from app.services.rule_loader import load_rules, sync_rules

# Up-to-date and not-eligible verdicts are counted but not stored: nothing needs attention.
STORED_OUTCOMES = (CareGapOutcome.OVERDUE, CareGapOutcome.DUE, CareGapOutcome.NOT_ASSESSABLE)


@dataclass
class CareGapSummary:
    source_system: str
    evaluated_on: date
    people: int = 0
    evaluations: int = 0
    stored_findings: int = 0
    by_rule_outcome: dict[str, dict[str, int]] = field(default_factory=dict)


def load_care_facts(db: Session, source_system: str) -> list[PersonCareFacts]:
    people = db.scalars(
        select(Person).where(Person.source_system == source_system).order_by(Person.person_id)
    ).all()
    services = defaultdict(list)
    for s in db.scalars(select(ScreeningEvent).where(ScreeningEvent.source_system == source_system)
                        .order_by(ScreeningEvent.id)):
        services[s.person_id].append(ServiceEvent(s.screening_type, s.result_status, s.completed_on))
    return [
        PersonCareFacts(p.person_id, source_system, p.date_of_birth, p.status, tuple(services[p.person_id]))
        for p in people
    ]


def run_care_gap_check(
    db: Session, source_system: str, evaluated_on: date, rules: list[RuleDefinition] | None = None
) -> CareGapSummary:
    """Replace this source's care-gap findings with a fresh evaluation. Flushes; the caller commits."""
    rules = rules if rules is not None else load_rules()
    sync_rules(db, rules)
    db.execute(delete(CareGapFinding).where(CareGapFinding.source_system == source_system))

    summary = CareGapSummary(source_system=source_system, evaluated_on=evaluated_on)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for facts in load_care_facts(db, source_system):
        summary.people += 1
        for result in evaluate_person(facts, rules, evaluated_on):
            summary.evaluations += 1
            counts[result.rule_id][result.outcome.value] += 1
            if result.outcome in STORED_OUTCOMES:
                db.add(CareGapFinding(
                    person_id=facts.person_id, source_system=source_system,
                    rule_id=result.rule_id, rule_version=result.rule_version,
                    service_type=result.service_type, outcome=result.outcome,
                    evaluated_on=evaluated_on, age_years=result.age_years,
                    due_date=result.due_date, last_completed_on=result.last_completed_on,
                    message=result.message, evidence=result.evidence,
                ))
                summary.stored_findings += 1
    db.flush()
    summary.by_rule_outcome = {rule: dict(outcomes) for rule, outcomes in sorted(counts.items())}
    return summary