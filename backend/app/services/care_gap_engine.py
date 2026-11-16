"""The care-gap judge. Pure functions: one person's facts and one rule in, one verdict out.

No database, no side effects. Missing information is never converted into a gap or into 'fine':
it becomes NOT_ASSESSABLE, which is an information gap and stays separate from care gaps.
"""

from datetime import date, timedelta

from app.db.enums import CareGapOutcome, PersonStatus, ScreeningStatus
from app.services.care_gap_types import CareGapResult, PersonCareFacts, RuleDefinition

C = CareGapOutcome


def age_in_years(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def add_years(born: date, years: int) -> date:
    try:
        return born.replace(year=born.year + years)
    except ValueError:  # 29 February in a non-leap year
        return born.replace(year=born.year + years, month=3, day=1)


def is_in_effect(rule: RuleDefinition, on: date) -> bool:
    return rule.effective_from <= on and (rule.effective_to is None or on <= rule.effective_to)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def evaluate(person: PersonCareFacts, rule: RuleDefinition, evaluated_on: date) -> CareGapResult:
    tag = f"[{rule.rule_id} v{rule.version}, {rule.status}] {rule.title}: "
    evidence: dict = {
        "rule_id": rule.rule_id, "rule_version": rule.version, "rule_status": rule.status,
        "rule_source": rule.source, "evaluated_on": _iso(evaluated_on),
        "date_of_birth": _iso(person.date_of_birth), "person_status": person.status.value,
    }
    state = {"age": None, "due": None, "last": None}

    def done(outcome: CareGapOutcome, message: str) -> CareGapResult:
        return CareGapResult(rule.rule_id, rule.version, rule.service_type, outcome, evaluated_on,
                             state["age"], state["due"], state["last"], tag + message, dict(evidence))

    if not is_in_effect(rule, evaluated_on):
        evidence["reason"] = "rule not in effect on the evaluation date"
        return done(C.NOT_ELIGIBLE, "rule is not in effect on the evaluation date.")
    if "inactive_person" in rule.exclusions and person.status == PersonStatus.INACTIVE:
        evidence["reason"] = "excluded: inactive person"
        return done(C.NOT_ELIGIBLE, "person is inactive, so the rule does not apply.")
    if person.date_of_birth is None:
        evidence["reason"] = "date_of_birth is missing"
        return done(C.NOT_ASSESSABLE, "cannot assess because the date of birth is not recorded.")

    age = age_in_years(person.date_of_birth, evaluated_on)
    state["age"] = age
    evidence["age_years"] = age
    if not rule.min_age_years <= age <= rule.max_age_years:
        evidence["reason"] = f"age {age} is outside {rule.min_age_years}-{rule.max_age_years}"
        return done(C.NOT_ELIGIBLE, f"age {age} is outside the eligible range.")

    matching = [s for s in person.services
                if s.service_type == rule.service_type and s.result_status == ScreeningStatus.COMPLETED]
    dated = sorted(s.completed_on for s in matching
                   if s.completed_on is not None and s.completed_on <= evaluated_on)
    ignored_future = sum(1 for s in matching if s.completed_on is not None and s.completed_on > evaluated_on)
    undated = sum(1 for s in matching if s.completed_on is None)
    evidence["undated_completed_count"] = undated
    evidence["ignored_future_completions"] = ignored_future

    if dated:
        last = dated[-1]
        due = last + timedelta(days=rule.interval_days)
        evidence["basis"] = "last_completion"
    else:
        if undated:
            evidence["reason"] = "a completed service has no completion date"
            return done(C.NOT_ASSESSABLE, "a completed service has no date, so the next due date cannot be computed.")
        last = None
        due = max(add_years(person.date_of_birth, rule.min_age_years), rule.effective_from)
        evidence["basis"] = "never_completed: due since the person became eligible"
    state["last"], state["due"] = last, due
    evidence["last_completed_on"] = _iso(last)
    evidence["next_due_date"] = _iso(due)

    if evaluated_on > due + timedelta(days=rule.grace_days):
        outcome = C.OVERDUE
    elif evaluated_on >= due - timedelta(days=rule.lead_days):
        outcome = C.DUE
    else:
        outcome = C.UP_TO_DATE

    if outcome in (C.OVERDUE, C.DUE) and undated:
        evidence["reason"] = "a completed service without a date might be more recent"
        return done(C.NOT_ASSESSABLE, "a completed service has no date and might be more recent, so this is not judged as a gap.")

    last_text = last.isoformat() if last else "never"
    if outcome == C.OVERDUE:
        return done(outcome, f"overdue. Next due {due}, grace period ended {due + timedelta(days=rule.grace_days)}, last completed {last_text}.")
    if outcome == C.DUE:
        return done(outcome, f"due now. Next due {due}, last completed {last_text}.")
    return done(outcome, f"up to date. Next due {due}, last completed {last_text}.")


def evaluate_person(person: PersonCareFacts, rules: list[RuleDefinition], evaluated_on: date) -> list[CareGapResult]:
    in_effect = sorted((r for r in rules if is_in_effect(r, evaluated_on)), key=lambda r: (r.rule_id, r.version))
    return [evaluate(person, rule, evaluated_on) for rule in in_effect]