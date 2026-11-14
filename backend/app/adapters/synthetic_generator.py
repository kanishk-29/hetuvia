"""Seeded generator for one linked, fictional population. Demonstration data only."""

import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from app.db.enums import (
    ConditionContext,
    ConditionStatus,
    DataState,
    EncounterStatus,
    PersonStatus,
    RelationshipType,
    ScreeningStatus,
    Verification,
)
from app.db.models import (
    Condition,
    Encounter,
    FamilyRelationship,
    Observation,
    Person,
    ScreeningEvent,
)

SOURCE = "synthetic"
REFERENCE_DATE = date(2026, 11, 1)  # fixed on purpose: "today" must not change the population
HISTORY_START = date(2021, 1, 1)
STALE_CUTOFF = REFERENCE_DATE - timedelta(days=730)
RECORDED_AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "hetuvia.synthetic")

# The answer key: every kind of hole the generator can plant.
PLANTED_KINDS = (
    "weight_unknown",
    "height_not_collected",
    "stale_bp",
    "completed_screening_no_date",
    "screening_due_date_unknown",
    "family_history_unknown",
    "family_history_not_collected",
    "no_encounters",
    "missing_dob",
    "missing_language",
)


@dataclass
class Population:
    seed: int
    people: list[Person] = field(default_factory=list)
    relationships: list[FamilyRelationship] = field(default_factory=list)
    encounters: list[Encounter] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    screenings: list[ScreeningEvent] = field(default_factory=list)
    true_birth_dates: dict[uuid.UUID, date] = field(default_factory=dict)
    planted: dict[str, list[uuid.UUID]] = field(default_factory=dict)

    def plant(self, kind: str, person_id: uuid.UUID) -> None:
        found = self.planted.setdefault(kind, [])
        if person_id not in found:
            found.append(person_id)


def _age_years(born: date, on: date) -> int:
    return (on - born).days // 365


def _prov(record_id: str | None = None) -> dict:
    return {
        "source_system": SOURCE,
        "source_record_id": record_id,
        "recorded_at": RECORDED_AT,
        "verification": Verification.VERIFIED,
    }


class _Builder:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.pop = Population(seed=seed)
        for kind in PLANTED_KINDS:
            self.pop.planted[kind] = []
        self._counters: dict[str, int] = {}
        self._relatives: dict[uuid.UUID, list[uuid.UUID]] = {}

    def new_id(self, kind: str) -> uuid.UUID:
        n = self._counters.get(kind, 0) + 1
        self._counters[kind] = n
        return uuid.uuid5(NAMESPACE, f"{self.seed}:{kind}:{n}")

    # ---------- households and people ----------

    def build(self, total: int) -> Population:
        rng = self.rng
        while len(self.pop.people) < total:
            remaining = total - len(self.pop.people)
            n_children = rng.choice([0, 0, 1, 2, 2, 3])
            n_adults = rng.choice([1, 2, 2, 2, 2])
            while n_adults + n_children > remaining:
                if n_children > 0:
                    n_children -= 1
                else:
                    n_adults -= 1
            self._household(n_adults, n_children, f"AREA-{rng.choice('ABCDE')}")

        for person in list(self.pop.people):
            self._history(person)

        for person in self.pop.people:  # demographic gaps are applied last, after history is built
            if rng.random() < 0.03:
                person.date_of_birth = None
                self.pop.plant("missing_dob", person.person_id)
            if rng.random() < 0.04:
                person.preferred_language = None
                self.pop.plant("missing_language", person.person_id)
        return self.pop

    def _person(self, age_days: int, area: str) -> Person:
        person_id = self.new_id("person")
        born = REFERENCE_DATE - timedelta(days=age_days)
        person = Person(
            person_id=person_id,
            date_of_birth=born,
            sex_recorded=self.rng.choice(["female", "male"]),
            preferred_language=self.rng.choice(["en", "ar", "hi", "ur"]),
            area_code=area,
            status=PersonStatus.ACTIVE,
            family_history_state=DataState.NOT_COLLECTED,
            **_prov(f"SYN-{self._counters['person']:04d}"),
        )
        self.pop.true_birth_dates[person_id] = born
        self.pop.people.append(person)
        self._relatives[person_id] = []
        return person

    def _household(self, n_adults: int, n_children: int, area: str) -> None:
        rng = self.rng
        low, high = (35, 65) if n_children else (19, 80)
        adults = [
            self._person(rng.randint(low * 365, high * 365 + 364), area) for _ in range(n_adults)
        ]
        children = [self._person(rng.randint(30, 18 * 365 - 1), area) for _ in range(n_children)]

        for child in children:
            for adult in adults:
                self._link(child, adult, RelationshipType.PARENT)  # adult is the parent of child
                self._link(adult, child, RelationshipType.CHILD)
        if len(adults) == 2:
            self._link(adults[0], adults[1], RelationshipType.SPOUSE)
            self._link(adults[1], adults[0], RelationshipType.SPOUSE)
        for i, first in enumerate(children):
            for second in children[i + 1 :]:
                self._link(first, second, RelationshipType.SIBLING)
                self._link(second, first, RelationshipType.SIBLING)

    def _link(self, person: Person, related: Person, kind: RelationshipType) -> None:
        self.pop.relationships.append(
            FamilyRelationship(
                id=self.new_id("relationship"),
                person_id=person.person_id,
                related_person_id=related.person_id,
                relationship_type=kind,
                **_prov(),
            )
        )
        self._relatives[person.person_id].append(related.person_id)

    # ---------- per-person history ----------

    def _history(self, person: Person) -> None:
        rng = self.rng
        born = self.pop.true_birth_dates[person.person_id]
        is_adult = _age_years(born, REFERENCE_DATE) >= 18
        stale_bp_person = is_adult and rng.random() < 0.10

        self._family_history(person)
        self._personal_condition(person, born, is_adult)

        bp_dates: list[date] = []
        for encounter in self._encounters(person, born):
            if encounter.status == EncounterStatus.COMPLETED:
                self._observations(person, encounter, born, stale_bp_person, bp_dates)
        if stale_bp_person and bp_dates:
            self.pop.plant("stale_bp", person.person_id)  # only old readings exist

        self._screenings(person, born, is_adult)

    def _family_history(self, person: Person) -> None:
        rng = self.rng
        roll = rng.random()
        if roll < 0.55:
            state = DataState.PRESENT
        elif roll < 0.85:
            state = DataState.EXPLICITLY_ABSENT
        elif roll < 0.93:
            state = DataState.UNKNOWN
            self.pop.plant("family_history_unknown", person.person_id)
        else:
            state = DataState.NOT_COLLECTED
            self.pop.plant("family_history_not_collected", person.person_id)
        person.family_history_state = state

        if state == DataState.PRESENT:
            relatives = self._relatives[person.person_id]
            for _ in range(rng.randint(1, 2)):
                code = rng.choice(["DEMO-F01", "DEMO-F02", "DEMO-F03"])
                self.pop.conditions.append(
                    Condition(
                        id=self.new_id("condition"),
                        person_id=person.person_id,
                        related_person_id=rng.choice(relatives) if relatives else None,
                        context=ConditionContext.FAMILY_HISTORY,
                        condition_code=code,
                        condition_label=f"Demo family history {code[-2:]}",
                        status=ConditionStatus.ACTIVE,
                        **_prov(),
                    )
                )

    def _personal_condition(self, person: Person, born: date, is_adult: bool) -> None:
        rng = self.rng
        if rng.random() < (0.35 if is_adult else 0.10):
            code = rng.choice(["DEMO-C01", "DEMO-C02", "DEMO-C03"])
            self.pop.conditions.append(
                Condition(
                    id=self.new_id("condition"),
                    person_id=person.person_id,
                    related_person_id=None,
                    context=ConditionContext.PERSONAL,
                    condition_code=code,
                    condition_label=f"Demo condition {code[-2:]}",
                    status=rng.choice(
                        [ConditionStatus.ACTIVE, ConditionStatus.ACTIVE, ConditionStatus.RESOLVED]
                    ),
                    onset_date=born + timedelta(days=rng.randint(0, (REFERENCE_DATE - born).days)),
                    **_prov(),
                )
            )

    def _encounters(self, person: Person, born: date) -> list[Encounter]:
        rng = self.rng
        if rng.random() < 0.05:
            self.pop.plant("no_encounters", person.person_id)
            return []
        start = max(born, HISTORY_START)
        span = (REFERENCE_DATE - start).days
        days = sorted(start + timedelta(days=rng.randint(0, span)) for _ in range(rng.randint(1, 8)))
        made: list[Encounter] = []
        for day in days:
            age = _age_years(born, day)
            well_child = age < 18 and rng.random() < (0.5 if age < 5 else 0.3)
            encounter = Encounter(
                id=self.new_id("encounter"),
                person_id=person.person_id,
                encounter_type="demo_well_child_visit" if well_child else "demo_clinic_visit",
                encounter_date=day,
                status=rng.choices(
                    [EncounterStatus.COMPLETED, EncounterStatus.NO_SHOW, EncounterStatus.CANCELLED],
                    weights=[85, 8, 7],
                )[0],
                **_prov(),
            )
            self.pop.encounters.append(encounter)
            made.append(encounter)
        return made

    def _observations(
        self, person: Person, encounter: Encounter, born: date, stale_bp_person: bool, bp_dates: list[date]
    ) -> None:
        rng = self.rng
        day = encounter.encounter_date
        age = _age_years(born, day)
        at = datetime.combine(day, time(9, 0), tzinfo=UTC)

        if age < 18:
            height = 50 + 6.5 * age + rng.uniform(-4, 4)
            weight = 3.5 + 3.0 * age + rng.uniform(-1.5, 1.5)
        else:
            height = rng.uniform(150, 190)
            weight = rng.uniform(50, 100)

        self._add_obs(person, encounter, at, "height", height, "cm", 0.06,
                      DataState.NOT_COLLECTED, "height_not_collected")
        self._add_obs(person, encounter, at, "weight", weight, "kg", 0.08,
                      DataState.UNKNOWN, "weight_unknown")

        if age >= 18:
            systolic = rng.uniform(95, 150)
            if stale_bp_person and day >= STALE_CUTOFF:
                return  # this person only has old blood-pressure readings
            self._add_obs(person, encounter, at, "systolic_blood_pressure", systolic, "mmHg", 0.0,
                          DataState.UNKNOWN, "")
            bp_dates.append(day)

    def _add_obs(self, person, encounter, at, kind, value, unit, gap_rate, gap_state, plant_kind) -> None:
        if self.rng.random() < gap_rate:
            number, unit_value, state = None, None, gap_state
            self.pop.plant(plant_kind, person.person_id)
        else:
            number, unit_value, state = Decimal(f"{value:.1f}"), unit, DataState.PRESENT
        self.pop.observations.append(
            Observation(
                id=self.new_id("observation"),
                person_id=person.person_id,
                encounter_id=encounter.id,
                observation_type=kind,
                value_numeric=number,
                unit=unit_value,
                value_state=state,
                observed_at=at,
                **_prov(),
            )
        )

    def _screenings(self, person: Person, born: date, is_adult: bool) -> None:
        rng = self.rng
        kind = "demo_adult_screening" if is_adult else "demo_well_child_visit"
        earliest = max(born + timedelta(days=30), date(2024, 1, 1))
        latest = REFERENCE_DATE + timedelta(days=90)
        for _ in range(rng.randint(1, 3)):
            due = earliest + timedelta(days=rng.randint(0, (latest - earliest).days))
            status = rng.choices(
                [ScreeningStatus.COMPLETED, ScreeningStatus.PENDING,
                 ScreeningStatus.DECLINED, ScreeningStatus.MISSED],
                weights=[55, 25, 8, 12],
            )[0]
            completed_on = None
            if status == ScreeningStatus.COMPLETED:
                completed_on = min(due + timedelta(days=rng.randint(-20, 30)), REFERENCE_DATE)
                if rng.random() < 0.06:
                    completed_on = None
                    self.pop.plant("completed_screening_no_date", person.person_id)
            due_stored = due
            if rng.random() < 0.05:
                due_stored = None
                self.pop.plant("screening_due_date_unknown", person.person_id)
            self.pop.screenings.append(
                ScreeningEvent(
                    id=self.new_id("screening"),
                    person_id=person.person_id,
                    screening_type=kind,
                    due_date=due_stored,
                    result_status=status,
                    completed_on=completed_on,
                    **_prov(),
                )
            )


def generate_population(seed: int = 42, total_people: int = 300) -> Population:
    return _Builder(seed).build(total_people)