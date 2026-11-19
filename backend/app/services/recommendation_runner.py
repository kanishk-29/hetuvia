"""Turn stored findings into proposed pathways, keeping every human decision."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.enums import RecommendationStatus as S
from app.db.models import CareGapFinding, DataQualityFinding, Recommendation
from app.services.audit import record_audit
from app.services.recommendation_engine import CareGapView, DataGapView, build_recommendations


@dataclass
class RecommendationSummary:
    source_system: str
    evaluated_on: date
    created: int = 0
    updated: int = 0
    reopened: int = 0
    closed: int = 0
    open_total: int = 0
    open_by_priority: dict[str, int] = field(default_factory=dict)


def run_recommendations(db: Session, source_system: str, evaluated_on: date) -> RecommendationSummary:
    """Create, update, reopen or close recommendations. Decisions are never deleted. Flushes only."""
    care = defaultdict(list)
    for f in db.scalars(select(CareGapFinding).where(CareGapFinding.source_system == source_system)
                        .order_by(CareGapFinding.rule_id, CareGapFinding.id)):
        care[f.person_id].append(CareGapView(f.id, f.rule_id, f.rule_version, f.outcome, f.message,
                                             f.due_date, f.last_completed_on, f.age_years))
    data = defaultdict(list)
    for f in db.scalars(select(DataQualityFinding).where(DataQualityFinding.source_system == source_system)
                        .order_by(DataQualityFinding.rule_code, DataQualityFinding.id)):
        data[f.person_id].append(DataGapView(f.id, f.rule_code, f.field_name, f.field_state, f.message))

    existing = {(r.person_id, r.pathway_code, r.rule_id): r for r in db.scalars(
        select(Recommendation).where(Recommendation.source_system == source_system))}
    summary = RecommendationSummary(source_system=source_system, evaluated_on=evaluated_on)
    produced = set()

    for person_id in sorted(set(care) | set(data), key=str):
        for draft in build_recommendations(care.get(person_id, []), data.get(person_id, [])):
            key = (person_id, draft.pathway_code, draft.rule_id)
            produced.add(key)
            row = existing.get(key)
            if row is None:
                db.add(Recommendation(
                    person_id=person_id, source_system=source_system, kind=draft.kind,
                    pathway_code=draft.pathway_code, pathway_title=draft.pathway_title,
                    rule_id=draft.rule_id, rule_version=draft.rule_version, priority=draft.priority,
                    priority_reasons=list(draft.priority_reasons), evidence=draft.evidence,
                    uncertainty=draft.uncertainty, review_required_reason=draft.review_required_reason,
                    status=S.PENDING_REVIEW, evaluated_on=evaluated_on,
                ))
                summary.created += 1
                continue
            row.rule_version = draft.rule_version
            row.priority = draft.priority
            row.priority_reasons = list(draft.priority_reasons)
            row.evidence = draft.evidence
            row.uncertainty = draft.uncertainty
            row.review_required_reason = draft.review_required_reason
            row.evaluated_on = evaluated_on
            if row.status == S.CLOSED:  # the need came back: ask for a fresh review
                row.status = S.PENDING_REVIEW
                row.reviewer_name = row.reviewer_note = row.reviewed_at = None
                record_audit(db, actor="system", role="system", action="recommendation_reopened",
                             object_type="recommendation", object_id=row.id, person_id=person_id,
                             detail={"evaluated_on": evaluated_on.isoformat()})
                summary.reopened += 1
            else:
                summary.updated += 1

    for key, row in existing.items():
        if key not in produced and row.status != S.CLOSED:
            previous = row.status.value
            row.status = S.CLOSED  # the gap closed: keep the record, never delete it
            record_audit(db, actor="system", role="system", action="recommendation_closed",
                         object_type="recommendation", object_id=row.id, person_id=row.person_id,
                         detail={"previous_status": previous, "evaluated_on": evaluated_on.isoformat()})
            summary.closed += 1
    db.flush()

    rows = db.execute(
        select(Recommendation.priority, func.count())
        .where(Recommendation.source_system == source_system, Recommendation.status != S.CLOSED)
        .group_by(Recommendation.priority)
    ).all()
    summary.open_by_priority = {priority.value: count for priority, count in rows}
    summary.open_total = sum(summary.open_by_priority.values())
    return summary


def format_recommendation_summary(summary: RecommendationSummary) -> str:
    lines = [
        f"Recommendations for source '{summary.source_system}' evaluated on {summary.evaluated_on}",
        f"  created {summary.created}, updated {summary.updated}, reopened {summary.reopened}, closed {summary.closed}",
        f"  open recommendations: {summary.open_total}",
    ]
    for name in ("contact_now", "review_data_first", "routine"):
        lines.append(f"    {name}: {summary.open_by_priority.get(name, 0)}")
    lines += [
        "",
        "Every recommendation starts as pending_review. Priority is outreach order, not clinical urgency.",
        "Pathways are DEMONSTRATION placeholders, not Abu Dhabi guidance.",
    ]
    return "\n".join(lines)