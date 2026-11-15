from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.base import ImportOutcome
from app.adapters.synthetic_generator import SOURCE as SYNTHETIC_SOURCE
from app.services.csv_importer import import_csv_directory


class CSVAdapter:
    def __init__(self, directory: Path | str, source_system: str = "csv_import", today: date | None = None) -> None:
        if source_system == SYNTHETIC_SOURCE:
            raise ValueError("'synthetic' is reserved for generated data; use another source name")
        self.directory = Path(directory)
        self.source_system = source_system
        self.today = today

    def load(self, db: Session) -> ImportOutcome:
        return import_csv_directory(db, self.directory, self.source_system, self.today)