
import argparse
import json
from pathlib import Path

from backend.inventory.diff_engine import compare_inventories
from backend.scraper.snapshot_validator import validate_snapshot


def load_snapshot(path):
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        vehicles = json.load(file)

    validate_snapshot(vehicles)
    return vehicles


def main():
    parser = argparse.ArgumentParser(
        description="Compare two AutoMatch inventory snapshots"
    )

    parser.add_argument("old_snapshot")
    parser.add_argument("new_snapshot")

    args = parser.parse_args()

    old_inventory = load_snapshot(args.old_snapshot)
    new_inventory = load_snapshot(args.new_snapshot)

    result = compare_inventories(
        old_inventory,
        new_inventory,
    )

    print("\n===== INVENTORY CHANGE SUMMARY =====")

    for key, value in result["summary"].items():
        print(f"{key}: {value}")

    print("\n===== ADDED VEHICLES =====")
    for vehicle in result["added"]:
        print(
            vehicle["source_listing_id"],
            vehicle.get("title"),
        )

    print("\n===== REMOVED VEHICLES =====")
    for vehicle in result["removed"]:
        print(
            vehicle["source_listing_id"],
            vehicle.get("title"),
        )

    print("\n===== UPDATED VEHICLES =====")
    for item in result["updated"]:
        print(
            item["source_listing_id"],
            item["changes"],
        )


if __name__ == "__main__":
    main()
