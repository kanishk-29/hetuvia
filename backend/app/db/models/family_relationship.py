import uuid

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import RelationshipType, db_enum
from app.db.mixins import ProvenanceMixin


class FamilyRelationship(ProvenanceMixin, Base):
    """Reads as: related_person is the <relationship_type> of person."""

    __tablename__ = "family_relationships"
    __table_args__ = (
        CheckConstraint("person_id <> related_person_id", name="not_self"),
        UniqueConstraint("person_id", "related_person_id", "relationship_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"))
    related_person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.person_id"))
    relationship_type: Mapped[RelationshipType] = mapped_column(
        db_enum(RelationshipType, "relationship_type")
    )