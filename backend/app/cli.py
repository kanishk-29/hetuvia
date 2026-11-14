import argparse

from app.db.session import get_session_factory
from app.services.seed import reset_synthetic, seed_database


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed", help="Load the synthetic population")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--people", type=int, default=300)
    sub.add_parser("reset-synthetic", help="Delete all synthetic records")
    args = parser.parse_args()

    with get_session_factory()() as db:
        if args.command == "seed":
            pop = seed_database(db, seed=args.seed, total_people=args.people)
            db.commit()
            print(f"Seeded seed={args.seed}: {len(pop.people)} people, "
                  f"{len(pop.relationships)} relationships, {len(pop.encounters)} encounters, "
                  f"{len(pop.observations)} observations, {len(pop.conditions)} conditions, "
                  f"{len(pop.screenings)} screenings")
            for kind, ids in pop.planted.items():
                print(f"  planted {kind}: {len(ids)} people")
        else:
            reset_synthetic(db)
            db.commit()
            print("Synthetic records deleted.")


if __name__ == "__main__":
    main()