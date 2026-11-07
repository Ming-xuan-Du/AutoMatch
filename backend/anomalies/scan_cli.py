
"""Controlled AutoMatch anomaly scanning CLI.

Usage:
    python -m backend.anomalies.scan_cli
    python -m backend.anomalies.scan_cli --no-model
    python -m backend.anomalies.scan_cli --apply

Default mode is read-only preview.
Only --apply commits anomaly findings.
"""

import argparse

from sqlalchemy import text

from backend.anomalies.scan_service import (
    run_anomaly_scan,
)
from backend.database.connection import SessionLocal


# Dedicated transaction lock for AutoMatch anomaly scans.
ADVISORY_LOCK_KEY = 820083620260806


def _print_summary(summary, *, applied: bool):
    print("\n=== AUTOMATCH ANOMALY SCAN ===")

    print(
        "Mode:",
        "APPLIED" if applied else "DRY RUN",
    )

    print("Vehicles checked:", summary.vehicles_checked)

    print(
        "Audit records checked:",
        summary.audit_records_checked,
    )

    print("Rule findings:", summary.rule_findings)
    print("ML findings:", summary.model_findings)

    print(
        "Created:" if applied else "Would create:",
        summary.created,
    )

    print(
        "Previously seen findings:",
        summary.seen_again,
    )

    print(
        "Orphan change findings skipped:",
        summary.orphan_change_findings,
    )

    print("Model status:", summary.model_status)

    if summary.model_message:
        print("Model warning:", summary.model_message)

    if applied:
        print("\nAnomaly findings committed.")
    else:
        print("\nPreview complete. No changes saved.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Preview or apply AutoMatch anomaly findings."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit findings to PostgreSQL.",
    )

    parser.add_argument(
        "--no-model",
        action="store_true",
        help="Run deterministic rules only.",
    )

    args = parser.parse_args(argv)

    with SessionLocal() as session:
        try:
            is_postgresql = (
                session.get_bind().dialect.name
                == "postgresql"
            )

            if args.apply:
                if is_postgresql:
                    acquired = session.execute(
                        text(
                            "SELECT "
                            "pg_try_advisory_xact_lock(:key)"
                        ),
                        {"key": ADVISORY_LOCK_KEY},
                    ).scalar_one()

                    if not acquired:
                        raise RuntimeError(
                            "Another anomaly scan is "
                            "currently applying findings"
                        )

            elif is_postgresql:
                # Database-level protection for preview.
                session.execute(
                    text("SET TRANSACTION READ ONLY")
                )

            summary = run_anomaly_scan(
                session,
                include_model=not args.no_model,
                dry_run=not args.apply,
            )

            if args.apply:
                session.commit()
            else:
                session.rollback()

        except Exception:
            session.rollback()
            raise

    _print_summary(
        summary,
        applied=args.apply,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
