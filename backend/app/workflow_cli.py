import argparse
import uuid
from datetime import date

from app.adapters.synthetic_generator import REFERENCE_DATE
from app.db.session import get_session_factory
from app.services.recommendation_runner import format_recommendation_summary, run_recommendations
from app.services.review import ReviewError, review_recommendation


def _date_arg(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as problem:
        raise argparse.ArgumentTypeError(f"invalid date '{text}': expected YYYY-MM-DD") from problem


def _uuid_arg(text: str) -> uuid.UUID:
    try:
        return uuid.UUID(text)
    except ValueError as problem:
        raise argparse.ArgumentTypeError(
            f"invalid recommendation id '{text}': expected a UUID such as 0f14e45f-ceea-467f-a1d5-9876543210ab"
        ) from problem


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.workflow_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    recommend = sub.add_parser("recommend", help="Turn stored findings into proposed pathways for review")
    recommend.add_argument("--source", default="synthetic")
    recommend.add_argument("--date", type=_date_arg, help="Evaluation date, YYYY-MM-DD")

    review = sub.add_parser("review", help="Record a reviewer's decision on one recommendation")
    review.add_argument("recommendation_id", type=_uuid_arg)
    review.add_argument("--decision", required=True, choices=["approve", "defer", "reject"])
    review.add_argument("--reviewer", required=True)
    review.add_argument("--note", default="")
    args = parser.parse_args()

    with get_session_factory()() as db:
        if args.command == "recommend":
            if args.date is not None:
                evaluated_on = args.date
            else:
                evaluated_on = REFERENCE_DATE if args.source == "synthetic" else date.today()
            summary = run_recommendations(db, args.source, evaluated_on)
            db.commit()
            print(format_recommendation_summary(summary))
        else:
            try:
                rec = review_recommendation(db, args.recommendation_id, args.decision,
                                            args.reviewer, args.note)
            except (LookupError, ReviewError) as problem:
                raise SystemExit(str(problem))
            db.commit()
            print(f"Recommendation {rec.id} is now {rec.status.value} (reviewer: {rec.reviewer_name}).")


if __name__ == "__main__":
    main()