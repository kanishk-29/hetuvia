import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record_audit(
    db: Session, *, actor: str, role: str, action: str, object_type: str,
    object_id: uuid.UUID, person_id: uuid.UUID | None = None, detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(actor=actor, role=role, action=action, object_type=object_type,
                       object_id=object_id, person_id=person_id, detail=detail or {})
    db.add(event)
    db.flush()
    return event