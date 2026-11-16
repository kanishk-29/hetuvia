from datetime import date

from sqlalchemy import func, select

from app.db.enums import CareGapOutcome
from app.db.models import CareGapFinding, GuidelineRule, Person
from app.services.rule_loader import load_rules, sync_rules
from app.services.seed import reset_source


def add_person_with_finding(db):
    person = Person(source_system="cg_test")
    db.add(person)
    db.flush()
    db.add(CareGapFinding(
        person_id=person.person_id, source_system="cg_test", rule_id="DEMO-X", rule_version="1",
        service_type="demo_adult_screening", outcome=CareGapOutcome.OVERDUE,
        evaluated_on=date(2026, 11, 1), age_years=46, due_date=date(2021, 1, 1),
        last_completed_on=None, message="overdue", evidence={"basis": "never_completed"},
    ))
    db.flush()
    return person


def test_syncing_rules_twice_does_not_duplicate_them(db):
    rules = load_rules()
    sync_rules(db, rules)
    sync_rules(db, rules)
    ids = [rule.rule_id for rule in rules]
    count = db.scalar(select(func.count()).select_from(GuidelineRule).where(GuidelineRule.rule_id.in_(ids)))
    assert count == len(rules)


def test_finding_keeps_outcome_and_evidence(db):
    person = add_person_with_finding(db)
    saved = db.scalars(select(CareGapFinding).where(CareGapFinding.person_id == person.person_id)).one()
    assert saved.outcome == CareGapOutcome.OVERDUE
    assert saved.evidence["basis"] == "never_completed"


def test_reset_removes_care_gap_findings_before_their_people(db):
    add_person_with_finding(db)
    reset_source(db, "cg_test")
    assert db.query(Person).filter(Person.source_system == "cg_test").count() == 0
    assert db.query(CareGapFinding).filter(CareGapFinding.source_system == "cg_test").count() == 0