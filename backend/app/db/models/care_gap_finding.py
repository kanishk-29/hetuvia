import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import CareGapOutcome, db_enum


class CareGapFinding(Base):
    """One rule's verdict for one person. Derived data: recomputed on every run."""

    __tablename__ = "care_gap_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    source_system: Mapped[str] = mapped_column(String(50))
    rule_id: Mapped[str] = mapped_column(String(50))  # matched to guideline_rules by (rule_id, version)
    rule_version: Mapped[str] = mapped_column(String(20))
    service_type: Mapped[str] = mapped_column(String(50))
    outcome: Mapped[CareGapOutcome] = mapped_column(db_enum(CareGapOutcome, "care_gap_outcome"))
    evaluated_on: Mapped[date] = mapped_column(Date)
    age_years: Mapped[int | None] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date)
    last_completed_on: Mapped[date | None] = mapped_column(Date)
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON)  # every fact the verdict used
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())