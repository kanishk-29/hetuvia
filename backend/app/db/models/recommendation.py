import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import OutreachPriority, RecommendationKind, RecommendationStatus, db_enum


class Recommendation(Base):
    """A proposed pathway for one person. Needs human review. Kept (as 'closed') when the gap closes."""

    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("source_system", "person_id", "pathway_code", "rule_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    source_system: Mapped[str] = mapped_column(String(50))
    kind: Mapped[RecommendationKind] = mapped_column(db_enum(RecommendationKind, "recommendation_kind"))
    pathway_code: Mapped[str] = mapped_column(String(50))
    pathway_title: Mapped[str] = mapped_column(String(200))
    rule_id: Mapped[str] = mapped_column(String(50))
    rule_version: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[OutreachPriority] = mapped_column(db_enum(OutreachPriority, "outreach_priority"))
    priority_reasons: Mapped[list] = mapped_column(JSON)
    evidence: Mapped[dict] = mapped_column(JSON)
    uncertainty: Mapped[str] = mapped_column(Text)
    review_required_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[RecommendationStatus] = mapped_column(
        db_enum(RecommendationStatus, "recommendation_status"), default=RecommendationStatus.PENDING_REVIEW
    )
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluated_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )