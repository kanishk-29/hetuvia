from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.models import ImportBatch


@dataclass
class FileStats:
    read: int = 0
    loaded: int = 0
    skipped: int = 0  # already imported earlier, left unchanged
    rejected: int = 0


@dataclass
class ImportOutcome:
    batch: ImportBatch
    files: dict[str, FileStats] = field(default_factory=dict)


class DataSourceAdapter(Protocol):
    """Every data source loads into the same canonical tables and returns a receipt."""

    source_system: str

    def load(self, db: Session) -> ImportOutcome: ...