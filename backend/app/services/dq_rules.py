"""Data-quality rules. Pure functions: facts in, findings out. No database, no side effects.

These are DEMONSTRATION rules about the completeness and consistency of records. They say nothing
about anyone's health. A missing value is reported as a gap and is never turned into a negative value.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from app.db.enums import DataState, ScreeningStatus, Severity
from app.services.dq_facts import EvaluationContext, FindingDraft, PersonFacts

STALENESS_APPLIES_TO = ("systolic_blood_pressure",)

RULE_TITLES = {
    "DQ-001": "Date of birth missing",
    "DQ-002": "Preferred language or area missing",
    "DQ-003": "Family history is a gap (unknown, not collected or stale)",
    "DQ-004": "Family history state contradicts its entries",
    "DQ-005": "Measurement recorded without a value",
    "DQ-006": "Latest reading is stale",
    "DQ-007": "Screening completed but completion date missing",
    "DQ-008": "Screening has no due date",
    "DQ-009": "No encounters on file",
    "DQ-010": "Conflicting dates",
}

Rule = Callable[[PersonFacts, EvaluationContext], list[FindingDraft]]


def _utc_date(moment: datetime) -> date:
    return moment.date() if moment.tzinfo is None else moment.astimezone(UTC).date()


def _draft(code, severity, table, subject_id, field_name, state, message) -> FindingDraft:
    return FindingDraft(code, severity, table, subject_id, field_name, state, message)


def dq_001_birth_date_missing(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    if person.date_of_birth is not None:
        return []
    return [_draft("DQ-001", Severity.WARNING, "people", person.person_id, "date_of_birth",
                   DataState.UNKNOWN, "Date of birth is not recorded; age-based rules cannot be applied.")]


def dq_002_language_or_area_missing(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    found = []
    for name, value in (("preferred_language", person.preferred_language), ("area_code", person.area_code)):
        if not value:
            found.append(_draft("DQ-002", Severity.INFO, "people", person.person_id, name,
                                DataState.UNKNOWN, f"{name} is not recorded."))
    return found


def dq_003_family_history_gap(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    state = person.family_history_state
    if state not in (DataState.UNKNOWN, DataState.NOT_COLLECTED, DataState.STALE):
        return []
    return [_draft("DQ-003", Severity.WARNING, "people", person.person_id, "family_history_state", state,
                   f"Family history is '{state.value}'. This is a gap in information, "
                   "not evidence of 'no family history'.")]


def dq_004_family_history_inconsistent(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    state, entries = person.family_history_state, person.family_history_entries
    says_present_but_empty = state == DataState.PRESENT and entries == 0
    says_none_but_has_entries = entries > 0 and state in (
        DataState.EXPLICITLY_ABSENT, DataState.UNKNOWN, DataState.NOT_COLLECTED, DataState.NOT_APPLICABLE)
    if not (says_present_but_empty or says_none_but_has_entries):
        return []
    return [_draft("DQ-004", Severity.ERROR, "people", person.person_id, "family_history_state", None,
                   f"Family history state is '{state.value}' but {entries} family-history entries exist.")]


def dq_005_measurement_without_value(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    found = []
    for obs in person.observations:
        if obs.value_state in (DataState.UNKNOWN, DataState.NOT_COLLECTED):
            found.append(_draft("DQ-005", Severity.WARNING, "observations", obs.id, obs.observation_type,
                                obs.value_state,
                                f"{obs.observation_type} was recorded as '{obs.value_state.value}'; no value is available."))
    return found


def dq_006_stale_reading(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    limit = ctx.evaluated_on - timedelta(days=ctx.stale_after_days)
    found = []
    for kind in STALENESS_APPLIES_TO:
        readings = [o for o in person.observations
                    if o.observation_type == kind and o.value_state == DataState.PRESENT
                    and o.observed_at is not None]
        if not readings:
            continue
        latest = max(readings, key=lambda o: (o.observed_at, str(o.id)))
        if _utc_date(latest.observed_at) < limit:
            found.append(_draft("DQ-006", Severity.WARNING, "observations", latest.id, kind, DataState.STALE,
                                f"Latest {kind} reading is dated {_utc_date(latest.observed_at)}, "
                                f"older than {ctx.stale_after_days} days."))
    return found


def dq_007_completed_without_date(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    return [
        _draft("DQ-007", Severity.WARNING, "screening_events", s.id, "completed_on", DataState.UNKNOWN,
               f"{s.screening_type} is marked completed but has no completion date.")
        for s in person.screenings
        if s.result_status == ScreeningStatus.COMPLETED and s.completed_on is None
    ]


def dq_008_no_due_date(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    return [
        _draft("DQ-008", Severity.INFO, "screening_events", s.id, "due_date", DataState.UNKNOWN,
               f"{s.screening_type} has no due date recorded.")
        for s in person.screenings if s.due_date is None
    ]


def dq_009_no_encounters(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    if person.encounters:
        return []
    return [_draft("DQ-009", Severity.INFO, "people", person.person_id, "encounters", DataState.UNKNOWN,
                   "No encounter records are on file for this person.")]


def dq_010_conflicting_dates(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    found = []
    born = person.date_of_birth
    if born is not None:
        for e in person.encounters:
            if e.encounter_date < born:
                found.append(_draft("DQ-010", Severity.ERROR, "encounters", e.id, "encounter_date", None,
                                    f"Encounter date {e.encounter_date} is before the date of birth {born}."))
        for o in person.observations:
            if o.observed_at is not None and _utc_date(o.observed_at) < born:
                found.append(_draft("DQ-010", Severity.ERROR, "observations", o.id, "observed_at", None,
                                    f"Observation date {_utc_date(o.observed_at)} is before the date of birth {born}."))
        for s in person.screenings:
            for name, value in (("due_date", s.due_date), ("completed_on", s.completed_on)):
                if value is not None and value < born:
                    found.append(_draft("DQ-010", Severity.ERROR, "screening_events", s.id, name, None,
                                        f"Screening {name} {value} is before the date of birth {born}."))
    encounter_dates = {e.id: e.encounter_date for e in person.encounters}
    for o in person.observations:
        linked = encounter_dates.get(o.encounter_id)
        if linked is not None and o.observed_at is not None and _utc_date(o.observed_at) != linked:
            found.append(_draft("DQ-010", Severity.ERROR, "observations", o.id, "observed_at", None,
                                f"Observation date {_utc_date(o.observed_at)} differs from its encounter date {linked}."))
    return found


RULES: tuple[Rule, ...] = (
    dq_001_birth_date_missing, dq_002_language_or_area_missing, dq_003_family_history_gap,
    dq_004_family_history_inconsistent, dq_005_measurement_without_value, dq_006_stale_reading,
    dq_007_completed_without_date, dq_008_no_due_date, dq_009_no_encounters, dq_010_conflicting_dates,
)


def evaluate_person(person: PersonFacts, ctx: EvaluationContext) -> list[FindingDraft]:
    findings = [finding for rule in RULES for finding in rule(person, ctx)]
    return sorted(findings, key=lambda f: (f.rule_code, f.subject_table, str(f.subject_id), f.field_name))