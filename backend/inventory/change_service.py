
import json
from pathlib import Path

from sqlalchemy import select

from backend.database.models import InventoryChange, InventorySnapshot
from backend.inventory.diff_engine import compare_inventories


def load_inventory(path):
    """Load a JSON inventory snapshot."""
    with Path(path).open("r", encoding="utf-8") as file:
        vehicles = json.load(file)

    if not isinstance(vehicles, list):
        raise ValueError("Inventory snapshot must contain a list")

    return vehicles


def record_inventory_changes(
    session,
    old_inventory,
    new_inventory,
    snapshot_id,
):
    """Compare inventories and persist change records."""
    snapshot = session.get(InventorySnapshot, snapshot_id)

    if snapshot is None:
        raise ValueError(f"Snapshot {snapshot_id} does not exist")

    existing = session.scalar(
        select(InventoryChange.id)
        .where(InventoryChange.snapshot_id == snapshot_id)
        .limit(1)
    )

    if existing is not None:
        raise ValueError(
            f"Changes already recorded for snapshot {snapshot_id}"
        )

    result = compare_inventories(old_inventory, new_inventory)
    records = []

    for vehicle in result["added"]:
        records.append(
            InventoryChange(
                snapshot_id=snapshot_id,
                source_listing_id=vehicle["source_listing_id"],
                change_type="added",
                changes={"new": vehicle},
            )
        )

    for vehicle in result["removed"]:
        records.append(
            InventoryChange(
                snapshot_id=snapshot_id,
                source_listing_id=vehicle["source_listing_id"],
                change_type="removed",
                changes={"old": vehicle},
            )
        )

    for item in result["updated"]:
        records.append(
            InventoryChange(
                snapshot_id=snapshot_id,
                source_listing_id=item["source_listing_id"],
                change_type="updated",
                changes=item["changes"],
            )
        )

    session.add_all(records)
    session.flush()

    return result
