import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Person


class PeopleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, person: Person) -> Person:
        self.db.add(person)
        self.db.flush()  # the caller decides when to commit
        return person

    def get(self, person_id: uuid.UUID) -> Person | None:
        return self.db.get(Person, person_id)

    def list(self, limit: int = 50, offset: int = 0) -> list[Person]:
        stmt = select(Person).order_by(Person.imported_at).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))