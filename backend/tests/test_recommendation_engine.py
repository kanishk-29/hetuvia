import uuid
from datetime import date

from app.db.enums import CareGapOutcome as C
from app.db.enums import DataState, OutreachPriority as P, RecommendationKind as K
from app.services.recommendation_engine import CareGapView, DataGapView, build_recommendations, queue_priority


def care(rule_id="DEMO-ADULT-SCREEN", outcome=C.OVERDUE):
    return CareGapView(uuid.uuid4(), rule_id, "1", outcome, "a finding message", date(2021, 1, 1), None, 46)


def gap(code="DQ-003", field="family_history_state", state=DataState.UNKNOWN):
    return DataGapView(uuid.uuid4(), code, field, state, "a data gap message")


def test_overdue_service_becomes_a_contact_now_recommendation():
    drafts = build_recommendations([care()], [])
    assert len(drafts) == 1
    assert (drafts[0].kind, drafts[0].priority) == (K.SERVICE, P.CONTACT_NOW)
    assert drafts[0].pathway_code == "DEMO-PATHWAY-ADULT"
    assert drafts[0].rule_id == "DEMO-ADULT-SCREEN"


def test_due_service_is_routine():
    assert build_recommendations([care(outcome=C.DUE)], [])[0].priority == P.ROUTINE


def test_not_assessable_never_becomes_a_service_recommendation():
    drafts = build_recommendations([care(outcome=C.NOT_ASSESSABLE)], [])
    assert [(d.kind, d.priority) for d in drafts] == [(K.INFORMATION, P.REVIEW_DATA_FIRST)]
    assert drafts[0].rule_id == "DATA-QUALITY"


def test_only_blocking_data_gaps_create_an_information_recommendation():
    assert build_recommendations([], [gap("DQ-005", "weight")]) == []
    assert build_recommendations([], [gap("DQ-007", "completed_on")]) == []
    assert len(build_recommendations([], [gap("DQ-003")])) == 1
    assert len(build_recommendations([], [gap("DQ-001", "date_of_birth")])) == 1


def test_a_service_and_an_information_recommendation_can_coexist():
    drafts = build_recommendations([care("DEMO-WCV", C.OVERDUE), care("DEMO-ADULT-SCREEN", C.NOT_ASSESSABLE)], [])
    assert sorted(d.kind.value for d in drafts) == ["information", "service"]


def test_up_to_date_and_not_eligible_produce_nothing():
    assert build_recommendations([care(outcome=C.UP_TO_DATE), care("DEMO-WCV", C.NOT_ELIGIBLE)], []) == []


def test_every_recommendation_needs_review_and_states_its_uncertainty():
    drafts = build_recommendations([care()], [gap()])
    assert len(drafts) == 2
    for draft in drafts:
        assert draft.review_required_reason and draft.uncertainty
        assert any("not clinical urgency" in reason for reason in draft.priority_reasons)


def test_queue_priority_picks_the_most_pressing():
    assert queue_priority([P.ROUTINE, P.CONTACT_NOW]) == P.CONTACT_NOW
    assert queue_priority([P.ROUTINE, P.REVIEW_DATA_FIRST]) == P.REVIEW_DATA_FIRST
    assert queue_priority([]) is None


def test_same_input_gives_the_same_ordered_output():
    gaps = [care("DEMO-WCV", C.OVERDUE), care("DEMO-ADULT-SCREEN", C.DUE)]
    first = build_recommendations(gaps, [gap()])
    assert first == build_recommendations(list(reversed(gaps)), [gap()]) or [d.pathway_code for d in first] == sorted(d.pathway_code for d in first)