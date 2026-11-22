from datetime import date
from pathlib import Path

import pytest

from app.db.enums import OutreachPriority, RecommendationKind, RecommendationStatus
from app.db.models import Person, Recommendation
from app.export_demo import DEFAULT_EXPORT_PATH, build_export

SOURCE = "export_test"


def _person(db, source_record_id: str) -> Person:
    person = Person(source_system=SOURCE, source_record_id=source_record_id)
    db.add(person)
    db.flush()
    return person


def _recommendation(db, person: Person, evaluated_on: date, code: str) -> Recommendation:
    rec = Recommendation(
        person_id=person.person_id,
        source_system=SOURCE,
        kind=RecommendationKind.INFORMATION,
        pathway_code=code,
        pathway_title="Resolve missing information first (demonstration)",
        rule_id="DATA-QUALITY",
        rule_version=None,
        priority=OutreachPriority.REVIEW_DATA_FIRST,
        priority_reasons=[],
        evidence={},
        uncertainty="Demonstration only.",
        review_required_reason="Human review required.",
        status=RecommendationStatus.PENDING_REVIEW,
        evaluated_on=evaluated_on,
    )
    db.add(rec)
    db.flush()
    return rec


def test_export_reports_the_stored_evaluation_date(db):
    person = _person(db, "SYN-9001")
    stored_date = date(2026, 1, 15)
    _recommendation(db, person, stored_date, "DEMO-PATHWAY-INFO")

    data = build_export(db, SOURCE, date(2026, 11, 1))

    assert data["meta"]["evaluated_on"] == stored_date.isoformat()


def test_export_refuses_mixed_stored_evaluation_dates(db):
    person = _person(db, "SYN-9002")
    _recommendation(db, person, date(2026, 1, 15), "DEMO-PATHWAY-INFO")
    _recommendation(db, person, date(2026, 11, 1), "DEMO-PATHWAY-OTHER")

    with pytest.raises(ValueError, match="mixed evaluation dates"):
        build_export(db, SOURCE, date(2026, 11, 1))


def test_default_export_lands_beside_the_served_demo_page():
    """White-box layout check: GitHub Pages serves docs/, so data.js must land there too."""
    repo_root = Path(__file__).resolve().parents[2]
    from_backend = (repo_root / "backend" / DEFAULT_EXPORT_PATH).resolve()

    assert from_backend == (repo_root / "docs" / "data.js").resolve()
    assert from_backend.is_file()
    demo_page = (repo_root / "docs" / "index.html").resolve()
    assert demo_page.is_file()
    assert 'src="data.js"' in demo_page.read_text(encoding="utf-8")
