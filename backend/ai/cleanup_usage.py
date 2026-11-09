
"""Safe cleanup of historical AI usage records.

Default behavior is dry run.
Deletion requires an explicit --apply flag.

Only AI usage records older than 45 days whose
leases have expired are eligible for deletion.
"""

import argparse

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.database.connection import SessionLocal
from backend.database.models import AIExtractionAttempt

from backend.database.target_guard import (
    UnsafeDatabaseTarget,
    require_local_write_target,
)


RETENTION_DAYS = 45


class AIUsageCleanupUnavailable(Exception):
    """Cleanup could not be completed safely."""


@dataclass(frozen=True)
class CleanupResult:
    candidates: int
    deleted: int
    applied: bool


def cleanup_ai_usage(
    session_factory,
    *,
    apply: bool = False,
) -> CleanupResult:
    """Preview or delete expired historical usage records.

    Uses the PostgreSQL transaction clock.

    Never deletes:
    - records within the retention period
    - records with an unexpired lease

    The quota table is the only deletion target.
    """

    try:
        with session_factory.begin() as session:
            bind = session.get_bind()

            if bind.dialect.name != "postgresql":
                raise AIUsageCleanupUnavailable(
                    "AI usage cleanup requires PostgreSQL."
                )

            database_now = session.scalar(
                select(func.now())
            )

            cutoff = database_now - timedelta(
                days=RETENTION_DAYS
            )

            conditions = (
                AIExtractionAttempt.created_at < cutoff,
                AIExtractionAttempt.lease_expires_at
                <= database_now,
            )

            candidates = session.scalar(
                select(
                    func.count(AIExtractionAttempt.id)
                ).where(*conditions)
            ) or 0

            deleted = 0

            if apply:
                result = session.execute(
                    delete(AIExtractionAttempt)
                    .where(*conditions)
                )

                deleted = result.rowcount

        return CleanupResult(
            candidates=int(candidates),
            deleted=int(deleted),
            applied=apply,
        )

    except SQLAlchemyError as exc:
        raise AIUsageCleanupUnavailable(
            "AI usage cleanup database operation failed."
        ) from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Clean expired AutoMatch AI usage records."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Delete eligible historical records. "
            "Without this flag, only preview counts."
        ),
    )

    parser.add_argument(
        "--confirm-database",
        help="Exact database name required for --apply.",
    )

    args = parser.parse_args(argv)

    if args.apply:
        try:
            require_local_write_target(
                SessionLocal.kw.get("bind"),
                confirmed_database=args.confirm_database,
            )
        except UnsafeDatabaseTarget as exc:
            print(f"REFUSED: {exc}")
            return 2

    try:
        result = cleanup_ai_usage(
            SessionLocal,
            apply=args.apply,
        )

    except AIUsageCleanupUnavailable as exc:
        print(f"Cleanup unavailable: {exc}")
        return 2

    print("AutoMatch AI Usage Cleanup")
    print(f"Retention: {RETENTION_DAYS} days")

    if result.applied:
        print("Mode: APPLY")
    else:
        print("Mode: DRY RUN")

    print(
        f"Eligible records: {result.candidates}"
    )

    print(
        f"Deleted records: {result.deleted}"
    )

    if not result.applied:
        print(
            "No records were deleted. "
            "Use --apply to execute cleanup."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
