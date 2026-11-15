"""Load documented CSV files into the canonical model.

Every row is checked. Good rows are loaded; bad rows go to the quarantine table with a reason.
Records are matched only by (source system, source ID). Names, birth dates and addresses are never
used to decide that two records are the same person.
"""

import csv
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import FileStats, ImportOutcome
from app.db.enums import ImportStatus, PersonStatus, Verification
from app.db.models import Encounter, ImportBatch, ImportRejection, Observation, Person
from app.services.import_validation import (
    FileKind,
    RejectionReason,
    RowProblem,
    missing_columns,
    validate_encounter_row,
    validate_observation_row,
    validate_person_row,
)

MISSING_COLUMNS_REASON = "missing_columns"
LOADED, SKIPPED, REJECTED = "loaded", "skipped", "rejected"
RowResult = tuple[str, RowProblem | None]


class _ImportRun:
    def __init__(self, db: Session, source_system: str, batch: ImportBatch, today: date) -> None:
        self.db = db
        self.source = source_system
        self.batch = batch
        self.today = today
        self.people: dict[str, uuid.UUID] = {}
        self.encounters: dict[str, tuple[uuid.UUID, uuid.UUID]] = {}  # source id -> (encounter id, person id)
        self.observation_ids: set[str] = set()
        self._preload()

    def _preload(self) -> None:
        """Remember what this source already loaded, so re-imports skip instead of duplicating."""
        s = self.source
        for rid, pid in self.db.execute(
            select(Person.source_record_id, Person.person_id)
            .where(Person.source_system == s, Person.source_record_id.is_not(None))
        ):
            self.people[rid] = pid
        for rid, eid, pid in self.db.execute(
            select(Encounter.source_record_id, Encounter.id, Encounter.person_id)
            .where(Encounter.source_system == s, Encounter.source_record_id.is_not(None))
        ):
            self.encounters[rid] = (eid, pid)
        self.observation_ids = set(self.db.scalars(
            select(Observation.source_record_id)
            .where(Observation.source_system == s, Observation.source_record_id.is_not(None))
        ))

    # ---------- quarantine ----------

    def _record(self, file_name: str, row_number: int, code: str, detail: str, raw: dict) -> None:
        self.db.add(ImportRejection(
            batch_id=self.batch.id, file_name=file_name, row_number=row_number,
            reason_code=code, reason_detail=detail, raw_row=raw,
        ))

    def _reject(self, file_name: str, row_number: int, problems: list[RowProblem], raw: dict) -> None:
        self._record(
            file_name, row_number, problems[0].reason.value,
            "; ".join(p.detail for p in problems), raw,
        )

    # ---------- generic file loop ----------

    def process_file(self, path: Path, kind: FileKind, validator: Callable, loader: Callable) -> FileStats:
        stats = FileStats()
        seen: set[str] = set()
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            header = [name.strip() for name in (reader.fieldnames or [])]
            missing = missing_columns(kind, header)
            if missing:
                self._record(path.name, 0, MISSING_COLUMNS_REASON,
                             f"required columns missing: {', '.join(missing)}",
                             {"header": ", ".join(header)})
                return stats
            reader.fieldnames = header

            for row_number, raw in enumerate(reader, start=2):  # row 1 is the header
                row = {k: v for k, v in raw.items() if k is not None}
                if not any((v or "").strip() for v in row.values()):
                    continue  # a fully blank line
                stats.read += 1
                result = validator(row, self.today)
                if not result.ok:
                    stats.rejected += 1
                    self._reject(path.name, row_number, result.problems, row)
                    continue
                status, problem = loader(result.values, seen)
                if status == LOADED:
                    stats.loaded += 1
                    continue
                if status == SKIPPED:
                    stats.skipped += 1
                else:
                    stats.rejected += 1
                self._reject(path.name, row_number, [problem], row)
        self.db.flush()  # parents must exist before the next file's rows point at them
        return stats

    def _check_key(self, sid: str, seen: set[str], existing) -> RowResult | None:
        if sid in seen:
            return REJECTED, RowProblem(
                RejectionReason.DUPLICATE_IN_FILE,
                f"source_record_id '{sid}' appears more than once in this file; later copies are not merged",
            )
        seen.add(sid)
        if sid in existing:
            return SKIPPED, RowProblem(
                RejectionReason.ALREADY_IMPORTED,
                f"source_record_id '{sid}' was already imported from {self.source}; left unchanged",
            )
        return None

    # ---------- one loader per file ----------

    def load_person(self, values: dict, seen: set[str]) -> RowResult:
        sid = values["source_record_id"]
        early = self._check_key(sid, seen, self.people)
        if early:
            return early
        person = Person(
            person_id=uuid.uuid4(),
            date_of_birth=values["date_of_birth"],
            sex_recorded=values["sex_recorded"],
            preferred_language=values["preferred_language"],
            area_code=values["area_code"],
            status=PersonStatus.ACTIVE,
            family_history_state=values["family_history_state"],
            source_system=self.source, source_record_id=sid,
            recorded_at=None, verification=Verification.REPORTED,
        )
        self.db.add(person)
        self.people[sid] = person.person_id
        return LOADED, None

    def load_encounter(self, values: dict, seen: set[str]) -> RowResult:
        owner = self.people.get(values["person_source_id"])
        if owner is None:
            return REJECTED, RowProblem(
                RejectionReason.UNKNOWN_PERSON,
                f"person_source_id '{values['person_source_id']}' is not a known person from {self.source}",
            )
        sid = values["source_record_id"]
        early = self._check_key(sid, seen, self.encounters)
        if early:
            return early
        encounter_id = uuid.uuid4()
        self.db.add(Encounter(
            id=encounter_id, person_id=owner,
            encounter_type=values["encounter_type"], encounter_date=values["encounter_date"],
            status=values["status"],
            source_system=self.source, source_record_id=sid,
            recorded_at=None, verification=Verification.REPORTED,
        ))
        self.encounters[sid] = (encounter_id, owner)
        return LOADED, None

    def load_observation(self, values: dict, seen: set[str]) -> RowResult:
        owner = self.people.get(values["person_source_id"])
        if owner is None:
            return REJECTED, RowProblem(
                RejectionReason.UNKNOWN_PERSON,
                f"person_source_id '{values['person_source_id']}' is not a known person from {self.source}",
            )
        encounter_id = None
        encounter_sid = values["encounter_source_id"]
        if encounter_sid:
            known = self.encounters.get(encounter_sid)
            if known is None:
                return REJECTED, RowProblem(
                    RejectionReason.UNKNOWN_ENCOUNTER,
                    f"encounter_source_id '{encounter_sid}' is not a known encounter from {self.source}",
                )
            if known[1] != owner:
                return REJECTED, RowProblem(
                    RejectionReason.UNKNOWN_ENCOUNTER,
                    f"encounter '{encounter_sid}' belongs to a different person; it was not re-attached",
                )
            encounter_id = known[0]
        sid = values["source_record_id"]
        early = self._check_key(sid, seen, self.observation_ids)
        if early:
            return early
        self.db.add(Observation(
            id=uuid.uuid4(), person_id=owner, encounter_id=encounter_id,
            observation_type=values["observation_type"],
            value_numeric=values["value"], unit=values["unit"],
            value_state=values["value_state"], observed_at=values["observed_at"],
            source_system=self.source, source_record_id=sid,
            recorded_at=None, verification=Verification.REPORTED,
        ))
        self.observation_ids.add(sid)
        return LOADED, None


def import_csv_directory(
    db: Session, directory: Path, source_system: str = "csv_import", today: date | None = None
) -> ImportOutcome:
    """Import people.csv, encounters.csv and observations.csv (each optional) from a folder.

    Flushes but never commits. If anything unexpected goes wrong the caller's rollback
    undoes the whole import, so there are no half-loaded batches.
    """
    directory = Path(directory)
    today = today or date.today()
    present = [kind for kind in FileKind if (directory / f"{kind.value}.csv").is_file()]
    if not present:
        raise FileNotFoundError(f"No people.csv, encounters.csv or observations.csv found in {directory}")

    batch = ImportBatch(
        source_system=source_system,
        description="csv files: " + ", ".join(f"{k.value}.csv" for k in present),
        status=ImportStatus.RUNNING,
    )
    db.add(batch)
    db.flush()

    run = _ImportRun(db, source_system, batch, today)
    handlers = {
        FileKind.PEOPLE: (validate_person_row, run.load_person),
        FileKind.ENCOUNTERS: (validate_encounter_row, run.load_encounter),
        FileKind.OBSERVATIONS: (validate_observation_row, run.load_observation),
    }
    files: dict[str, FileStats] = {}
    for kind in FileKind:  # order matters: people, then encounters, then observations
        if kind in present:
            validator, loader = handlers[kind]
            files[kind.value] = run.process_file(directory / f"{kind.value}.csv", kind, validator, loader)

    batch.rows_read = sum(s.read for s in files.values())
    batch.rows_loaded = sum(s.loaded for s in files.values())
    batch.rows_skipped = sum(s.skipped for s in files.values())
    batch.rows_rejected = sum(s.rejected for s in files.values())
    batch.status = ImportStatus.COMPLETED
    batch.finished_at = datetime.now(UTC)
    db.flush()
    return ImportOutcome(batch=batch, files=files)