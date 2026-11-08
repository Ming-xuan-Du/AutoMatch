
"""Safely initialize a dedicated AutoMatch demo database.

Never intended for the local production-like inventory DB.
Requires explicit target confirmation and --apply.
"""

import argparse
import hashlib
import json
import os

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from backend.database.connection import (
    SessionLocal,
    engine,
)
from backend.database.models import (
    AIExtractionAttempt,
    AnomalyFlag,
    AnomalyReviewEvent,
    InventoryChange,
    InventorySnapshot,
    Vehicle,
)
from backend.demo.generate_inventory import (
    build_demo_inventory,
)


DEMO_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "demo"
    / "synthetic_inventory_v1.json"
)

SEED_LOCK_KEY = 7534726519001

CHECKED_TABLES = (
    Vehicle,
    InventorySnapshot,
    InventoryChange,
    AnomalyFlag,
    AnomalyReviewEvent,
    AIExtractionAttempt,
)


class DemoSeedRefused(Exception):
    """Safety requirements for demo seeding were not met."""


@dataclass(frozen=True)
class SeedResult:
    vehicle_count: int
    applied: bool


def load_demo_data():
    """Accept only the checked-in deterministic demo dataset."""

    content = DEMO_FILE.read_bytes()
    payload = json.loads(content)

    if payload != build_demo_inventory():
        raise DemoSeedRefused(
            "Synthetic dataset differs from its generator."
        )

    return (
        payload["vehicles"],
        hashlib.sha256(content).hexdigest(),
    )


def verify_demo_target(url, confirmed_name):
    """Refuse local or unconfirmed database targets."""

    if os.getenv("AUTOMATCH_DEMO_SEED_ALLOWED") != "1":
        raise DemoSeedRefused(
            "Demo database seeding is not enabled."
        )

    database = url.database or ""
    host = (url.host or "").lower()

    if (
        database != confirmed_name
        or "demo" not in database.lower()
        or not database
    ):
        raise DemoSeedRefused(
            "Database name confirmation failed."
        )

    if host in {
        "",
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise DemoSeedRefused(
            "Local database targets are not allowed."
        )

    if not url.drivername.startswith("postgresql"):
        raise DemoSeedRefused(
            "A PostgreSQL database is required."
        )


def seed_demo_database(
    session_factory,
    *,
    apply=False,
):
    """Preview or atomically insert the demo dataset.

    The target must have no existing application records.
    The function never deletes or updates existing data.

    CLI target authorization is performed separately.
    """

    vehicles, payload_hash = load_demo_data()

    with session_factory.begin() as session:
        if session.get_bind().dialect.name != "postgresql":
            raise DemoSeedRefused(
                "Demo seeding requires PostgreSQL."
            )

        # Serialize simultaneous demo-seeding attempts.
        session.execute(
            text(
                "SELECT pg_advisory_xact_lock(:key)"
            ),
            {"key": SEED_LOCK_KEY},
        )

        for model in CHECKED_TABLES:
            count = session.scalar(
                select(func.count())
                .select_from(model)
            ) or 0

            if count != 0:
                raise DemoSeedRefused(
                    "Target database is not empty. "
                    "No data was changed."
                )

        if apply:
            session.add_all(
                Vehicle(**vehicle)
                for vehicle in vehicles
            )

            session.add(
                InventorySnapshot(
                    total_vehicles=len(vehicles),
                    source_file=(
                        "synthetic:automatch-synthetic-v1"
                    ),
                    crawl_id="automatch-synthetic-v1",
                    payload_hash=payload_hash,
                    status="success",
                    pages_expected=1,
                    pages_seen=1,
                    added=len(vehicles),
                    updated=0,
                    unchanged=0,
                    suspected_missing=0,
                    inactive=0,
                )
            )

    return SeedResult(
        vehicle_count=len(vehicles),
        applied=apply,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Initialize an isolated AutoMatch demo DB."
    )

    parser.add_argument(
        "--confirm-database",
        required=True,
        help="Exact name of the target demo database.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write demo records after all safety checks.",
    )

    args = parser.parse_args(argv)

    try:
        verify_demo_target(
            engine.url,
            args.confirm_database,
        )

        result = seed_demo_database(
            SessionLocal,
            apply=args.apply,
        )

    except (
        DemoSeedRefused,
        SQLAlchemyError,
        OSError,
        ValueError,
    ) as exc:
        if isinstance(exc, DemoSeedRefused):
            print(f"REFUSED: {exc}")
        else:
            print(
                "REFUSED: Demo initialization failed. "
                "Check database configuration and migrations."
            )
        return 2

    print("AutoMatch Demo Database")
    print(
        "Mode:",
        "APPLY" if result.applied else "DRY RUN",
    )
    print("Synthetic vehicles:", result.vehicle_count)

    if result.applied:
        print("Demo inventory initialized successfully.")
    else:
        print("No database changes were made.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
