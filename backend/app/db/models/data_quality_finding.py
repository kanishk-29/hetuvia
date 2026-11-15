import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import DataState, Severity, db_enum


class DataQualityFinding(Base):
    """A sticky note on a record. Derived data: recomputed on every run, never edited by hand."""

    __tablename__ = "data_quality_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    source_system: Mapped[str] = mapped_column(String(50))
    subject_table: Mapped[str] = mapped_column(String(50))  # which table the flagged row lives in
    subject_id: Mapped[uuid.UUID] = mapped_column()  # the flagged row (the person's own ID for people)
    field_name: Mapped[str] = mapped_column(String(50))
    rule_code: Mapped[str] = mapped_column(String(20))
    rule_version: Mapped[str] = mapped_column(String(20))
    severity: Mapped[Severity] = mapped_column(db_enum(Severity, "severity"))
    field_state: Mapped[DataState | None] = mapped_column(db_enum(DataState, "finding_field_state"))
    message: Mapped[str] = mapped_column(Text)
    evaluated_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())