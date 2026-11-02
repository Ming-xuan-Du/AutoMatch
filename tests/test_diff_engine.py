
# tests/test_diff_engine.py

from backend.inventory.diff_engine import (
    index_vehicles,
    detect_field_changes,
    compare_inventories,
)


def make_vehicle(vehicle_id, price=30000, mileage=50000):
    return {
        "source_listing_id": vehicle_id,
        "title": f"Test Vehicle {vehicle_id}",
        "price_cash": price,
        "price_finance": price - 1000 if price is not None else None,
        "mileage_km": mileage,
    }


def test_index_vehicles():
    vehicles = [
        make_vehicle("101"),
        make_vehicle("102"),
    ]

    result = index_vehicles(vehicles)

    assert len(result) == 2
    assert result["101"]["source_listing_id"] == "101"


def test_detect_price_change():
    old = make_vehicle("101", price=30000)
    new = make_vehicle("101", price=28000)

    changes = detect_field_changes(old, new)

    assert changes["price_cash"]["old"] == 30000
    assert changes["price_cash"]["new"] == 28000


def test_detect_mileage_change():
    old = make_vehicle("101", mileage=50000)
    new = make_vehicle("101", mileage=51000)

    changes = detect_field_changes(old, new)

    assert changes["mileage_km"]["new"] == 51000


def test_no_field_changes():
    vehicle = make_vehicle("101")

    changes = detect_field_changes(vehicle, vehicle.copy())

    assert changes == {}


def test_added_vehicle():
    old = [make_vehicle("101")]
    new = [
        make_vehicle("101"),
        make_vehicle("102"),
    ]

    result = compare_inventories(old, new)

    assert len(result["added"]) == 1
    assert result["added"][0]["source_listing_id"] == "102"


def test_removed_vehicle():
    old = [
        make_vehicle("101"),
        make_vehicle("102"),
    ]
    new = [make_vehicle("101")]

    result = compare_inventories(old, new)

    assert len(result["removed"]) == 1
    assert result["removed"][0]["source_listing_id"] == "102"


def test_updated_vehicle():
    old = [make_vehicle("101", price=30000)]
    new = [make_vehicle("101", price=25000)]

    result = compare_inventories(old, new)

    assert len(result["updated"]) == 1
    assert result["summary"]["updated"] == 1


def test_unchanged_vehicle():
    old = [make_vehicle("101")]
    new = [make_vehicle("101")]

    result = compare_inventories(old, new)

    assert len(result["unchanged"]) == 1
    assert result["summary"]["unchanged"] == 1


def test_complete_inventory_comparison():
    old = [
        make_vehicle("101", price=30000),
        make_vehicle("102", price=40000),
        make_vehicle("103", price=50000),
    ]

    new = [
        make_vehicle("101", price=28000),
        make_vehicle("103", price=50000),
        make_vehicle("104", price=35000),
    ]

    result = compare_inventories(old, new)

    assert result["summary"] == {
        "old_total": 3,
        "new_total": 3,
        "added": 1,
        "removed": 1,
        "updated": 1,
        "unchanged": 1,
    }


def test_missing_price_does_not_remove_vehicle():
    old = [make_vehicle("101", price=30000)]
    new = [make_vehicle("101", price=None)]

    result = compare_inventories(old, new)

    assert len(result["removed"]) == 0
    assert len(result["updated"]) == 1
    assert (
        result["updated"][0]["changes"]["price_cash"]["new"]
        is None
    )


def test_image_change_detected():
    old = make_vehicle("101")
    new = make_vehicle("101")

    old["image_url"] = "https://example.com/old.jpg"
    new["image_url"] = "https://example.com/new.jpg"

    result = compare_inventories(old_inventory=[old], new_inventory=[new])

    assert len(result["updated"]) == 1
    assert "image_url" in result["updated"][0]["changes"]
