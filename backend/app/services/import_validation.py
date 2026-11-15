"""Row-level checks for imported files. Pure functions: no database, no side effects."""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from app.db.enums import DataState, EncounterStatus


class FileKind(str, Enum):
    PEOPLE = "people"
    ENCOUNTERS = "encounters"
    OBSERVATIONS = "observations"


# Every listed column must exist in the file's header. Individual cells may be blank where noted below.
REQUIRED_COLUMNS: dict[FileKind, tuple[str, ...]] = {
    FileKind.PEOPLE: (
        "source_record_id", "date_of_birth", "sex_recorded",
        "preferred_language", "area_code", "family_history_state",
    ),
    FileKind.ENCOUNTERS: (
        "source_record_id", "person_source_id", "encounter_type", "encounter_date", "status",
    ),
    FileKind.OBSERVATIONS: (
        "source_record_id", "person_source_id", "encounter_source_id",
        "observation_type", "value", "unit", "value_state", "observed_at",
    ),
}

# Accepted units are checked, never converted. Silent conversion is how health data goes quietly wrong.
ALLOWED_UNITS = {"height": "cm", "weight": "kg", "systolic_blood_pressure": "mmHg"}
EARLIEST_PLAUSIBLE_DATE = date(1900, 1, 1)
LARGEST_ACCEPTED_VALUE = Decimal("1000000")  # a column-size guard, not a clinical threshold
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RejectionReason(str, Enum):
    MISSING_VALUE = "missing_value"
    BAD_DATE = "bad_date"
    FUTURE_DATE = "future_date"
    UNKNOWN_STATUS = "unknown_status"
    UNKNOWN_TYPE = "unknown_type"
    BAD_NUMBER = "bad_number"
    BAD_UNIT = "bad_unit"
    STATE_VALUE_MISMATCH = "state_value_mismatch"
    DUPLICATE_IN_FILE = "duplicate_in_file"  # used by the importer in Part B
    UNKNOWN_PERSON = "unknown_person"  # used by the importer in Part B
    UNKNOWN_ENCOUNTER = "unknown_encounter"  # used by the importer in Part B
    ALREADY_IMPORTED = "already_imported"  # used by the importer in Part B


@dataclass(frozen=True)
class RowProblem:
    reason: RejectionReason
    detail: str


@dataclass
class ValidationResult:
    values: dict[str, object] = field(default_factory=dict)
    problems: list[RowProblem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, reason: RejectionReason, detail: str) -> None:
        self.problems.append(RowProblem(reason, detail))


def missing_columns(kind: FileKind, header: list[str]) -> list[str]:
    return [column for column in REQUIRED_COLUMNS[kind] if column not in header]


# ---------- small helpers ----------

def _text(row: dict[str, str | None], key: str) -> str:
    return (row.get(key) or "").strip()


def _require(row: dict[str, str | None], key: str, result: ValidationResult) -> str:
    text = _text(row, key)
    if not text:
        result.add(RejectionReason.MISSING_VALUE, f"{key} is required")
    return text


def _parse_date(text: str, label: str, today: date, result: ValidationResult) -> date | None:
    if not _ISO_DATE.match(text):
        result.add(RejectionReason.BAD_DATE, f"{label} '{text}' is not in YYYY-MM-DD format")
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        result.add(RejectionReason.BAD_DATE, f"{label} '{text}' is not a real calendar date")
        return None
    if parsed > today:
        result.add(RejectionReason.FUTURE_DATE, f"{label} {text} is in the future")
        return None
    if parsed < EARLIEST_PLAUSIBLE_DATE:
        result.add(RejectionReason.BAD_DATE, f"{label} {text} is implausibly early")
        return None
    return parsed


def _parse_choice(text: str, enum_cls: type[Enum], label: str, result: ValidationResult):
    allowed = [member.value for member in enum_cls]
    if text not in allowed:
        result.add(
            RejectionReason.UNKNOWN_STATUS,
            f"{label} '{text}' is not one of: {', '.join(allowed)}",
        )
        return None
    return enum_cls(text)


# ---------- one validator per file ----------

def validate_person_row(row: dict[str, str | None], today: date) -> ValidationResult:
    result = ValidationResult()
    result.values["source_record_id"] = _require(row, "source_record_id", result)

    dob_text = _text(row, "date_of_birth")
    # A blank date of birth means "unknown". It is stored as unknown, never guessed.
    result.values["date_of_birth"] = (
        _parse_date(dob_text, "date_of_birth", today, result) if dob_text else None
    )
    result.values["sex_recorded"] = _text(row, "sex_recorded") or None
    result.values["preferred_language"] = _text(row, "preferred_language") or None
    result.values["area_code"] = _text(row, "area_code") or None

    state_text = _text(row, "family_history_state")
    if not state_text:
        result.add(
            RejectionReason.MISSING_VALUE,
            "family_history_state must be explicit (for example 'unknown' or 'not_collected'), never blank",
        )
        result.values["family_history_state"] = None
    else:
        result.values["family_history_state"] = _parse_choice(
            state_text, DataState, "family_history_state", result
        )
    return result


def validate_encounter_row(row: dict[str, str | None], today: date) -> ValidationResult:
    result = ValidationResult()
    result.values["source_record_id"] = _require(row, "source_record_id", result)
    result.values["person_source_id"] = _require(row, "person_source_id", result)
    result.values["encounter_type"] = _require(row, "encounter_type", result)

    date_text = _require(row, "encounter_date", result)
    result.values["encounter_date"] = (
        _parse_date(date_text, "encounter_date", today, result) if date_text else None
    )
    status_text = _require(row, "status", result)
    result.values["status"] = (
        _parse_choice(status_text, EncounterStatus, "status", result) if status_text else None
    )
    return result


def validate_observation_row(row: dict[str, str | None], today: date) -> ValidationResult:
    result = ValidationResult()
    result.values["source_record_id"] = _require(row, "source_record_id", result)
    result.values["person_source_id"] = _require(row, "person_source_id", result)
    result.values["encounter_source_id"] = _text(row, "encounter_source_id") or None

    obs_type = _require(row, "observation_type", result)
    if obs_type and obs_type not in ALLOWED_UNITS:
        result.add(
            RejectionReason.UNKNOWN_TYPE,
            f"observation_type '{obs_type}' is not one of: {', '.join(ALLOWED_UNITS)}",
        )
    result.values["observation_type"] = obs_type

    state_text = _require(row, "value_state", result)
    state = _parse_choice(state_text, DataState, "value_state", result) if state_text else None
    result.values["value_state"] = state

    value_text, unit = _text(row, "value"), _text(row, "unit")
    value: Decimal | None = None
    if state == DataState.PRESENT:
        if not value_text:
            result.add(RejectionReason.MISSING_VALUE, "value is required when value_state is 'present'")
        else:
            try:
                value = Decimal(value_text)
            except InvalidOperation:
                result.add(RejectionReason.BAD_NUMBER, f"value '{value_text}' is not a number")
            else:
                if not value.is_finite() or value <= 0 or value >= LARGEST_ACCEPTED_VALUE:
                    result.add(RejectionReason.BAD_NUMBER, f"value '{value_text}' is not an acceptable positive number")
                    value = None
        expected = ALLOWED_UNITS.get(obs_type)
        if expected and unit != expected:
            result.add(
                RejectionReason.BAD_UNIT,
                f"unit '{unit}' is not accepted for {obs_type}; expected '{expected}' (no conversion is done)",
            )
    elif state is not None and value_text:
        result.add(
            RejectionReason.STATE_VALUE_MISMATCH,
            f"value must be blank when value_state is '{state.value}'",
        )
    result.values["value"] = value
    result.values["unit"] = unit or None if state == DataState.PRESENT else None

    observed_text = _text(row, "observed_at")
    observed: datetime | None = None
    if observed_text:
        try:
            observed = datetime.fromisoformat(observed_text)
        except ValueError:
            result.add(RejectionReason.BAD_DATE, f"observed_at '{observed_text}' is not an ISO date or datetime")
        else:
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            if observed.date() > today:
                result.add(RejectionReason.FUTURE_DATE, f"observed_at {observed_text} is in the future")
            elif observed.date() < EARLIEST_PLAUSIBLE_DATE:
                result.add(RejectionReason.BAD_DATE, f"observed_at {observed_text} is implausibly early")
    result.values["observed_at"] = observed
    return result