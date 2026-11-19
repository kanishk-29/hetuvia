import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.adapters.synthetic_generator import REFERENCE_DATE
from app.db.enums import CareGapOutcome as C
from app.db.enums import OutreachPriority, RecommendationKind as K, RecommendationStatus as S, ScreeningStatus
from app.db.models import AuditEvent, CareGapFinding, Person, Recommendation, ScreeningEvent
from app.services.audit import record_audit
from app.services.care_gap_runner import run_care_gap_check
from app.services.dq_runner import run_quality_check
from app.services.recommendation_runner import run_recommendations
from app.services.review import ReviewError, review_recommendation
from app.services.seed import reset_source, seed_database

SOURCE = "synthetic"


@pytest.fixture
def ready(db):
    pop = seed_database(db)
    run_quality_check(db, SOURCE, REFERENCE_DATE)
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    summary = run_recommendations(db, SOURCE, REFERENCE_DATE)
    return db, pop, summary


def make_recommendation(db):
    person = Person(source_system="rec_test")
    db.add(person)
    db.flush()
    rec = Recommendation(
        person_id=person.person_id, source_system="rec_test", kind=K.SERVICE,
        pathway_code="DEMO-PATHWAY-ADULT", pathway_title="t", rule_id="DEMO-ADULT-SCREEN",
        rule_version="1", priority=OutreachPriority.CONTACT_NOW, priority_reasons=["r"], evidence={},
        uncertainty="u", review_required_reason="r", evaluated_on=date(2026, 11, 1),
    )
    db.add(rec)
    db.flush()
    return rec


def test_recommendations_match_the_findings(ready):
    db, pop, summary = ready
    recs = db.scalars(select(Recommendation).where(Recommendation.source_system == SOURCE)).all()
    assert recs and all(r.status == S.PENDING_REVIEW for r in recs)

    service = {(r.person_id, r.rule_id) for r in recs if r.kind == K.SERVICE}
    gaps = {(f.person_id, f.rule_id) for f in db.scalars(select(CareGapFinding).where(
        CareGapFinding.source_system == SOURCE, CareGapFinding.outcome.in_([C.OVERDUE, C.DUE])))}
    assert service == gaps

    info = {r.person_id for r in recs if r.kind == K.INFORMATION}
    missing_birth = set(pop.planted["missing_dob"])
    assert not [r for r in recs if r.person_id in missing_birth and r.kind == K.SERVICE]
    assert missing_birth <= info
    history_gaps = set(pop.planted["family_history_unknown"]) | set(pop.planted["family_history_not_collected"])
    assert history_gaps <= info

    reset_source(db, SOURCE)  # recommendations must be removed before their people
    assert db.query(Recommendation).filter(Recommendation.source_system == SOURCE).count() == 0


def test_regenerating_keeps_human_decisions(ready):
    db, pop, summary = ready
    rec = db.scalars(select(Recommendation).where(
        Recommendation.source_system == SOURCE, Recommendation.kind == K.SERVICE)).first()
    review_recommendation(db, rec.id, "approve", "Dr Test", "looks right")
    again = run_recommendations(db, SOURCE, REFERENCE_DATE)
    db.refresh(rec)
    assert rec.status == S.APPROVED and rec.reviewer_name == "Dr Test"
    assert again.created == 0 and again.closed == 0


def test_closing_the_gap_closes_the_recommendation(ready):
    db, pop, summary = ready
    overdue = [f for f in db.scalars(select(CareGapFinding).where(
        CareGapFinding.source_system == SOURCE, CareGapFinding.rule_id == "DEMO-ADULT-SCREEN",
        CareGapFinding.outcome == C.OVERDUE)) if f.evidence["undated_completed_count"] == 0]
    target = overdue[0]
    rec = db.scalars(select(Recommendation).where(
        Recommendation.person_id == target.person_id, Recommendation.rule_id == "DEMO-ADULT-SCREEN")).one()
    assert rec.status == S.PENDING_REVIEW

    db.add(ScreeningEvent(person_id=target.person_id, screening_type="demo_adult_screening",
                          result_status=ScreeningStatus.COMPLETED, completed_on=date(2026, 10, 1),
                          source_system=SOURCE))
    db.flush()
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    again = run_recommendations(db, SOURCE, REFERENCE_DATE)
    db.refresh(rec)
    assert rec.status == S.CLOSED and again.closed >= 1
    events = db.scalars(select(AuditEvent).where(AuditEvent.object_id == rec.id)).all()
    assert [e.action for e in events] == ["recommendation_closed"]


def test_review_rules_and_audit_trail(db):
    rec = make_recommendation(db)
    with pytest.raises(ReviewError):
        review_recommendation(db, rec.id, "defer", "Dr Test", "")
    with pytest.raises(ReviewError):
        review_recommendation(db, rec.id, "approve", "  ", "ok")
    with pytest.raises(ReviewError):
        review_recommendation(db, rec.id, "maybe", "Dr Test", "x")
    with pytest.raises(LookupError):
        review_recommendation(db, uuid.uuid4(), "approve", "Dr Test", "x")
    assert rec.status == S.PENDING_REVIEW  # the failed attempts changed nothing

    review_recommendation(db, rec.id, "defer", "Dr Test", "need more information")
    assert rec.status == S.DEFERRED
    review_recommendation(db, rec.id, "approve", "Dr Test", "")  # a deferred one can be revisited
    assert rec.status == S.APPROVED
    with pytest.raises(ReviewError):
        review_recommendation(db, rec.id, "reject", "Dr Test", "too late")  # decided is final

    actions = [e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.object_id == rec.id))]
    assert sorted(actions) == ["recommendation_approve", "recommendation_defer"]


def test_audit_log_survives_a_reset(db):
    event = record_audit(db, actor="Dr Test", role="clinical_reviewer", action="test",
                         object_type="recommendation", object_id=uuid.uuid4())
    reset_source(db, "rec_test")
    assert db.query(AuditEvent).filter(AuditEvent.id == event.id).count() == 1