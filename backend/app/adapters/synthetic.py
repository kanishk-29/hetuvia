from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.base import FileStats, ImportOutcome
from app.adapters.synthetic_generator import SOURCE, Population
from app.db.enums import ImportStatus
from app.db.models import ImportBatch
from app.services.seed import seed_database


class SyntheticAdapter:
    source_system = SOURCE

    def __init__(self, seed: int = 42, total_people: int = 300) -> None:
        self.seed = seed
        self.total_people = total_people
        self.population: Population | None = None  # kept so callers can read the answer key

    def load(self, db: Session) -> ImportOutcome:
        pop = seed_database(db, self.seed, self.total_people, reset=True)
        self.population = pop
        counts = {
            "people": len(pop.people),
            "relationships": len(pop.relationships),
            "encounters": len(pop.encounters),
            "conditions": len(pop.conditions),
            "observations": len(pop.observations),
            "screenings": len(pop.screenings),
        }
        total = sum(counts.values())
        batch = ImportBatch(
            source_system=SOURCE,
            description=f"synthetic seed={self.seed}, people={self.total_people}",
            status=ImportStatus.COMPLETED,
            finished_at=datetime.now(UTC),
            rows_read=total, rows_loaded=total, rows_skipped=0, rows_rejected=0,
        )
        db.add(batch)
        db.flush()
        return ImportOutcome(batch=batch, files={n: FileStats(read=c, loaded=c) for n, c in counts.items()})