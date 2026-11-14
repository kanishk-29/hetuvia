from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.adapters.synthetic_generator import SOURCE, Population, generate_population
from app.db.models import (
    Condition,
    Encounter,
    FamilyRelationship,
    Observation,
    Person,
    ScreeningEvent,
)


def reset_synthetic(db: Session) -> None:
    """Delete only synthetic rows, children first so foreign keys stay valid."""
    for model in (Observation, ScreeningEvent, Condition, Encounter, FamilyRelationship, Person):
        db.execute(delete(model).where(model.source_system == SOURCE))


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