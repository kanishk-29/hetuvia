import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.enums import DataState, EncounterStatus, RelationshipType
from app.db.models import Encounter, FamilyRelationship, Observation, Person
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