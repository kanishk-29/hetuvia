"""Turns findings into proposed pathways. Pure functions: no database.

Outreach priority is NOT clinical urgency, and every recommendation needs human review.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.db.enums import CareGapOutcome, DataState, OutreachPriority, RecommendationKind
from app.services.pathways import (
    BLOCKING_DATA_QUALITY_RULES,
    INFORMATION_PATHWAY_CODE,
    INFORMATION_PATHWAY_TITLE,
    INFORMATION_RULE_ID,
    SERVICE_PATHWAYS,
)

PRIORITY_RANK = {
    OutreachPriority.CONTACT_NOW: 0,
    OutreachPriority.REVIEW_DATA_FIRST: 1,
    OutreachPriority.ROUTINE: 2,
}
NOT_URGENCY = "Outreach priority is a coordination order, not clinical urgency; clinical urgency is not assessed here."


@dataclass(frozen=True)
class CareGapView:
    finding_id: uuid.UUID
    rule_id: str
    rule_version: str
    outcome: CareGapOutcome
    message: str
    due_date: date | None
    last_completed_on: date | None
    age_years: int | None


@dataclass(frozen=True)
class DataGapView:
    finding_id: uuid.UUID
    rule_code: str
    field_name: str
    field_state: DataState | None
    message: str


@dataclass(frozen=True)
class RecommendationDraft:
    kind: RecommendationKind
    pathway_code: str
    pathway_title: str
    rule_id: str
    rule_version: str | None
    priority: OutreachPriority
    priority_reasons: tuple[str, ...]
    evidence: dict
    uncertainty: str
    review_required_reason: str


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def queue_priority(priorities: Iterable[OutreachPriority]) -> OutreachPriority | None:
    """A person's work-queue category is their most urgent-to-contact recommendation."""
    ranked = sorted(priorities, key=lambda p: PRIORITY_RANK[p])
    return ranked[0] if ranked else None


def build_recommendations(care_gaps: list[CareGapView], data_gaps: list[DataGapView]) -> list[RecommendationDraft]:
    drafts: list[RecommendationDraft] = []
    info_reasons: list[str] = []
    info_care: list[dict] = []
    info_data: list[dict] = []

    for gap in sorted(care_gaps, key=lambda g: (g.rule_id, str(g.finding_id))):
        if gap.outcome in (CareGapOutcome.OVERDUE, CareGapOutcome.DUE) and gap.rule_id in SERVICE_PATHWAYS:
            code, title = SERVICE_PATHWAYS[gap.rule_id]
            overdue = gap.outcome == CareGapOutcome.OVERDUE
            drafts.append(RecommendationDraft(
                kind=RecommendationKind.SERVICE, pathway_code=code, pathway_title=title,
                rule_id=gap.rule_id, rule_version=gap.rule_version,
                priority=OutreachPriority.CONTACT_NOW if overdue else OutreachPriority.ROUTINE,
                priority_reasons=(gap.message, NOT_URGENCY),
                evidence={
                    "care_gap_finding_id": str(gap.finding_id), "rule_id": gap.rule_id,
                    "rule_version": gap.rule_version, "outcome": gap.outcome.value,
                    "due_date": _iso(gap.due_date), "last_completed_on": _iso(gap.last_completed_on),
                    "age_years": gap.age_years, "message": gap.message,
                },
                uncertainty="Based on a demonstration rule: eligibility ages and intervals are placeholders, not an approved guideline.",
                review_required_reason="Every recommendation needs human review in this prototype before any outreach.",
            ))
        elif gap.outcome == CareGapOutcome.NOT_ASSESSABLE:
            info_reasons.append(f"{gap.rule_id}: {gap.message}")
            info_care.append({"care_gap_finding_id": str(gap.finding_id), "rule_id": gap.rule_id,
                              "outcome": gap.outcome.value, "message": gap.message})

    for gap in sorted(data_gaps, key=lambda d: (d.rule_code, d.field_name, str(d.finding_id))):
        if gap.rule_code in BLOCKING_DATA_QUALITY_RULES:
            info_reasons.append(f"{gap.rule_code} {gap.field_name}: {gap.message}")
            info_data.append({"finding_id": str(gap.finding_id), "rule_code": gap.rule_code,
                              "field_name": gap.field_name,
                              "field_state": gap.field_state.value if gap.field_state else None,
                              "message": gap.message})

    if info_reasons:
        drafts.append(RecommendationDraft(
            kind=RecommendationKind.INFORMATION, pathway_code=INFORMATION_PATHWAY_CODE,
            pathway_title=INFORMATION_PATHWAY_TITLE, rule_id=INFORMATION_RULE_ID, rule_version=None,
            priority=OutreachPriority.REVIEW_DATA_FIRST,
            priority_reasons=tuple(info_reasons) + (NOT_URGENCY,),
            evidence={"care_gap_findings": info_care, "data_quality_findings": info_data},
            uncertainty="Information is missing or unreliable. Missing is not treated as normal or as negative.",
            review_required_reason="Uncertain: this recommendation rests on missing information.",
        ))
    return sorted(drafts, key=lambda d: (d.pathway_code, d.rule_id))