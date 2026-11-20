import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.enums import (
    CareGapOutcome,
    DataState,
    OutreachPriority,
    PersonStatus,
    RecommendationKind,
    RecommendationStatus,
    Severity,
)
from app.db.models import (
    AuditEvent,
    CareGapFinding,
    DataQualityFinding,
    Person,
    Recommendation,
)
from app.db.session import get_db
from app.main import app

SOURCE = "api_test"


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def seeded(db):
    person = Person(
        source_system=SOURCE,
        source_record_id="API-0001",
        date_of_birth=date(1980, 5, 2),
        preferred_language="en",
        area_code="AREA-A",
        status=PersonStatus.ACTIVE,
        family_history_state=DataState.PRESENT,
    )
    db.add(person)
    db.flush()

    gap = CareGapFinding(
        person_id=person.person_id,
        source_system=SOURCE,
        rule_id="DEMO-ADULT-SCREEN",
        rule_version="v1",
        service_type="demo_adult_screening",
        outcome=CareGapOutcome.OVERDUE,
        evaluated_on=date(2026, 11, 1),
        age_years=46,
        message="Screening is overdue (demonstration).",
        evidence={"outcome": "overdue"},
    )
    dq = DataQualityFinding(
        person_id=person.person_id,
        source_system=SOURCE,
        subject_table="people",
        subject_id=person.person_id,
        field_name="date_of_birth",
        rule_code="DQ-001",
        rule_version="v1",
        severity=Severity.WARNING,
        field_state=DataState.UNKNOWN,
        message="Date of birth is unknown (demonstration).",
        evaluated_on=date(2026, 11, 1),
    )
    rec = Recommendation(
        person_id=person.person_id,
        source_system=SOURCE,
        kind=RecommendationKind.SERVICE,
        pathway_code="DEMO-PATHWAY-SERVICE",
        pathway_title="Close a demonstrated screening gap",
        rule_id="DEMO-ADULT-SCREEN",
        rule_version="v1",
        priority=OutreachPriority.CONTACT_NOW,
        priority_reasons=["overdue"],
        evidence={"rule_id": "DEMO-ADULT-SCREEN"},
        uncertainty="Demonstration only.",
        review_required_reason="Human review required.",
        status=RecommendationStatus.PENDING_REVIEW,
        evaluated_on=date(2026, 11, 1),
    )
    db.add_all([gap, dq, rec])
    db.flush()

    audit = AuditEvent(
        actor="tester",
        role="clinical_reviewer",
        action="recommendation_approve",
        object_type="recommendation",
        object_id=rec.id,
        person_id=person.person_id,
        detail={"decision": "approve"},
    )
    db.add(audit)
    db.flush()
    return person, gap, dq, rec, audit


def test_people_list_is_paginated_and_filtered(client, seeded):
    person, *_ = seeded
    response = client.get("/api/v1/people", params={"source": SOURCE, "limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"total": 1, "limit": 1, "offset": 0}
    assert body["items"][0]["source_record_id"] == "API-0001"

    missing = client.get("/api/v1/people", params={"source": "no_such_source"})
    assert missing.json()["meta"]["total"] == 0

    search = client.get("/api/v1/people", params={"search": "API-000"})
    assert search.json()["meta"]["total"] == 1


def test_get_person_returns_404_for_unknown_id(client):
    response = client.get(f"/api/v1/people/{uuid.uuid4()}")
    assert response.status_code == 404


def test_finding_and_recommendation_filters(client, seeded):
    person, gap, dq, rec, _ = seeded
    assert client.get(
        "/api/v1/care-gap-findings",
        params={"source": SOURCE, "person_id": str(person.person_id), "outcome": "overdue"},
    ).json()["meta"]["total"] == 1
    assert client.get(
        "/api/v1/care-gap-findings", params={"source": SOURCE, "outcome": "up_to_date"}
    ).json()["meta"]["total"] == 0
    assert client.get(
        "/api/v1/data-quality-findings", params={"source": SOURCE, "rule_code": "DQ-001"}
    ).json()["items"][0]["id"] == str(dq.id)
    assert client.get(
        "/api/v1/recommendations",
        params={"source": SOURCE, "status": "pending_review", "priority": "contact_now"},
    ).json()["meta"]["total"] == 1
    assert client.get(
        "/api/v1/recommendations",
        params={"source": SOURCE, "person_id": str(person.person_id), "status": "approved"},
    ).json()["meta"]["total"] == 0


def test_audit_events_are_readable(client, seeded):
    _, _, _, _, audit = seeded
    body = client.get(
        "/api/v1/audit-events", params={"action": "recommendation_approve"}
    ).json()
    assert body["meta"]["total"] >= 1
    assert any(item["id"] == str(audit.id) for item in body["items"])


def test_summary_reflects_stored_records(client, seeded):
    body = client.get("/api/v1/summary", params={"source": SOURCE}).json()
    assert body["source_system"] == SOURCE
    assert body["people"] == 1
    assert body["care_gap_findings"]["overdue"] == 1
    assert body["data_quality_findings"]["DQ-001"] == 1
    assert body["recommendations_by_status"]["pending_review"] == 1
    assert body["recommendations_by_priority"]["contact_now"] == 1
    assert body["audit_events"] >= 1
    assert body["label"].startswith("DEMONSTRATION")


def test_invalid_pagination_is_rejected(client):
    assert client.get("/api/v1/people", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/recommendations", params={"offset": -1}).status_code == 422
