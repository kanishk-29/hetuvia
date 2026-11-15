import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import DataState, db_enum
from app.db.mixins import ProvenanceMixin


class Observation(ProvenanceMixin, Base):
    __tablename__ = "observations"
    __table_args__ = (
        # A value exists if and only if the state says "present".
        CheckConstraint("(value_state = 'present') = (value_numeric IS NOT NULL)", name="value_matches_state"),
        CheckConstraint("value_numeric IS NULL OR unit IS NOT NULL", name="value_has_unit"),
        UniqueConstraint("source_system", "source_record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.id"))
    observation_type: Mapped[str] = mapped_column(String(50))
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    value_state: Mapped[DataState] = mapped_column(
        db_enum(DataState, "value_state"), default=DataState.PRESENT
    )
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))