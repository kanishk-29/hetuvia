from datetime import date

from app.db.enums import DataState, Severity
from app.db.models import DataQualityFinding, Person
from app.services.seed import reset_source


def add_person_with_finding(db):
    person = Person(source_system="dq_test")
    db.add(person)
    db.flush()
    db.add(DataQualityFinding(
        person_id=person.person_id, source_system="dq_test", subject_table="people",
        subject_id=person.person_id, field_name="date_of_birth", rule_code="DQ-001",
        rule_version="demo-1", severity=Severity.WARNING, field_state=DataState.UNKNOWN,
        message="Date of birth is not recorded.", evaluated_on=date(2026, 11, 1),
    ))
    db.flush()
    return person


def test_finding_keeps_severity_and_state(db):
    person = add_person_with_finding(db)
    saved = db.query(DataQualityFinding).filter(DataQualityFinding.person_id == person.person_id).one()
    assert saved.severity == Severity.WARNING
    assert saved.field_state == DataState.UNKNOWN


def test_reset_removes_findings_before_their_people(db):
    add_person_with_finding(db)
    reset_source(db, "dq_test")
    assert db.query(Person).filter(Person.source_system == "dq_test").count() == 0
    assert db.query(DataQualityFinding).filter(DataQualityFinding.source_system == "dq_test").count() == 0