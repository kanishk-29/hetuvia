from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.adapters.base import FileStats
from app.adapters.csv_adapter import CSVAdapter
from app.adapters.synthetic import SyntheticAdapter
from app.db.enums import DataState
from app.db.models import ImportRejection, Observation, Person
from app.services.import_report import format_report

SAMPLE = Path(__file__).resolve().parent.parent / "sample_import"
TODAY = date(2026, 11, 1)
SOURCE = "csv_test"


def load_sample(db):
    return CSVAdapter(SAMPLE, SOURCE, TODAY).load(db)


def people_named(db, source_id):
    return list(db.scalars(select(Person).where(
        Person.source_system == SOURCE, Person.source_record_id == source_id)))


def test_sample_import_counts(db):
    outcome = load_sample(db)
    assert outcome.files["people"] == FileStats(read=9, loaded=4, skipped=0, rejected=5)
    assert outcome.files["encounters"] == FileStats(read=8, loaded=4, skipped=0, rejected=4)
    assert outcome.files["observations"] == FileStats(read=12, loaded=5, skipped=0, rejected=7)
    batch = outcome.batch
    assert (batch.rows_read, batch.rows_loaded, batch.rows_skipped, batch.rows_rejected) == (29, 13, 0, 16)


def test_every_rejection_has_the_expected_reason(db):
    outcome = load_sample(db)
    codes = db.scalars(select(ImportRejection.reason_code).where(
        ImportRejection.batch_id == outcome.batch.id)).all()
    assert Counter(codes) == {
        "bad_date": 2, "future_date": 1, "unknown_status": 2, "missing_value": 2,
        "duplicate_in_file": 3, "unknown_person": 1, "bad_unit": 1,
        "state_value_mismatch": 1, "unknown_encounter": 2, "unknown_type": 1,
    }


def test_duplicate_id_is_rejected_not_merged(db):
    load_sample(db)
    rows = people_named(db, "P-001")
    assert len(rows) == 1
    assert rows[0].date_of_birth == date(2015, 3, 1)  # the later row's 1999 date did not overwrite it


def test_blank_birth_date_is_stored_as_unknown(db):
    load_sample(db)
    person = people_named(db, "P-003")[0]
    assert person.date_of_birth is None
    assert person.family_history_state == DataState.NOT_COLLECTED


def test_unknown_measurement_stores_no_value(db):
    load_sample(db)
    unknown = db.scalars(select(Observation).where(
        Observation.source_system == SOURCE, Observation.source_record_id == "O-005")).one()
    assert unknown.value_numeric is None
    assert unknown.value_state == DataState.UNKNOWN


def test_wrong_unit_row_is_quarantined_not_converted(db):
    load_sample(db)
    loaded = db.scalars(select(Observation).where(
        Observation.source_system == SOURCE, Observation.source_record_id == "O-003")).all()
    assert loaded == []


def test_reimport_skips_without_duplicating(db):
    load_sample(db)
    second = load_sample(db)
    batch = second.batch
    assert (batch.rows_loaded, batch.rows_skipped, batch.rows_rejected) == (0, 13, 16)
    count = db.scalar(select(func.count()).select_from(Person).where(Person.source_system == SOURCE))
    assert count == 4


def test_missing_header_columns_refuse_the_whole_file(db, tmp_path):
    (tmp_path / "people.csv").write_text("source_record_id,area_code\nX-1,AREA-A\n", encoding="utf-8")
    outcome = CSVAdapter(tmp_path, SOURCE, TODAY).load(db)
    assert outcome.files["people"] == FileStats()
    reasons = db.scalars(select(ImportRejection).where(ImportRejection.batch_id == outcome.batch.id)).all()
    assert [(r.reason_code, r.row_number) for r in reasons] == [("missing_columns", 0)]
    assert people_named(db, "X-1") == []


def test_synthetic_source_name_is_reserved():
    with pytest.raises(ValueError):
        CSVAdapter(SAMPLE, "synthetic")


def test_folder_without_files_is_an_error(db, tmp_path):
    with pytest.raises(FileNotFoundError):
        CSVAdapter(tmp_path, SOURCE, TODAY).load(db)


def test_report_shows_counts_and_reasons(db):
    outcome = load_sample(db)
    text = format_report(db, outcome)
    assert "rows read 29, loaded 13" in text
    assert "duplicate_in_file: 3" in text


def test_synthetic_adapter_returns_a_receipt(db):
    adapter = SyntheticAdapter()
    outcome = adapter.load(db)
    assert outcome.batch.rows_loaded == outcome.batch.rows_read > 0
    assert adapter.population.planted["weight_unknown"]