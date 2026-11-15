import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import EncounterStatus, db_enum
from app.db.mixins import ProvenanceMixin


class Encounter(ProvenanceMixin, Base):
    __tablename__ = "encounters"
    __table_args__ = (UniqueConstraint("source_system", "source_record_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"), index=True)
    encounter_type: Mapped[str] = mapped_column(String(50))
    encounter_date: Mapped[date] = mapped_column(Date)
    status: Mapped[EncounterStatus] = mapped_column(db_enum(EncounterStatus, "encounter_status"))