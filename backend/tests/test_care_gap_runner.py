from datetime import date

import pytest
from sqlalchemy import func, select

from app.adapters.synthetic_generator import REFERENCE_DATE
from app.db.enums import CareGapOutcome as C
from app.db.enums import ScreeningStatus
from app.db.models import CareGapFinding, GuidelineRule, Person, ScreeningEvent
from app.services.care_gap_engine import age_in_years
from app.services.care_gap_report import format_care_gap_person_report, format_care_gap_summary
from app.services.care_gap_runner import run_care_gap_check
from app.services.rule_loader import load_rules
from app.services.seed import seed_database

SOURCE = "synthetic"
RULE_FOR_SERVICE = {"demo_well_child_visit": "DEMO-WCV", "demo_adult_screening": "DEMO-ADULT-SCREEN"}


@pytest.fixture
def checked(db):
    pop = seed_database(db)
    summary = run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    return db, pop, summary


def test_every_person_is_judged_against_every_rule(checked):
    db, pop, summary = checked
    rules = load_rules()
    assert summary.people == 300
    assert summary.evaluations == 300 * len(rules)
    for rule in rules:
        assert sum(summary.by_rule_outcome[rule.rule_id].values()) == 300
    ids = [rule.rule_id for rule in rules]
    synced = db.scalar(select(func.count()).select_from(GuidelineRule).where(GuidelineRule.rule_id.in_(ids)))
    assert synced == len(rules)


def test_eligibility_follows_age_and_missing_birth_dates_are_information_gaps(checked):
    db, pop, summary = checked
    missing = set(pop.planted["missing_dob"])
    known = [born for pid, born in pop.true_birth_dates.items() if pid not in missing]
    for rule in load_rules():
        counts = summary.by_rule_outcome[rule.rule_id]
        in_range = sum(1 for born in known
                       if rule.min_age_years <= age_in_years(born, REFERENCE_DATE) <= rule.max_age_years)
        assert counts.get("not_eligible", 0) == len(known) - in_range
        assert counts.get("not_assessable", 0) >= len(missing)
        eligible_side = sum(counts.get(o, 0) for o in ("overdue", "due", "up_to_date", "not_assessable"))
        assert eligible_side == in_range + len(missing)
    outcomes = set(db.scalars(select(CareGapFinding.outcome).where(CareGapFinding.person_id.in_(missing))))
    assert outcomes == {C.NOT_ASSESSABLE}  # never a care gap, never 'fine'


def test_a_completed_screening_without_a_date_is_never_called_a_gap(checked):
    db, pop, summary = checked
    undated = {(s.person_id, RULE_FOR_SERVICE[s.screening_type]) for s in pop.screenings
               if s.result_status == ScreeningStatus.COMPLETED and s.completed_on is None}
    assert undated
    flagged = {(person_id, rule_id) for person_id, rule_id in db.execute(
        select(CareGapFinding.person_id, CareGapFinding.rule_id)
        .where(CareGapFinding.outcome.in_([C.OVERDUE, C.DUE])))}
    assert not (undated & flagged)


def test_a_completed_service_closes_the_gap_in_the_database(db):
    seed_database(db)
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    overdue = db.scalars(select(CareGapFinding).where(
        CareGapFinding.rule_id == "DEMO-ADULT-SCREEN", CareGapFinding.outcome == C.OVERDUE)).all()
    target = next((f for f in overdue if f.evidence["undated_completed_count"] == 0), None)
    assert target is not None

    db.add(ScreeningEvent(
        person_id=target.person_id, screening_type="demo_adult_screening",
        result_status=ScreeningStatus.COMPLETED, completed_on=date(2026, 10, 1), source_system=SOURCE,
    ))
    db.flush()
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)

    remaining = db.scalars(select(CareGapFinding).where(
        CareGapFinding.person_id == target.person_id, CareGapFinding.rule_id == "DEMO-ADULT-SCREEN")).all()
    assert remaining == []  # now up to date, so nothing is stored


def test_reruns_and_reseeds_reproduce_the_same_verdicts(db):
    def snapshot():
        rows = db.scalars(select(CareGapFinding).where(CareGapFinding.source_system == SOURCE))
        return sorted((str(f.person_id), f.rule_id, f.rule_version, f.outcome.value,
                       f.due_date, f.last_completed_on) for f in rows)

    seed_database(db)
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    first = snapshot()
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    assert snapshot() == first  # a rerun replaces, never duplicates
    seed_database(db)
    run_care_gap_check(db, SOURCE, REFERENCE_DATE)
    assert snapshot() == first  # same input and same rule version, same result


def test_report_shows_the_rule_the_label_and_the_facts(checked):
    db, pop, summary = checked
    finding = db.scalars(select(CareGapFinding).where(CareGapFinding.outcome == C.OVERDUE)).first()
    person = db.get(Person, finding.person_id)
    text = format_care_gap_person_report(db, SOURCE, person.source_record_id)
    assert "DEMONSTRATION RULES" in text
    assert finding.rule_id in text
    assert "[overdue]" in text
    assert "next due" in text
    assert "evaluated on 2026-11-01" in text


def test_summary_matches_stored_findings(checked):
    db, pop, summary = checked
    stored = db.scalar(select(func.count()).select_from(CareGapFinding)
                       .where(CareGapFinding.source_system == SOURCE))
    from_counts = sum(counts.get(o, 0) for counts in summary.by_rule_outcome.values()
                      for o in ("overdue", "due", "not_assessable"))
    assert summary.stored_findings == stored == from_counts
    text = format_care_gap_summary(summary)
    assert "DEMONSTRATION RULES" in text
    assert "people checked: 300" in text


def test_report_errors_are_clear(db):
    with pytest.raises(LookupError):
        format_care_gap_person_report(db, "nothing_here", "X-1")
    db.add(Person(source_system="cg_empty", source_record_id="E-1"))
    db.flush()
    assert "care-gap-check" in format_care_gap_person_report(db, "cg_empty", "E-1")


    