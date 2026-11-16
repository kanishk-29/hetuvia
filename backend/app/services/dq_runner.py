"""Run the data-quality rules over a stored population and keep the findings."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.enums import ConditionContext
from app.db.models import (
    Condition,
    DataQualityFinding,
    Encounter,
    Observation,
    Person,
    ScreeningEvent,
)
from app.services.dq_facts import (
    RULE_VERSION,
    EncounterFact,
    EvaluationContext,
    ObservationFact,
    PersonFacts,
    ScreeningFact,
)
from app.services.dq_rules import evaluate_person


@dataclass
class QualitySummary:
    source_system: str
    evaluated_on: date
    people: int = 0
    people_with_findings: int = 0
    findings: int = 0
    by_rule: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)


def load_person_facts(db: Session, source_system: str) -> list[PersonFacts]:
    """Read one source's records into plain snapshots, in a stable order."""
    people = db.scalars(
        select(Person).where(Person.source_system == source_system).order_by(Person.person_id)
    ).all()

    encounters = defaultdict(list)
    for e in db.scalars(select(Encounter).where(Encounter.source_system == source_system)
                        .order_by(Encounter.encounter_date, Encounter.id)):
        encounters[e.person_id].append(EncounterFact(e.id, e.encounter_date))

    observations = defaultdict(list)
    for o in db.scalars(select(Observation).where(Observation.source_system == source_system)
                        .order_by(Observation.id)):
        observations[o.person_id].append(
            ObservationFact(o.id, o.observation_type, o.value_state, o.observed_at, o.encounter_id))

    screenings = defaultdict(list)
    for s in db.scalars(select(ScreeningEvent).where(ScreeningEvent.source_system == source_system)
                        .order_by(ScreeningEvent.id)):
        screenings[s.person_id].append(
            ScreeningFact(s.id, s.screening_type, s.due_date, s.result_status, s.completed_on))

    entries = dict(db.execute(
        select(Condition.person_id, func.count())
        .where(Condition.source_system == source_system,
               Condition.context == ConditionContext.FAMILY_HISTORY)
        .group_by(Condition.person_id)
    ).all())

    return [
        PersonFacts(
            person_id=p.person_id, source_system=source_system,
            date_of_birth=p.date_of_birth, preferred_language=p.preferred_language,
            area_code=p.area_code, family_history_state=p.family_history_state,
            family_history_entries=entries.get(p.person_id, 0),
            encounters=tuple(encounters[p.person_id]),
            observations=tuple(observations[p.person_id]),
            screenings=tuple(screenings[p.person_id]),
        )
        for p in people
    ]


def run_quality_check(db: Session, source_system: str, evaluated_on: date) -> QualitySummary:
    """Replace this source's findings with a fresh evaluation. Flushes; the caller commits."""
    ctx = EvaluationContext(evaluated_on=evaluated_on)
    db.execute(delete(DataQualityFinding).where(DataQualityFinding.source_system == source_system))

    summary = QualitySummary(source_system=source_system, evaluated_on=evaluated_on)
    by_rule: Counter = Counter()
    by_severity: Counter = Counter()
    for facts in load_person_facts(db, source_system):
        summary.people += 1
        drafts = evaluate_person(facts, ctx)
        if drafts:
            summary.people_with_findings += 1
        for d in drafts:
            db.add(DataQualityFinding(
                person_id=facts.person_id, source_system=source_system,
                subject_table=d.subject_table, subject_id=d.subject_id, field_name=d.field_name,
                rule_code=d.rule_code, rule_version=RULE_VERSION, severity=d.severity,
                field_state=d.field_state, message=d.message, evaluated_on=evaluated_on,
            ))
            by_rule[d.rule_code] += 1
            by_severity[d.severity.value] += 1
    db.flush()

    summary.findings = sum(by_rule.values())
    summary.by_rule = dict(sorted(by_rule.items()))
    summary.by_severity = dict(by_severity)
    return summary