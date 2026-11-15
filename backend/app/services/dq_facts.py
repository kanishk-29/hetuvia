"""Plain, read-only snapshots of what the rules inspect. No database objects leak into the rules."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.db.enums import DataState, ScreeningStatus, Severity

RULE_VERSION = "demo-1"


@dataclass(frozen=True)
class EncounterFact:
    id: uuid.UUID
    encounter_date: date


@dataclass(frozen=True)
class ObservationFact:
    id: uuid.UUID
    observation_type: str
    value_state: DataState
    observed_at: datetime | None
    encounter_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ScreeningFact:
    id: uuid.UUID
    screening_type: str
    due_date: date | None
    result_status: ScreeningStatus
    completed_on: date | None


@dataclass(frozen=True)
class PersonFacts:
    person_id: uuid.UUID
    source_system: str
    date_of_birth: date | None
    preferred_language: str | None
    area_code: str | None
    family_history_state: DataState
    family_history_entries: int = 0
    encounters: tuple[EncounterFact, ...] = ()
    observations: tuple[ObservationFact, ...] = ()
    screenings: tuple[ScreeningFact, ...] = ()


@dataclass(frozen=True)
class EvaluationContext:
    evaluated_on: date
    stale_after_days: int = 730  # a demonstration parameter, not a clinical threshold


@dataclass(frozen=True)
class FindingDraft:
    rule_code: str
    severity: Severity
    subject_table: str
    subject_id: uuid.UUID
    field_name: str
    field_state: DataState | None  # None for contradictions, which are not gaps
    message: str