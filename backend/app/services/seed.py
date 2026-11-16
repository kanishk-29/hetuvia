from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.synthetic_generator import SOURCE, Population, generate_population
from app.db.models import (
    CareGapFinding, Condition, DataQualityFinding,
    Encounter,
    FamilyRelationship,
    ImportBatch,
    ImportRejection,
    Observation,
    Person,
    ScreeningEvent,
)


def reset_source(db: Session, source_system: str) -> None:
    """Delete everything one source loaded, children first so foreign keys stay valid."""
    for model in (CareGapFinding, DataQualityFinding, Observation, ScreeningEvent, Condition, Encounter, FamilyRelationship, Person):
        db.execute(delete(model).where(model.source_system == source_system))
    batch_ids = select(ImportBatch.id).where(ImportBatch.source_system == source_system)
    db.execute(delete(ImportRejection).where(ImportRejection.batch_id.in_(batch_ids)))
    db.execute(delete(ImportBatch).where(ImportBatch.source_system == source_system))


def reset_synthetic(db: Session) -> None:
    reset_source(db, SOURCE)


def seed_database(
    db: Session, seed: int = 42, total_people: int = 300, reset: bool = True
) -> Population:
    """Load a generated population. Flushes but never commits: the caller decides."""
    if reset:
        reset_synthetic(db)
    pop = generate_population(seed, total_people)
    for batch in (
        pop.people, pop.relationships, pop.encounters,
        pop.conditions, pop.observations, pop.screenings,
    ):
        db.add_all(batch)
        db.flush()  # parents must exist before their children
    return pop