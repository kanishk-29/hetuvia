import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    """Who did what, when. Append-only history. No foreign keys, so resets never erase it."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    object_type: Mapped[str] = mapped_column(String(50))
    object_id: Mapped[uuid.UUID] = mapped_column()
    person_id: Mapped[uuid.UUID | None] = mapped_column()
    detail: Mapped[dict] = mapped_column(JSON)