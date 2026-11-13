import enum

from sqlalchemy import Enum


class DataState(str, enum.Enum):
    PRESENT = "present"
    EXPLICITLY_ABSENT = "explicitly_absent"
    UNKNOWN = "unknown"
    NOT_COLLECTED = "not_collected"
    NOT_APPLICABLE = "not_applicable"
    STALE = "stale"


class Verification(str, enum.Enum):
    VERIFIED = "verified"
    REPORTED = "reported"
    ESTIMATED = "estimated"
    MISSING = "missing"


class PersonStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RelationshipType(str, enum.Enum):
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    SPOUSE = "spouse"
    GUARDIAN = "guardian"


class EncounterStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


def db_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Store enum VALUES as text, with a database CHECK that rejects anything else."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=30,
        values_callable=lambda e: [m.value for m in e],
    )