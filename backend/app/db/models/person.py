import uuid
from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import DataState, PersonStatus, db_enum
from app.db.mixins import ProvenanceMixin


class Person(ProvenanceMixin, Base):
    __tablename__ = "people"

    person_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    date_of_birth: Mapped[date | None] = mapped_column(Date)  # NULL = unknown
    sex_recorded: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[str | None] = mapped_column(String(10))
    area_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[PersonStatus] = mapped_column(
        db_enum(PersonStatus, "person_status"), default=PersonStatus.ACTIVE
    )
    family_history_state: Mapped[DataState] = mapped_column(
        db_enum(DataState, "family_history_state"),
        default=DataState.NOT_COLLECTED,
        server_default=DataState.NOT_COLLECTED.value,
    )