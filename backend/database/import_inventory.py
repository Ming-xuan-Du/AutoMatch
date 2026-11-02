
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from backend.database.connection import SessionLocal
from backend.database.models import Vehicle, InventorySnapshot
from backend.inventory.change_service import (
    load_inventory,
    record_inventory_changes,
)
from backend.scraper.snapshot_validator import validate_snapshot


VEHICLE_FIELDS = (
    "title", "year", "price_cash", "price_finance",
    "mileage_km", "exterior_color", "stock_no",
    "doors", "body_style", "transmission",
    "drivetrain", "engine", "vin",
    "listing_url", "image_url",
)


def inventory_fingerprint(vehicles):
    """Hash inventory content independent of vehicle ordering."""
    normalized = sorted(
        vehicles,
        key=lambda item: str(item["source_listing_id"]),
    )
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def import_inventory(snapshot_path):
    path = Path(snapshot_path).resolve()
    vehicles = load_inventory(path)

    # Never write invalid inventory into the database.
    validate_snapshot(vehicles)

    now = datetime.now(timezone.utc)
    fingerprint = inventory_fingerprint(vehicles)

    with SessionLocal.begin() as session:
        previous_snapshots = session.scalars(
            select(InventorySnapshot)
            .order_by(InventorySnapshot.id.desc())
        ).all()

        previous_inventory = None

        # Find the latest usable historical snapshot.
        for previous in previous_snapshots:
            if not previous.source_file:
                continue

            previous_path = Path(previous.source_file)

            if not previous_path.exists():
                continue

            try:
                candidate = load_inventory(previous_path)
                validate_snapshot(candidate)
            except (OSError, ValueError, TypeError):
                continue

            previous_inventory = candidate
            break

        # The first import has no historical baseline.
        if previous_inventory is not None:
            if inventory_fingerprint(previous_inventory) == fingerprint:
                print("Identical inventory already imported.")
                print("Skipping duplicate snapshot.")
                return {
                    "skipped": True,
                    "total": len(vehicles),
                }

        snapshot = InventorySnapshot(
            scraped_at=now,
            total_vehicles=len(vehicles),
            source_file=str(path),
        )
        session.add(snapshot)
        session.flush()

        change_result = None

        if previous_inventory is not None:
            change_result = record_inventory_changes(
                session=session,
                old_inventory=previous_inventory,
                new_inventory=vehicles,
                snapshot_id=snapshot.id,
            )

        added = 0
        updated = 0
        unchanged = 0

        for data in vehicles:
            listing_id = str(data["source_listing_id"])

            vehicle = session.scalar(
                select(Vehicle).where(
                    Vehicle.source_listing_id == listing_id
                )
            )

            if vehicle is None:
                vehicle = Vehicle(
                    source_listing_id=listing_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    is_active=True,
                    **{
                        field: data.get(field)
                        for field in VEHICLE_FIELDS
                    },
                )
                session.add(vehicle)
                added += 1
            else:
                changed = False

                for field in VEHICLE_FIELDS:
                    new_value = data.get(field)
                    if getattr(vehicle, field) != new_value:
                        setattr(vehicle, field, new_value)
                        changed = True

                vehicle.last_seen_at = now
                vehicle.is_active = True

                if changed:
                    updated += 1
                else:
                    unchanged += 1

    print("Inventory import completed!")
    print(f"Added: {added}")
    print(f"Updated: {updated}")
    print(f"Unchanged: {unchanged}")
    print(f"Total: {len(vehicles)}")

    if change_result is not None:
        print("\nInventory changes:")
        for key, value in change_result["summary"].items():
            print(f"{key}: {value}")

    return {
        "skipped": False,
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "total": len(vehicles),
        "changes": change_result,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m backend.database.import_inventory "
            "<snapshot.json>"
        )

    import_inventory(sys.argv[1])
