import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.enums import RecommendationStatus as S
from app.db.models import Recommendation
from app.services.audit import record_audit

DECISION_TO_STATUS = {"approve": S.APPROVED, "defer": S.DEFERRED, "reject": S.REJECTED}
REVIEWABLE = (S.PENDING_REVIEW, S.DEFERRED)


class ReviewError(ValueError):
    pass


def review_recommendation(
    db: Session, recommendation_id: uuid.UUID, decision: str, reviewer: str,
    note: str | None, role: str = "clinical_reviewer",
) -> Recommendation:
    """Record a human decision. Defer and reject need a note. Every decision is audited."""
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise LookupError(f"No recommendation {recommendation_id}")
    if decision not in DECISION_TO_STATUS:
        raise ReviewError("decision must be approve, defer or reject")
    reviewer = (reviewer or "").strip()
    if not reviewer:
        raise ReviewError("a reviewer name is required")
    note = (note or "").strip()
    if decision in ("defer", "reject") and not note:
        raise ReviewError("a note is required to defer or reject")
    if rec.status not in REVIEWABLE:
        raise ReviewError(f"a recommendation that is {rec.status.value} cannot be reviewed")

    before = rec.status.value
    rec.status = DECISION_TO_STATUS[decision]
    rec.reviewer_name = reviewer
    rec.reviewer_note = note or None
    rec.reviewed_at = datetime.now(UTC)
    record_audit(db, actor=reviewer, role=role, action=f"recommendation_{decision}",
                 object_type="recommendation", object_id=rec.id, person_id=rec.person_id,
                 detail={"from": before, "to": rec.status.value, "note": note})
    db.flush()
    return rec