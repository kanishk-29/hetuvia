import argparse
from datetime import date
from pathlib import Path

from app.adapters.csv_adapter import CSVAdapter
from app.adapters.synthetic import SyntheticAdapter
from app.adapters.synthetic_generator import REFERENCE_DATE
from app.db.session import get_session_factory
from app.services.dq_report import format_person_report, format_summary
from app.services.dq_runner import run_quality_check
from app.services.import_report import format_report
from app.services.seed import reset_source


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="Load the synthetic population")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--people", type=int, default=300)

    imp = sub.add_parser("import-csv", help="Import people/encounters/observations CSV files from a folder")
    imp.add_argument("directory")
    imp.add_argument("--source", default="csv_import")

    check = sub.add_parser("quality-check", help="Run the data-quality rules and store the findings")
    check.add_argument("--source", default="synthetic")
    check.add_argument("--date", help="Evaluation date, YYYY-MM-DD (synthetic data defaults to its fixed reference date)")

    report = sub.add_parser("quality-report", help="Show one person's fields and findings")
    report.add_argument("person", help="The person's source record ID, for example SYN-0007")
    report.add_argument("--source", default="synthetic")

    reset = sub.add_parser("reset-source", help="Delete everything loaded by one source system")
    reset.add_argument("name")

    sub.add_parser("reset-synthetic", help="Delete all synthetic records")
    args = parser.parse_args()

    with get_session_factory()() as db:
        if args.command == "seed":
            adapter = SyntheticAdapter(args.seed, args.people)
            outcome = adapter.load(db)
            db.commit()
            counts = ", ".join(f"{s.loaded} {name}" for name, s in outcome.files.items())
            print(f"Seeded seed={args.seed}: {counts}")
            for kind, ids in adapter.population.planted.items():
                print(f"  planted {kind}: {len(ids)} people")
        elif args.command == "import-csv":
            outcome = CSVAdapter(Path(args.directory), args.source).load(db)
            db.commit()
            print(format_report(db, outcome))
        elif args.command == "quality-check":
            if args.date:
                evaluated_on = date.fromisoformat(args.date)
            else:
                evaluated_on = REFERENCE_DATE if args.source == "synthetic" else date.today()
            summary = run_quality_check(db, args.source, evaluated_on)
            db.commit()
            print(format_summary(summary))
        elif args.command == "quality-report":
            try:
                print(format_person_report(db, args.source, args.person))
            except LookupError as problem:
                raise SystemExit(str(problem))
        elif args.command == "reset-source":
            reset_source(db, args.name)
            db.commit()
            print(f"Deleted everything loaded by source '{args.name}'.")
        else:
            reset_source(db, "synthetic")
            db.commit()
            print("Synthetic records deleted.")


if __name__ == "__main__":
    main()
