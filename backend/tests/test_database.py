import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.enums import (
   ConditionContext,
    DataState,
    EncounterStatus,
    RelationshipType,
    ScreeningStatus,
)
from app.db.models import Condition, Encounter, FamilyRelationship, Observation, Person, ScreeningEvent

from app.repositories.people import PeopleRepository


def make_person() -> Person:
    return Person(date_of_birth=date(2015, 3, 1), source_system="synthetic")


def test_insert_and_read_person(db):
    repo = PeopleRepository(db)
    person = repo.add(make_person())
    found = repo.get(person.person_id)
    assert found is not None
    assert found.date_of_birth == date(2015, 3, 1)


def test_encounter_for_missing_person_is_rejected(db):
    db.add(Encounter(
        person_id=uuid.uuid4(), encounter_type="well_child_visit",
        encounter_date=date(2026, 1, 1), status=EncounterStatus.COMPLETED,
        source_system="synthetic",
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_person_cannot_be_their_own_relative(db):
    person = PeopleRepository(db).add(make_person())
    db.add(FamilyRelationship(
        person_id=person.person_id, related_person_id=person.person_id,
        relationship_type=RelationshipType.PARENT, source_system="synthetic",
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_unknown_observation_stores_no_value(db):
    person = PeopleRepository(db).add(make_person())
    db.add(Observation(
        person_id=person.person_id, observation_type="weight",
        value_state=DataState.UNKNOWN, source_system="synthetic",
    ))
    db.flush()
    saved = db.query(Observation).one()
    assert saved.value_numeric is None
    assert saved.value_state == DataState.UNKNOWN


def test_present_observation_requires_a_value(db):
    person = PeopleRepository(db).add(make_person())
    db.add(Observation(
        person_id=person.person_id, observation_type="weight",
        value_state=DataState.PRESENT, source_system="synthetic",
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_family_history_defaults_to_not_collected(db):
    person = PeopleRepository(db).add(make_person())
    assert person.family_history_state == DataState.NOT_COLLECTED


def test_completed_screening_may_lack_a_date(db):
    person = PeopleRepository(db).add(make_person())
    db.add(ScreeningEvent(
        person_id=person.person_id, screening_type="demo_adult_screening",
        result_status=ScreeningStatus.COMPLETED, completed_on=None,
        source_system="synthetic",
    ))
    db.flush()  # allowed: the gap is reported later, not forbidden here


def test_completion_date_requires_completed_status(db):
    person = PeopleRepository(db).add(make_person())
    db.add(ScreeningEvent(
        person_id=person.person_id, screening_type="demo_adult_screening",
        result_status=ScreeningStatus.PENDING, completed_on=date(2026, 1, 1),
        source_system="synthetic",
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_personal_condition_cannot_name_a_relative(db):
    repo = PeopleRepository(db)
    person, other = repo.add(make_person()), repo.add(make_person())
    db.add(Condition(
        person_id=person.person_id, related_person_id=other.person_id,
        context=ConditionContext.PERSONAL, condition_code="DEMO-C01",
        condition_label="Demo condition", source_system="synthetic",
    ))
    with pytest.raises(IntegrityError):
        db.flush()