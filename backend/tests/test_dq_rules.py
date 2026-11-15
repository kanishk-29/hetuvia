import uuid
from datetime import UTC, date, datetime

import pytest

from app.db.enums import DataState, ScreeningStatus, Severity
from app.services.dq_facts import (
    EncounterFact,
    EvaluationContext,
    ObservationFact,
    PersonFacts,
    ScreeningFact,
)
from app.services.dq_rules import evaluate_person

CTX = EvaluationContext(evaluated_on=date(2026, 11, 1))
ENCOUNTER_ID = uuid.uuid4()


def person(**changes):
    base = dict(
        person_id=uuid.uuid4(), source_system="test", date_of_birth=date(1990, 1, 1),
        preferred_language="en", area_code="AREA-A",
        family_history_state=DataState.EXPLICITLY_ABSENT, family_history_entries=0,
        encounters=(EncounterFact(ENCOUNTER_ID, date(2026, 5, 1)),),
        observations=(), screenings=(),
    )
    base.update(changes)
    return PersonFacts(**base)


def obs(kind, state, when=None, encounter_id=None):
    return ObservationFact(uuid.uuid4(), kind, state, when, encounter_id)


def screening(status, due=date(2026, 1, 1), completed=None):
    return ScreeningFact(uuid.uuid4(), "demo_adult_screening", due, status, completed)


def of_rule(findings, code):
    return [f for f in findings if f.rule_code == code]


def test_complete_record_has_no_findings():
    assert evaluate_person(person(), CTX) == []


def test_missing_birth_date_is_flagged_as_unknown():
    findings = evaluate_person(person(date_of_birth=None), CTX)
    assert len(findings) == 1
    assert (findings[0].rule_code, findings[0].severity, findings[0].field_state) == (
        "DQ-001", Severity.WARNING, DataState.UNKNOWN)


def test_missing_language_is_info_only():
    findings = evaluate_person(person(preferred_language=None), CTX)
    assert [(f.rule_code, f.field_name, f.severity) for f in findings] == [
        ("DQ-002", "preferred_language", Severity.INFO)]


@pytest.mark.parametrize("state", [DataState.UNKNOWN, DataState.NOT_COLLECTED, DataState.STALE])
def test_family_history_gap_keeps_its_state(state):
    findings = evaluate_person(person(family_history_state=state), CTX)
    assert [(f.rule_code, f.field_state) for f in findings] == [("DQ-003", state)]


def test_explicitly_absent_family_history_is_not_a_gap():
    assert of_rule(evaluate_person(person(), CTX), "DQ-003") == []


def test_present_family_history_without_entries_is_a_contradiction():
    findings = evaluate_person(person(family_history_state=DataState.PRESENT), CTX)
    assert [(f.rule_code, f.severity) for f in findings] == [("DQ-004", Severity.ERROR)]


def test_absent_family_history_with_entries_is_a_contradiction():
    findings = evaluate_person(person(family_history_entries=1), CTX)
    assert [f.rule_code for f in findings] == ["DQ-004"]


def test_unknown_and_not_collected_measurements_are_flagged():
    facts = person(observations=(
        obs("weight", DataState.UNKNOWN), obs("height", DataState.NOT_COLLECTED)))
    found = of_rule(evaluate_person(facts, CTX), "DQ-005")
    assert sorted((f.field_name, f.field_state) for f in found) == [
        ("height", DataState.NOT_COLLECTED), ("weight", DataState.UNKNOWN)]


def test_a_measurement_with_a_value_is_not_flagged_as_missing():
    facts = person(observations=(obs("weight", DataState.PRESENT),))
    assert of_rule(evaluate_person(facts, CTX), "DQ-005") == []


def test_old_blood_pressure_is_stale_and_recent_is_not():
    old = obs("systolic_blood_pressure", DataState.PRESENT, datetime(2023, 1, 1, 9, tzinfo=UTC))
    recent = obs("systolic_blood_pressure", DataState.PRESENT, datetime(2026, 5, 1, 9, tzinfo=UTC))
    stale = of_rule(evaluate_person(person(observations=(old,)), CTX), "DQ-006")
    assert [f.field_state for f in stale] == [DataState.STALE]
    assert of_rule(evaluate_person(person(observations=(recent,)), CTX), "DQ-006") == []


def test_staleness_looks_at_the_latest_reading_only():
    old = obs("systolic_blood_pressure", DataState.PRESENT, datetime(2023, 1, 1, 9, tzinfo=UTC))
    recent = obs("systolic_blood_pressure", DataState.PRESENT, datetime(2026, 5, 1, 9, tzinfo=UTC))
    assert of_rule(evaluate_person(person(observations=(old, recent)), CTX), "DQ-006") == []


def test_completed_screening_without_a_date_is_flagged():
    flagged = person(screenings=(screening(ScreeningStatus.COMPLETED, completed=None),))
    fine = person(screenings=(screening(ScreeningStatus.COMPLETED, completed=date(2026, 2, 1)),
                              screening(ScreeningStatus.PENDING, completed=None)))
    assert [f.rule_code for f in evaluate_person(flagged, CTX)] == ["DQ-007"]
    assert evaluate_person(fine, CTX) == []


def test_screening_without_a_due_date_is_info():
    facts = person(screenings=(screening(ScreeningStatus.PENDING, due=None),))
    findings = evaluate_person(facts, CTX)
    assert [(f.rule_code, f.severity) for f in findings] == [("DQ-008", Severity.INFO)]


def test_person_without_encounters_is_flagged():
    findings = evaluate_person(person(encounters=()), CTX)
    assert [f.rule_code for f in findings] == ["DQ-009"]


def test_event_before_birth_is_a_conflict_only_when_birth_is_known():
    early = EncounterFact(uuid.uuid4(), date(1980, 1, 1))
    assert [f.rule_code for f in evaluate_person(person(encounters=(early,)), CTX)] == ["DQ-010"]
    no_birth = evaluate_person(person(encounters=(early,), date_of_birth=None), CTX)
    assert of_rule(no_birth, "DQ-010") == []


def test_observation_date_must_match_its_encounter():
    mismatch = obs("weight", DataState.PRESENT, datetime(2026, 5, 2, 9, tzinfo=UTC), ENCOUNTER_ID)
    findings = evaluate_person(person(observations=(mismatch,)), CTX)
    assert [f.rule_code for f in findings] == ["DQ-010"]


def test_same_input_gives_same_findings():
    facts = person(date_of_birth=None, preferred_language=None,
                   observations=(obs("weight", DataState.UNKNOWN),))
    assert evaluate_person(facts, CTX) == evaluate_person(facts, CTX)