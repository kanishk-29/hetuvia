from datetime import timedelta

from sqlalchemy import func, select

from app.adapters.synthetic_generator import PLANTED_KINDS, REFERENCE_DATE, _age_years, generate_population
from app.db.enums import ConditionContext, DataState
from app.db.models import Condition, Person
from app.services.care_gap_engine import age_in_years
from app.services.rule_loader import load_rules
from app.services.seed import seed_database


def snapshot(pop):
    return (
        sorted((str(p.person_id), p.date_of_birth, p.sex_recorded, p.preferred_language,
                p.area_code, p.family_history_state.value) for p in pop.people),
        sorted((str(e.id), str(e.person_id), e.encounter_date, e.status.value) for e in pop.encounters),
        sorted((str(o.id), str(o.person_id), o.observation_type, o.value_numeric,
                o.value_state.value) for o in pop.observations),
        sorted((str(s.id), str(s.person_id), s.due_date, s.completed_on,
                s.result_status.value) for s in pop.screenings),
    )


def test_same_seed_gives_same_population():
    assert snapshot(generate_population(42)) == snapshot(generate_population(42))


def test_different_seed_gives_different_population():
    assert snapshot(generate_population(42)) != snapshot(generate_population(43))


def test_size_and_child_share():
    pop = generate_population(42)
    assert len(pop.people) == 300
    cutoff = REFERENCE_DATE - timedelta(days=18 * 365)
    children = [born for born in pop.true_birth_dates.values() if born > cutoff]
    assert 0.30 <= len(children) / 300 <= 0.50


def test_every_record_points_to_a_real_person():
    pop = generate_population(42)
    ids = {p.person_id for p in pop.people}
    assert all(r.person_id in ids and r.related_person_id in ids for r in pop.relationships)
    for rows in (pop.encounters, pop.observations, pop.screenings, pop.conditions):
        assert all(r.person_id in ids for r in rows)
    encounter_ids = {e.id for e in pop.encounters}
    assert all(o.encounter_id in encounter_ids for o in pop.observations)


def test_every_planted_gap_type_exists():
    pop = generate_population(42)
    for kind in PLANTED_KINDS:
        assert pop.planted[kind], f"no people planted for {kind}"


def test_generated_ages_and_screening_types_match_the_rules():
    pop = generate_population(42)
    rules = load_rules()
    born_by_id = {p.person_id: p.date_of_birth for p in pop.people}
    for person in pop.people:
        if person.date_of_birth is not None:
            assert _age_years(person.date_of_birth, REFERENCE_DATE) == age_in_years(
                person.date_of_birth, REFERENCE_DATE
            )
    for screening in pop.screenings:
        born = born_by_id[screening.person_id]
        if born is None:
            continue
        age = age_in_years(born, REFERENCE_DATE)
        assert any(
            rule.service_type == screening.screening_type
            and rule.min_age_years <= age <= rule.max_age_years
            for rule in rules
        )


def test_seed_loads_into_database_and_repeats_cleanly(db):
    seed_database(db)
    first = db.scalar(select(func.count()).select_from(Person).where(Person.source_system == "synthetic"))
    seed_database(db)
    second = db.scalar(select(func.count()).select_from(Person).where(Person.source_system == "synthetic"))
    assert first == second == 300


def test_unknown_family_history_is_never_stored_as_none(db):
    pop = seed_database(db)
    unknown_ids = pop.planted["family_history_unknown"]
    people = db.scalars(select(Person).where(Person.person_id.in_(unknown_ids))).all()
    assert len(people) == len(unknown_ids)
    assert all(p.family_history_state == DataState.UNKNOWN for p in people)
    entries = db.scalar(
        select(func.count()).select_from(Condition).where(
            Condition.person_id.in_(unknown_ids),
            Condition.context == ConditionContext.FAMILY_HISTORY,
        )
    )
    assert entries == 0