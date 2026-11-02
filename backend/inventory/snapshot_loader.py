import hashlib
import json
from pathlib import Path

from backend.inventory.sync_service import (
    InventorySnapshot,
)


EXPECTED_SOURCE = "https://cccmotors.ca/cars"


def load_certified_snapshot(path):
    """
    Load a saved crawl only if its completeness
    metadata and checksum are valid.

    This function does not modify the database.
    """

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Snapshot not found: {path}"
        )

    receipt_path = path.with_suffix(".meta.json")

    if not receipt_path.is_file():
        raise ValueError(
            "Missing completeness metadata. "
            "This snapshot cannot be safely applied."
        )

    content = path.read_bytes()

    vehicles = json.loads(
        content.decode("utf-8")
    )

    receipt = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )

    if not isinstance(vehicles, list):
        raise ValueError(
            "Snapshot root must be a list"
        )

    if not isinstance(receipt, dict):
        raise ValueError(
            "Invalid metadata structure"
        )

    # Verify the snapshot has not changed.
    actual_hash = hashlib.sha256(
        content
    ).hexdigest()

    if actual_hash != receipt.get("snapshot_sha256"):
        raise ValueError(
            "Snapshot checksum mismatch"
        )

    if receipt.get("schema_version") != 1:
        raise ValueError(
            "Unsupported metadata version"
        )

    if receipt.get("source_url") != EXPECTED_SOURCE:
        raise ValueError(
            "Unexpected inventory source"
        )

    if receipt.get("crawl_id") != path.stem:
        raise ValueError(
            "Snapshot ID does not match filename"
        )

    if receipt.get("validation_passed") is not True:
        raise ValueError(
            "Snapshot validation was not confirmed"
        )

    if receipt.get("is_complete") is not True:
        raise ValueError(
            "Snapshot is marked incomplete"
        )

    expected_count = receipt.get("expected_count")

    if (
        type(expected_count) is not int
        or expected_count <= 0
        or len(vehicles) != expected_count
        or receipt.get("vehicle_count") != expected_count
    ):
        raise ValueError(
            "Inventory count mismatch"
        )

    if (
        receipt.get("pages_expected") != 1
        or receipt.get("pages_seen") != 1
    ):
        raise ValueError(
            "Unexpected pagination metadata"
        )

    # Check every listing identifier before syncing.
    seen_ids = set()

    for index, vehicle in enumerate(vehicles):
        if not isinstance(vehicle, dict):
            raise ValueError(
                f"Invalid vehicle at index {index}"
            )

        listing_id = str(
            vehicle.get("source_listing_id") or ""
        ).strip()

        if not listing_id:
            raise ValueError(
                f"Missing listing ID at index {index}"
            )

        if listing_id in seen_ids:
            raise ValueError(
                f"Duplicate listing ID: {listing_id}"
            )

        seen_ids.add(listing_id)

    return InventorySnapshot(
        snapshot_id=receipt["crawl_id"],
        vehicles=vehicles,
        pages_expected=1,
        pages_seen=1,
        is_complete=True,
        source_file=str(path.resolve()),
    )
