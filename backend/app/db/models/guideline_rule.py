import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import RuleStatus, db_enum


class GuidelineRule(Base):
    """A versioned rule, loaded from a labelled config file. Never edited in place: new version, new row."""

    __tablename__ = "guideline_rules"
    __table_args__ = (UniqueConstraint("rule_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    service_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[RuleStatus] = mapped_column(db_enum(RuleStatus, "rule_status"))
    min_age_years: Mapped[int] = mapped_column(Integer)
    max_age_years: Mapped[int] = mapped_column(Integer)
    interval_days: Mapped[int] = mapped_column(Integer)
    lead_days: Mapped[int] = mapped_column(Integer)
    grace_days: Mapped[int] = mapped_column(Integer)
    exclusions: Mapped[list] = mapped_column(JSON)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(Text)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())