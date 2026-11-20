import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.db.enums import (
    CareGapOutcome,
    DataState,
    OutreachPriority,
    PersonStatus,
    RecommendationKind,
    RecommendationStatus,
    Severity,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PersonOut(ORMModel):
    person_id: uuid.UUID
    source_system: str
    source_record_id: str | None
    date_of_birth: date | None
    sex_recorded: str | None
    preferred_language: str | None
    area_code: str | None
    status: PersonStatus
    family_history_state: DataState


class CareGapFindingOut(ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID
    source_system: str
    rule_id: str
    rule_version: str
    service_type: str
    outcome: CareGapOutcome
    evaluated_on: date
    age_years: int | None
    due_date: date | None
    last_completed_on: date | None
    message: str
    evidence: dict[str, object]


class DataQualityFindingOut(ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID
    source_system: str
    subject_table: str
    subject_id: uuid.UUID
    field_name: str
    rule_code: str
    rule_version: str
    severity: Severity
    field_state: DataState | None
    message: str
    evaluated_on: date


class RecommendationOut(ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID
    source_system: str
    kind: RecommendationKind
    pathway_code: str
    pathway_title: str
    rule_id: str
    rule_version: str | None
    priority: OutreachPriority
    priority_reasons: list[str]
    evidence: dict[str, object]
    uncertainty: str
    review_required_reason: str
    status: RecommendationStatus
    reviewer_name: str | None
    reviewer_note: str | None
    reviewed_at: datetime | None
    evaluated_on: date


class AuditEventOut(ORMModel):
    id: uuid.UUID
    occurred_at: datetime
    actor: str
    role: str
    action: str
    object_type: str
    object_id: uuid.UUID
    person_id: uuid.UUID | None
    detail: dict[str, object]


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class PersonPage(BaseModel):
    items: list[PersonOut]
    meta: PageMeta


class CareGapPage(BaseModel):
    items: list[CareGapFindingOut]
    meta: PageMeta


class DataQualityPage(BaseModel):
    items: list[DataQualityFindingOut]
    meta: PageMeta


class RecommendationPage(BaseModel):
    items: list[RecommendationOut]
    meta: PageMeta


class AuditEventPage(BaseModel):
    items: list[AuditEventOut]
    meta: PageMeta


class SummaryOut(BaseModel):
    source_system: str | None
    people: int
    care_gap_findings: dict[str, int]
    data_quality_findings: dict[str, int]
    recommendations_by_status: dict[str, int]
    recommendations_by_priority: dict[str, int]
    audit_events: int
    label: Literal["DEMONSTRATION — fictional data and placeholder rules; not clinical advice"]
