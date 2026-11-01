
import pytest

from backend.scraper.snapshot_validator import (
    validate_snapshot,
    SnapshotValidationError,
)


@pytest.fixture
def valid_vehicle():
    return {
        "source_listing_id": "637089",
        "title": "2023 Mercedes-Benz G-Class",
        "year": 2023,
        "price_cash": 217880,
        "price_finance": 215880,
        "mileage_km": 51818,
        "listing_url": (
            "https://cccmotors.ca/cars/used/example"
        ),
        "exterior_color": "Black",
    }


def test_valid_snapshot(valid_vehicle):
    result = validate_snapshot([valid_vehicle])
    assert len(result) == 1


def test_empty_snapshot():
    with pytest.raises(SnapshotValidationError):
        validate_snapshot([])


def test_duplicate_vehicle_id(valid_vehicle):
    vehicles = [
        valid_vehicle,
        valid_vehicle.copy(),
    ]

    with pytest.raises(
        SnapshotValidationError,
        match="duplicate"
    ):
        validate_snapshot(vehicles)


def test_missing_vehicle_id(valid_vehicle):
    valid_vehicle["source_listing_id"] = None

    with pytest.raises(SnapshotValidationError):
        validate_snapshot([valid_vehicle])


def test_missing_title(valid_vehicle):
    valid_vehicle["title"] = None

    with pytest.raises(SnapshotValidationError):
        validate_snapshot([valid_vehicle])


def test_negative_price(valid_vehicle):
    valid_vehicle["price_cash"] = -100

    with pytest.raises(SnapshotValidationError):
        validate_snapshot([valid_vehicle])


def test_negative_mileage(valid_vehicle):
    valid_vehicle["mileage_km"] = -500

    with pytest.raises(SnapshotValidationError):
        validate_snapshot([valid_vehicle])


def test_invalid_listing_url(valid_vehicle):
    valid_vehicle["listing_url"] = "invalid-url"

    with pytest.raises(SnapshotValidationError):
        validate_snapshot([valid_vehicle])


def test_expected_count_mismatch(valid_vehicle):
    with pytest.raises(SnapshotValidationError):
        validate_snapshot(
            [valid_vehicle],
            expected_count=219,
        )


def test_optional_field_missing(valid_vehicle):
    valid_vehicle["exterior_color"] = None

    result = validate_snapshot([valid_vehicle])

    assert len(result) == 1


def test_missing_cash_price_allowed(valid_vehicle):
    valid_vehicle["price_cash"] = None
    valid_vehicle["price_finance"] = 139988

    result = validate_snapshot([valid_vehicle])

    assert len(result) == 1



def test_both_prices_missing(valid_vehicle):
    valid_vehicle["price_cash"] = None
    valid_vehicle["price_finance"] = None

    result = validate_snapshot([valid_vehicle])

    assert len(result) == 1
    assert result[0]["price_cash"] is None
    assert result[0]["price_finance"] is None
