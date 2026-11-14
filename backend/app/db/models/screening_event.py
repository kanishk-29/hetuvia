import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import ScreeningStatus, db_enum
from app.db.mixins import ProvenanceMixin


class ScreeningEvent(ProvenanceMixin, Base):
    __tablename__ = "screening_events"
    __table_args__ = (
        # A completion date only makes sense for completed screenings.
        # The reverse is allowed on purpose: "completed, date unknown" is a data-quality finding, not an error.
        CheckConstraint(
            "completed_on IS NULL OR result_status = 'completed'",
            name="date_only_if_completed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    screening_type: Mapped[str] = mapped_column(String(50))
    due_date: Mapped[date | None] = mapped_column(Date)  # NULL = due date unknown
    result_status: Mapped[ScreeningStatus] = mapped_column(
        db_enum(ScreeningStatus, "screening_status"), default=ScreeningStatus.PENDING
    )
    completed_on: Mapped[date | None] = mapped_column(Date)