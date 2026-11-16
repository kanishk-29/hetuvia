import uuid
from dataclasses import dataclass
from datetime import date

from app.db.enums import CareGapOutcome, PersonStatus, ScreeningStatus


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    version: str
    title: str
    service_type: str
    status: str
    min_age_years: int
    max_age_years: int
    interval_days: int
    lead_days: int
    grace_days: int
    exclusions: tuple[str, ...]
    effective_from: date
    effective_to: date | None
    source: str


@dataclass(frozen=True)
class ServiceEvent:
    service_type: str
    result_status: ScreeningStatus
    completed_on: date | None


@dataclass(frozen=True)
class PersonCareFacts:
    person_id: uuid.UUID
    source_system: str
    date_of_birth: date | None
    status: PersonStatus
    services: tuple[ServiceEvent, ...] = ()


@dataclass(frozen=True)
class CareGapResult:
    rule_id: str
    rule_version: str
    service_type: str
    outcome: CareGapOutcome
    evaluated_on: date
    age_years: int | None
    due_date: date | None
    last_completed_on: date | None
    message: str
    evidence: dict