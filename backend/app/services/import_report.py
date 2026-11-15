from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.base import ImportOutcome
from app.db.models import ImportRejection


def format_report(db: Session, outcome: ImportOutcome) -> str:
    batch = outcome.batch
    lines = [
        f"Import batch {batch.id}",
        f"  source: {batch.source_system}",
        f"  status: {batch.status.value}",
        f"  {batch.description}",
        f"  rows read {batch.rows_read}, loaded {batch.rows_loaded}, "
        f"skipped (already imported) {batch.rows_skipped}, rejected {batch.rows_rejected}",
        "",
        "By file:",
    ]
    for name, s in outcome.files.items():
        lines.append(f"  {name}: read {s.read}, loaded {s.loaded}, skipped {s.skipped}, rejected {s.rejected}")

    by_reason = db.execute(
        select(ImportRejection.reason_code, func.count())
        .where(ImportRejection.batch_id == batch.id)
        .group_by(ImportRejection.reason_code)
        .order_by(ImportRejection.reason_code)
    ).all()
    if by_reason:
        lines += ["", "Quarantine and skips by reason:"]
        lines += [f"  {code}: {count}" for code, count in by_reason]

        lines += ["", "Details (file, row, reason):"]
        details = db.scalars(
            select(ImportRejection)
            .where(ImportRejection.batch_id == batch.id)
            .order_by(ImportRejection.file_name, ImportRejection.row_number)
        )
        lines += [f"  {r.file_name} row {r.row_number}: {r.reason_code} - {r.reason_detail}" for r in details]
    return "\n".join(lines)