"""Read-only operator API. Clinical actions stay in the CLI until auth/RBAC exists."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    AuditEventPage,
    CareGapPage,
    DataQualityPage,
    PersonOut,
    PersonPage,
    RecommendationPage,
    SummaryOut,
)
from app.db.enums import CareGapOutcome, OutreachPriority, PersonStatus, RecommendationStatus
from app.db.models import (
    AuditEvent,
    CareGapFinding,
    DataQualityFinding,
    Person,
    Recommendation,
)
from app.db.session import get_db

router = APIRouter()

DEMO_LABEL = "DEMONSTRATION — fictional data and placeholder rules; not clinical advice"


def _meta(total: int, limit: int, offset: int) -> dict:
    return {"total": total, "limit": limit, "offset": offset}


def _count_by(db: Session, model, column, source: str | None) -> dict[str, int]:
    query = select(column, func.count()).group_by(column)
    if source is not None:
        query = query.where(model.source_system == source)
    result = {}
    for value, count in db.execute(query):
        key = value.value if hasattr(value, "value") else str(value)
        result[str(key)] = count
    return result


@router.get("/summary", response_model=SummaryOut)
def get_summary(source: str | None = None, db: Session = Depends(get_db)) -> dict:
    people_query = select(func.count()).select_from(Person)
    if source is not None:
        people_query = people_query.where(Person.source_system == source)
    return {
        "source_system": source,
        "people": db.scalar(people_query) or 0,
        "care_gap_findings": _count_by(db, CareGapFinding, CareGapFinding.outcome, source),
        "data_quality_findings": _count_by(db, DataQualityFinding, DataQualityFinding.rule_code, source),
        "recommendations_by_status": _count_by(db, Recommendation, Recommendation.status, source),
        "recommendations_by_priority": _count_by(db, Recommendation, Recommendation.priority, source),
        "audit_events": db.scalar(select(func.count()).select_from(AuditEvent)) or 0,
        "label": DEMO_LABEL,
    }


@router.get("/people", response_model=PersonPage)
def list_people(
    source: str | None = None,
    status: PersonStatus | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    where = []
    if source is not None:
        where.append(Person.source_system == source)
    if status is not None:
        where.append(Person.status == status)
    if search:
        where.append(Person.source_record_id.ilike(f"%{search}%"))

    total = db.scalar(select(func.count()).select_from(Person).where(*where)) or 0
    rows = db.scalars(
        select(Person).where(*where).order_by(Person.source_record_id).limit(limit).offset(offset)
    ).all()
    return {"items": rows, "meta": _meta(total, limit, offset)}


@router.get("/people/{person_id}", response_model=PersonOut)
def get_person(person_id: uuid.UUID, db: Session = Depends(get_db)) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.get("/care-gap-findings", response_model=CareGapPage)
def list_care_gap_findings(
    person_id: uuid.UUID | None = None,
    source: str | None = None,
    outcome: CareGapOutcome | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    where = []
    if person_id is not None:
        where.append(CareGapFinding.person_id == person_id)
    if source is not None:
        where.append(CareGapFinding.source_system == source)
    if outcome is not None:
        where.append(CareGapFinding.outcome == outcome)

    total = db.scalar(select(func.count()).select_from(CareGapFinding).where(*where)) or 0
    rows = db.scalars(
        select(CareGapFinding)
        .where(*where)
        .order_by(CareGapFinding.created_at.desc(), CareGapFinding.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": rows, "meta": _meta(total, limit, offset)}


@router.get("/data-quality-findings", response_model=DataQualityPage)
def list_data_quality_findings(
    person_id: uuid.UUID | None = None,
    source: str | None = None,
    rule_code: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    where = []
    if person_id is not None:
        where.append(DataQualityFinding.person_id == person_id)
    if source is not None:
        where.append(DataQualityFinding.source_system == source)
    if rule_code is not None:
        where.append(DataQualityFinding.rule_code == rule_code)

    total = db.scalar(select(func.count()).select_from(DataQualityFinding).where(*where)) or 0
    rows = db.scalars(
        select(DataQualityFinding)
        .where(*where)
        .order_by(DataQualityFinding.created_at.desc(), DataQualityFinding.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": rows, "meta": _meta(total, limit, offset)}


@router.get("/recommendations", response_model=RecommendationPage)
def list_recommendations(
    person_id: uuid.UUID | None = None,
    source: str | None = None,
    status: RecommendationStatus | None = None,
    priority: OutreachPriority | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    where = []
    if person_id is not None:
        where.append(Recommendation.person_id == person_id)
    if source is not None:
        where.append(Recommendation.source_system == source)
    if status is not None:
        where.append(Recommendation.status == status)
    if priority is not None:
        where.append(Recommendation.priority == priority)

    total = db.scalar(select(func.count()).select_from(Recommendation).where(*where)) or 0
    rows = db.scalars(
        select(Recommendation)
        .where(*where)
        .order_by(Recommendation.updated_at.desc(), Recommendation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": rows, "meta": _meta(total, limit, offset)}


@router.get("/audit-events", response_model=AuditEventPage)
def list_audit_events(
    action: str | None = None,
    person_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    where = []
    if action is not None:
        where.append(AuditEvent.action == action)
    if person_id is not None:
        where.append(AuditEvent.person_id == person_id)

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*where)) or 0
    rows = db.scalars(
        select(AuditEvent)
        .where(*where)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": rows, "meta": _meta(total, limit, offset)}
