import argparse
from pathlib import Path

from app.adapters.csv_adapter import CSVAdapter
from app.adapters.synthetic import SyntheticAdapter
from app.db.session import get_session_factory
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
