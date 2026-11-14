import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import ConditionContext, ConditionStatus, db_enum
from app.db.mixins import ProvenanceMixin


class Condition(ProvenanceMixin, Base):
    """A recorded condition. Codes in synthetic data are DEMO codes, not real clinical codes."""

    __tablename__ = "conditions"
    __table_args__ = (
        CheckConstraint(
            "context = 'family_history' OR related_person_id IS NULL",
            name="related_only_for_family_history",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    related_person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.person_id"))
    context: Mapped[ConditionContext] = mapped_column(db_enum(ConditionContext, "condition_context"))
    condition_code: Mapped[str] = mapped_column(String(30))
    condition_label: Mapped[str] = mapped_column(String(100))
    status: Mapped[ConditionStatus] = mapped_column(
        db_enum(ConditionStatus, "condition_status"), default=ConditionStatus.ACTIVE
    )
    onset_date: Mapped[date | None] = mapped_column(Date)