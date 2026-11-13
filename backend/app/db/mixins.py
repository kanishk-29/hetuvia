from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.enums import Verification, db_enum


class ProvenanceMixin:
    source_system: Mapped[str] = mapped_column(String(50))
    source_record_id: Mapped[str | None] = mapped_column(String(100))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification: Mapped[Verification] = mapped_column(
        db_enum(Verification, "verification"), default=Verification.REPORTED
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )