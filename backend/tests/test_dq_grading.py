from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.adapters.synthetic_generator import PLANTED_KINDS, REFERENCE_DATE
from app.db.enums import DataState
from app.db.models import DataQualityFinding, Person
from app.services.dq_report import format_person_report, format_summary
from app.services.dq_runner import run_quality_check
from app.services.seed import seed_database

SOURCE = "synthetic"

# planted gap -> (rule code, field name or None for any, field state or None for any)
KEY_TO_RULE = {
    "missing_dob": ("DQ-001", "date_of_birth", None),
    "missing_language": ("DQ-002", "preferred_language", None),
    "family_history_unknown": ("DQ-003", None, DataState.UNKNOWN),
    "family_history_not_collected": ("DQ-003", None, DataState.NOT_COLLECTED),
    "weight_unknown": ("DQ-005", "weight", DataState.UNKNOWN),
    "height_not_collected": ("DQ-005", "height", DataState.NOT_COLLECTED),
    "stale_bp": ("DQ-006", None, None),
    "completed_screening_no_date": ("DQ-007", None, None),
    "screening_due_date_unknown": ("DQ-008", None, None),
    "no_encounters": ("DQ-009", None, None),
}


def people_flagged(db, code, field_name, state):
    query = select(DataQualityFinding.person_id).where(
        DataQualityFinding.source_system == SOURCE, DataQualityFinding.rule_code == code)
    if field_name:
        query = query.where(DataQualityFinding.field_name == field_name)
    if state:
        query = query.where(DataQualityFinding.field_state == state)
    return set(db.scalars(query))


def stored_snapshot(db):
    rows = db.scalars(select(DataQualityFinding).where(DataQualityFinding.source_system == SOURCE))
    return sorted(
        (str(f.person_id), f.rule_code, str(f.subject_id), f.field_name, f.severity.value,
         f.field_state.value if f.field_state else "")
        for f in rows
    )


def test_engine_finds_every_planted_gap(db):
    assert set(KEY_TO_RULE) == set(PLANTED_KINDS)  # the grading table must cover every planted kind
    pop = seed_database(db)
    run_quality_check(db, SOURCE, REFERENCE_DATE)

    problems = []
    for key, (code, field_name, state) in KEY_TO_RULE.items():
        planted = set(pop.planted[key])
        found = people_flagged(db, code, field_name, state)
        if planted - found:
            problems.append(f"{key}: engine missed {len(planted - found)} of {len(planted)} planted")
        if found - planted and key != "stale_bp":
            problems.append(f"{key}: engine flagged {len(found - planted)} people who were not planted")
    assert not problems, "; ".join(problems)

    # Stale readings may legitimately exceed the key: an adult whose only blood-pressure
    # readings happen to be old. Verify each extra from the generator's own records.
    limit = REFERENCE_DATE - timedelta(days=730)
    extras = people_flagged(db, "DQ-006", None, None) - set(pop.planted["stale_bp"])
    for person_id in extras:
        dates = [o.observed_at.date() for o in pop.observations
                 if o.person_id == person_id and o.observation_type == "systolic_blood_pressure"
                 and o.value_state == DataState.PRESENT]
        assert dates and max(dates) < limit


def test_clean_synthetic_data_has_no_contradictions(db):
    seed_database(db)
    run_quality_check(db, SOURCE, REFERENCE_DATE)
    contradictions = db.scalar(select(func.count()).select_from(DataQualityFinding).where(
        DataQualityFinding.source_system == SOURCE,
        DataQualityFinding.rule_code.in_(["DQ-004", "DQ-010"])))
    assert contradictions == 0


def test_rerun_replaces_findings_and_reproduces_them(db):
    seed_database(db)
    first = run_quality_check(db, SOURCE, REFERENCE_DATE)
    before = stored_snapshot(db)
    second = run_quality_check(db, SOURCE, REFERENCE_DATE)
    assert second.findings == first.findings
    assert stored_snapshot(db) == before


def test_summary_matches_stored_findings(db):
    seed_database(db)
    summary = run_quality_check(db, SOURCE, REFERENCE_DATE)
    stored = db.scalar(select(func.count()).select_from(DataQualityFinding)
                       .where(DataQualityFinding.source_system == SOURCE))
    assert summary.findings == stored == sum(summary.by_rule.values())
    assert summary.people == 300
    assert "people checked: 300" in format_summary(summary)


def test_person_report_shows_missing_fields_as_unknown(db):
    pop = seed_database(db)
    run_quality_check(db, SOURCE, REFERENCE_DATE)

    no_birth = db.get(Person, pop.planted["missing_dob"][0])
    text = format_person_report(db, SOURCE, no_birth.source_record_id)
    assert "date_of_birth: [unknown - not recorded]" in text
    assert "DQ-001" in text

    unknown_history = db.get(Person, pop.planted["family_history_unknown"][0])
    text = format_person_report(db, SOURCE, unknown_history.source_record_id)
    assert "family_history_state: unknown" in text
    assert "DQ-003" in text


def test_report_errors_are_clear(db):
    with pytest.raises(LookupError):
        format_person_report(db, "nothing_here", "X-1")
    db.add(Person(source_system="dq_empty", source_record_id="E-1"))
    db.flush()
    assert "quality-check" in format_person_report(db, "dq_empty", "E-1")