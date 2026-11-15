import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImportRejection(Base):
    """The quarantine bin: one row per rejected or skipped input row, with the reason.

    raw_row keeps the original cells so a person can fix and resubmit. In this prototype
    it only ever holds fictional data.
    """

    __tablename__ = "import_rejections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(100))
    row_number: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(50))
    reason_detail: Mapped[str] = mapped_column(Text)
    raw_row: Mapped[dict] = mapped_column(JSON)