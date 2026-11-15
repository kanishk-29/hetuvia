from datetime import date

from app.services.import_validation import (
    FileKind,
    RejectionReason,
    missing_columns,
    validate_encounter_row,
    validate_observation_row,
    validate_person_row,
)
from app.db.enums import DataState

TODAY = date(2026, 11, 1)


def good_person(**changes):
    row = {
        "source_record_id": "EXT-1", "date_of_birth": "2015-03-01", "sex_recorded": "female",
        "preferred_language": "en", "area_code": "AREA-A", "family_history_state": "unknown",
    }
    row.update(changes)
    return row


def good_encounter(**changes):
    row = {
        "source_record_id": "ENC-1", "person_source_id": "EXT-1",
        "encounter_type": "demo_clinic_visit", "encounter_date": "2026-05-01", "status": "completed",
    }
    row.update(changes)
    return row


def good_observation(**changes):
    row = {
        "source_record_id": "OBS-1", "person_source_id": "EXT-1", "encounter_source_id": "ENC-1",
        "observation_type": "weight", "value": "20.5", "unit": "kg",
        "value_state": "present", "observed_at": "2026-05-01",
    }
    row.update(changes)
    return row


def reasons(result):
    return {problem.reason for problem in result.problems}


def test_missing_columns_are_reported():
    assert missing_columns(FileKind.PEOPLE, ["source_record_id", "area_code"]) == [
        "date_of_birth", "sex_recorded", "preferred_language", "family_history_state",
    ]


def test_valid_person_row_passes():
    result = validate_person_row(good_person(), TODAY)
    assert result.ok
    assert result.values["family_history_state"] == DataState.UNKNOWN


def test_blank_birth_date_means_unknown_not_an_error():
    result = validate_person_row(good_person(date_of_birth=""), TODAY)
    assert result.ok
    assert result.values["date_of_birth"] is None


def test_future_birth_date_is_rejected():
    assert RejectionReason.FUTURE_DATE in reasons(validate_person_row(good_person(date_of_birth="2027-01-01"), TODAY))


def test_wrong_date_format_is_rejected():
    assert RejectionReason.BAD_DATE in reasons(validate_person_row(good_person(date_of_birth="01/02/2020"), TODAY))


def test_blank_family_history_state_is_rejected():
    assert RejectionReason.MISSING_VALUE in reasons(validate_person_row(good_person(family_history_state=""), TODAY))


def test_unknown_status_word_is_rejected():
    assert RejectionReason.UNKNOWN_STATUS in reasons(validate_person_row(good_person(family_history_state="maybe"), TODAY))


def test_encounter_with_unknown_status_is_rejected():
    assert RejectionReason.UNKNOWN_STATUS in reasons(validate_encounter_row(good_encounter(status="happened"), TODAY))


def test_observation_present_without_value_is_rejected():
    assert RejectionReason.MISSING_VALUE in reasons(validate_observation_row(good_observation(value=""), TODAY))


def test_observation_unknown_with_a_value_is_rejected():
    result = validate_observation_row(good_observation(value_state="unknown"), TODAY)
    assert RejectionReason.STATE_VALUE_MISMATCH in reasons(result)


def test_observation_unknown_with_blank_value_is_accepted():
    result = validate_observation_row(good_observation(value="", unit="", value_state="unknown"), TODAY)
    assert result.ok
    assert result.values["value"] is None


def test_wrong_unit_is_rejected_not_converted():
    result = validate_observation_row(good_observation(value="45", unit="lb"), TODAY)
    assert RejectionReason.BAD_UNIT in reasons(result)


def test_unknown_observation_type_is_rejected():
    result = validate_observation_row(good_observation(observation_type="mystery"), TODAY)
    assert RejectionReason.UNKNOWN_TYPE in reasons(result)