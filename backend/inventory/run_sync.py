import argparse
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.database import connection
from backend.database.models import Vehicle
from backend.inventory.snapshot_loader import (
    load_certified_snapshot,
)
from backend.inventory.sync_service import sync_inventory


def get_engine():
    engine = getattr(connection, "engine", None)

    if engine is None:
        factory = getattr(
            connection,
            "SessionLocal",
            None,
        )

        if factory is not None:
            engine = factory.kw.get("bind")

    if engine is None:
        raise RuntimeError(
            "Cannot locate database engine"
        )

    return engine


def show_unverified_preview(path, error):
    """
    Display basic information about an old snapshot.
    Unverified files are never applied.
    """

    print("\nUNVERIFIED SNAPSHOT")
    print(f"Reason: {error}")
    print("Database modifications are disabled.")

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            print(f"Vehicle records: {len(data)}")
    except (OSError, UnicodeError, ValueError):
        print("Could not read snapshot contents.")


def main():
    parser = argparse.ArgumentParser(
        description="AutoMatch Inventory Sync"
    )

    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Path to saved inventory JSON",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply a certified snapshot to PostgreSQL",
    )

    args = parser.parse_args()
    path = args.snapshot

    print("\nAutoMatch Inventory Synchronization")
    print("-" * 45)
    print(f"Snapshot: {path}")

    # First check whether the file is certified.
    try:
        snapshot = load_certified_snapshot(path)
    except (OSError, UnicodeError, ValueError) as exc:
        if args.apply:
            raise SystemExit(
                f"REFUSED: {exc}"
            ) from exc

        show_unverified_preview(path, exc)
        return

    print("Snapshot integrity: VERIFIED")
    print(f"Crawl ID: {snapshot.snapshot_id}")
    print(f"Vehicle count: {len(snapshot.vehicles)}")

    engine = get_engine()

    SessionLocal = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    if not args.apply:
        # Read existing IDs without modifying PostgreSQL.
        incoming_ids = {
            str(vehicle["source_listing_id"])
            for vehicle in snapshot.vehicles
        }

        with SessionLocal() as session:
            existing_ids = set(
                session.scalars(
                    select(Vehicle.source_listing_id)
                ).all()
            )

        print("\nDRY-RUN PREVIEW")
        print(f"Existing DB records: {len(existing_ids)}")

        print(
            "New listing IDs: ",
            len(incoming_ids - existing_ids),
        )

        print(
            "Existing IDs absent from crawl: ",
            len(existing_ids - incoming_ids),
        )

        print(
            "Existing IDs present in crawl: ",
            len(incoming_ids & existing_ids),
        )

        print(
            "\nNo database changes were made."
        )
        print(
            "This preview does not apply the "
            "missing-streak or inventory-drop rules."
        )
        return

    if engine.dialect.name != "postgresql":
        raise SystemExit(
            "REFUSED: --apply requires PostgreSQL"
        )

    print("\nApplying snapshot to PostgreSQL...")

    result = sync_inventory(
        SessionLocal,
        snapshot,
    )

    print("\nSYNC RESULT")
    print("-" * 45)
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Added: {result.added}")
    print(f"Updated: {result.updated}")
    print(f"Unchanged: {result.unchanged}")
    print(
        "Suspected missing: "
        f"{result.suspected_missing}"
    )
    print(f"Deactivated: {result.inactive}")
    print(f"Replayed: {result.replayed}")

    if result.error_detail:
        print(f"Warning: {result.error_detail}")


if __name__ == "__main__":
    main()
