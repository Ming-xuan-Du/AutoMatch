
from pathlib import Path

import pytest

from backend.scraper.parser import parse_inventory, parse_vehicle


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "fixtures"
    / "inventory_sample.html"
)


@pytest.fixture
def inventory_html():
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parse_three_vehicles(inventory_html):
    vehicles = parse_inventory(inventory_html)

    assert len(vehicles) == 3


def test_vehicle_ids_are_unique(inventory_html):
    vehicles = parse_inventory(inventory_html)

    ids = [v["source_listing_id"] for v in vehicles]

    assert len(ids) == len(set(ids))


def test_first_vehicle_fields(inventory_html):
    vehicles = parse_inventory(inventory_html)

    vehicle = next(
        v for v in vehicles
        if v["source_listing_id"] == "637089"
    )

    assert vehicle["year"] == 2023
    assert vehicle["price_cash"] == 217880
    assert vehicle["price_finance"] == 215880
    assert vehicle["mileage_km"] == 51818
    assert vehicle["body_style"] == "SUV"
    assert vehicle["drivetrain"] == "AWD"
    assert vehicle["doors"] == 4


def test_listing_url(inventory_html):
    vehicles = parse_inventory(inventory_html)

    for vehicle in vehicles:
        assert vehicle["listing_url"] is not None
        assert vehicle["listing_url"].startswith("https://")


def test_empty_inventory():
    with pytest.raises(ValueError, match="No vehicle cards found"):
        parse_inventory("<html><body></body></html>")


def test_missing_vehicle_card():
    with pytest.raises(ValueError, match="Vehicle card not found"):
        parse_vehicle("<div>No vehicle here</div>")


def test_parser_handles_formatted_and_invalid_numbers():
    html = """
    <div id="vehicle-123">
        <a class="inventory_a__title_2"
           href="/vehicles/123">
            2020 Toyota Corolla
        </a>

        <p class="inventory_p__price">
            <span>Cash Price</span>
            <span>$25 900</span>
        </p>

        <p class="inventory_p__price">
            <span>Finance Price</span>
            <span>-$1,000</span>
        </p>

        <div class="inventory_div__cell">
            <p>Odometer</p>
            <p>85 000 km</p>
        </div>
    </div>
    """

    vehicle = parse_vehicle(html)

    assert vehicle["source_listing_id"] == "123"
    assert vehicle["price_cash"] == 25900
    assert vehicle["price_finance"] is None
    assert vehicle["mileage_km"] == 85000
