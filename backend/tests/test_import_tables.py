import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ImportBatch, ImportRejection, Person


def test_duplicate_source_id_in_same_system_is_rejected(db):
    db.add(Person(source_system="csv_import", source_record_id="EXT-1"))
    db.flush()
    db.add(Person(source_system="csv_import", source_record_id="EXT-1"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_source_id_in_different_systems_is_not_merged(db):
    db.add(Person(source_system="system_a", source_record_id="EXT-1"))
    db.add(Person(source_system="system_b", source_record_id="EXT-1"))
    db.flush()
    assert db.query(Person).filter(Person.source_record_id == "EXT-1").count() == 2


def test_rejection_keeps_reason_and_original_row(db):
    batch = ImportBatch(source_system="csv_import")
    db.add(batch)
    db.flush()
    db.add(ImportRejection(
        batch_id=batch.id,
        file_name="people.csv",
        row_number=7,
        reason_code="bad_date",
        reason_detail="date_of_birth '01/02/2020' is not in YYYY-MM-DD format",
        raw_row={"source_record_id": "EXT-9", "date_of_birth": "01/02/2020"},
    ))
    db.flush()
    saved = db.query(ImportRejection).filter(ImportRejection.batch_id == batch.id).one()
    assert saved.reason_code == "bad_date"
    assert saved.raw_row["source_record_id"] == "EXT-9"
