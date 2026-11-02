
# backend/inventory/diff_engine.py

TRACKED_FIELDS = (
    "title",
    "year",
    "price_cash",
    "price_finance",
    "mileage_km",
    "exterior_color",
    "stock_no",
    "doors",
    "body_style",
    "transmission",
    "drivetrain",
    "engine",
    "vin",
    "listing_url",
    "image_url",
)


def index_vehicles(vehicles):
    """
    Index vehicles using source_listing_id.
    """
    return {
        vehicle["source_listing_id"]: vehicle
        for vehicle in vehicles
    }


def detect_field_changes(old_vehicle, new_vehicle):
    """
    Return changed fields with their old and new values.
    """
    changes = {}

    for field in TRACKED_FIELDS:
        old_value = old_vehicle.get(field)
        new_value = new_vehicle.get(field)

        if old_value != new_value:
            changes[field] = {
                "old": old_value,
                "new": new_value,
            }

    return changes


def compare_inventories(old_inventory, new_inventory):
    """
    Compare two inventory snapshots.

    Returns added, removed, updated and unchanged vehicles.
    """
    old_index = index_vehicles(old_inventory)
    new_index = index_vehicles(new_inventory)

    old_ids = set(old_index.keys())
    new_ids = set(new_index.keys())

    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    common_ids = old_ids & new_ids

    added = [
        new_index[vehicle_id]
        for vehicle_id in sorted(added_ids)
    ]

    removed = [
        old_index[vehicle_id]
        for vehicle_id in sorted(removed_ids)
    ]

    updated = []
    unchanged = []

    for vehicle_id in sorted(common_ids):
        old_vehicle = old_index[vehicle_id]
        new_vehicle = new_index[vehicle_id]

        changes = detect_field_changes(
            old_vehicle,
            new_vehicle,
        )

        if changes:
            updated.append({
                "source_listing_id": vehicle_id,
                "vehicle": new_vehicle,
                "changes": changes,
            })
        else:
            unchanged.append(new_vehicle)

    return {
        "added": added,
        "removed": removed,
        "updated": updated,
        "unchanged": unchanged,
        "summary": {
            "old_total": len(old_inventory),
            "new_total": len(new_inventory),
            "added": len(added),
            "removed": len(removed),
            "updated": len(updated),
            "unchanged": len(unchanged),
        },
    }
