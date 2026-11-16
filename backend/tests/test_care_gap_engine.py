import uuid
from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.db.enums import CareGapOutcome as C
from app.db.enums import PersonStatus, ScreeningStatus
from app.services.care_gap_engine import evaluate, evaluate_person
from app.services.care_gap_types import PersonCareFacts, RuleDefinition, ServiceEvent

EVAL = date(2026, 11, 1)
ADULT = "demo_adult_screening"
CHILD = "demo_well_child_visit"

ADULT_RULE = RuleDefinition(
    rule_id="T-ADULT", version="1", title="Test adult screening", service_type=ADULT,
    status="demonstration", min_age_years=30, max_age_years=74, interval_days=730,
    lead_days=60, grace_days=30, exclusions=("inactive_person",),
    effective_from=date(2021, 1, 1), effective_to=None, source="test rule, not a guideline",
)
CHILD_RULE = replace(ADULT_RULE, rule_id="T-CHILD", service_type=CHILD,
                     min_age_years=0, max_age_years=17, interval_days=365)


def person(born=date(1980, 1, 1), status=PersonStatus.ACTIVE, services=()):
    return PersonCareFacts(uuid.uuid4(), "test", born, status, tuple(services))


def done(on, service=ADULT):
    return ServiceEvent(service, ScreeningStatus.COMPLETED, on)


def test_never_completed_adult_is_overdue():
    result = evaluate(person(), ADULT_RULE, EVAL)
    assert result.outcome == C.OVERDUE
    assert result.due_date == date(2021, 1, 1)
    assert result.last_completed_on is None
    assert result.age_years == 46


def test_recent_completion_is_up_to_date():
    assert evaluate(person(services=[done(date(2026, 3, 1))]), ADULT_RULE, EVAL).outcome == C.UP_TO_DATE


def test_old_completion_is_overdue_with_the_computed_due_date():
    last = date(2023, 1, 1)
    result = evaluate(person(services=[done(last)]), ADULT_RULE, EVAL)
    assert result.outcome == C.OVERDUE
    assert result.due_date == last + timedelta(days=730)
    assert result.last_completed_on == last


@pytest.mark.parametrize("days_until_due, expected", [
    (60, C.DUE), (61, C.UP_TO_DATE), (-30, C.DUE), (-31, C.OVERDUE),
])
def test_window_boundaries(days_until_due, expected):
    next_due = EVAL + timedelta(days=days_until_due)
    last = next_due - timedelta(days=730)
    assert evaluate(person(services=[done(last)]), ADULT_RULE, EVAL).outcome == expected


def test_a_completed_service_closes_the_gap():
    before = evaluate(person(services=[done(date(2023, 1, 1))]), ADULT_RULE, EVAL)
    after = evaluate(person(services=[done(date(2023, 1, 1)), done(date(2026, 10, 1))]), ADULT_RULE, EVAL)
    assert before.outcome == C.OVERDUE
    assert after.outcome == C.UP_TO_DATE


def test_missing_birth_date_is_not_assessable_never_a_gap():
    result = evaluate(person(born=None), ADULT_RULE, EVAL)
    assert result.outcome == C.NOT_ASSESSABLE
    assert "date of birth" in result.message


@pytest.mark.parametrize("born, eligible", [
    (date(1996, 11, 2), False),  # 29 years old
    (date(1996, 11, 1), True),   # turns 30 today
    (date(1952, 11, 1), True),   # 74
    (date(1951, 11, 1), False),  # 75
])
def test_age_edges(born, eligible):
    assert (evaluate(person(born=born), ADULT_RULE, EVAL).outcome != C.NOT_ELIGIBLE) == eligible


def test_each_rule_applies_only_to_its_own_ages():
    child, adult = person(born=date(2015, 3, 1)), person(born=date(1980, 1, 1))
    assert evaluate(child, ADULT_RULE, EVAL).outcome == C.NOT_ELIGIBLE
    assert evaluate(adult, CHILD_RULE, EVAL).outcome == C.NOT_ELIGIBLE
    assert evaluate(child, CHILD_RULE, EVAL).outcome != C.NOT_ELIGIBLE


def test_inactive_person_is_excluded():
    result = evaluate(person(status=PersonStatus.INACTIVE), ADULT_RULE, EVAL)
    assert result.outcome == C.NOT_ELIGIBLE
    assert "inactive" in result.evidence["reason"]


def test_completed_without_a_date_is_not_assessable():
    undated = ServiceEvent(ADULT, ScreeningStatus.COMPLETED, None)
    result = evaluate(person(services=[undated]), ADULT_RULE, EVAL)
    assert result.outcome == C.NOT_ASSESSABLE
    assert result.evidence["undated_completed_count"] == 1


def test_an_undated_completion_only_matters_when_it_could_change_the_verdict():
    undated = ServiceEvent(ADULT, ScreeningStatus.COMPLETED, None)
    recent = evaluate(person(services=[done(date(2026, 3, 1)), undated]), ADULT_RULE, EVAL)
    old = evaluate(person(services=[done(date(2023, 1, 1)), undated]), ADULT_RULE, EVAL)
    assert recent.outcome == C.UP_TO_DATE
    assert old.outcome == C.NOT_ASSESSABLE


def test_missed_declined_and_pending_do_not_count_as_completed():
    services = [ServiceEvent(ADULT, s, None)
                for s in (ScreeningStatus.MISSED, ScreeningStatus.DECLINED, ScreeningStatus.PENDING)]
    assert evaluate(person(services=services), ADULT_RULE, EVAL).outcome == C.OVERDUE


def test_other_service_types_do_not_count():
    assert evaluate(person(services=[done(date(2026, 3, 1), CHILD)]), ADULT_RULE, EVAL).outcome == C.OVERDUE


def test_a_completion_dated_in_the_future_is_ignored():
    result = evaluate(person(services=[done(date(2027, 1, 1))]), ADULT_RULE, EVAL)
    assert result.outcome == C.OVERDUE
    assert result.evidence["ignored_future_completions"] == 1


def test_same_input_gives_same_verdict():
    facts = person(services=[done(date(2023, 1, 1))])
    assert evaluate(facts, ADULT_RULE, EVAL) == evaluate(facts, ADULT_RULE, EVAL)
    assert evaluate_person(facts, [ADULT_RULE, CHILD_RULE], EVAL) == evaluate_person(facts, [CHILD_RULE, ADULT_RULE], EVAL)


def test_rules_not_yet_in_effect_are_skipped():
    later = replace(ADULT_RULE, effective_from=date(2027, 1, 1))
    assert evaluate_person(person(), [later], EVAL) == []


def test_evidence_names_the_rule_and_the_facts_used():
    result = evaluate(person(services=[done(date(2026, 3, 1))]), ADULT_RULE, EVAL)
    assert result.evidence["rule_id"] == "T-ADULT"
    assert result.evidence["rule_version"] == "1"
    assert result.evidence["rule_status"] == "demonstration"
    assert result.evidence["last_completed_on"] == "2026-03-01"
    assert "next_due_date" in result.evidence