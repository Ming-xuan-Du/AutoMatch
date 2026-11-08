
"""Tests for synthetic portfolio inventory."""

import json

import pytest

from backend.database.models import Vehicle
from backend.demo.generate_inventory import (
    build_demo_inventory,
    main,
    serialize_demo_inventory,
)


def test_demo_has_50_unique_vehicles():
    data = build_demo_inventory()
    vehicles = data["vehicles"]

    assert data["is_synthetic"] is True
    assert len(vehicles) == 50

    ids = [
        vehicle["source_listing_id"]
        for vehicle in vehicles
    ]

    assert len(ids) == len(set(ids))
    assert all(value.startswith("DEMO-") for value in ids)


def test_demo_records_match_vehicle_schema():
    data = build_demo_inventory()

    model_columns = {
        column.name
        for column in Vehicle.__table__.columns
    }

    for vehicle in data["vehicles"]:
        assert set(vehicle).issubset(model_columns)

        assert vehicle["is_active"] is True
        assert vehicle["missing_streak"] == 0

        assert vehicle["vin"] is None
        assert vehicle["image_url"] is None

        assert "Synthetic Demo" in vehicle["title"]
        assert vehicle["listing_url"].startswith(
            "https://example.invalid/"
        )

        assert vehicle["price_cash"] > 0
        assert vehicle["mileage_km"] >= 0


def test_demo_has_useful_matching_examples():
    vehicles = build_demo_inventory()["vehicles"]

    assert any(
        "Toyota RAV4" in vehicle["title"]
        and vehicle["body_style"] == "SUV"
        and vehicle["drivetrain"] == "AWD"
        and vehicle["price_cash"] <= 30000
        and vehicle["year"] >= 2020
        for vehicle in vehicles
    )

    assert any(
        "Honda Civic" in vehicle["title"]
        and vehicle["body_style"] == "Sedan"
        for vehicle in vehicles
    )

    assert len({
        vehicle["body_style"]
        for vehicle in vehicles
    }) >= 2

    assert len({
        vehicle["year"]
        for vehicle in vehicles
    }) == 5


def test_generator_is_deterministic_and_safe(
    tmp_path,
):
    output = tmp_path / "synthetic.json"

    # Default mode never creates a file.
    assert main(["--output", str(output)]) == 0
    assert not output.exists()

    # Explicit write creates deterministic JSON.
    assert main([
        "--output", str(output), "--write"
    ]) == 0

    first_content = output.read_text(
        encoding="utf-8"
    )

    assert first_content == serialize_demo_inventory()

    data = json.loads(first_content)
    assert len(data["vehicles"]) == 50

    # Running again must not change the output.
    assert main([
        "--output", str(output), "--write"
    ]) == 0

    assert output.read_text(
        encoding="utf-8"
    ) == first_content

    # Refuse to overwrite different existing data.
    output.write_text(
        "existing important content",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="REFUSED"):
        main([
            "--output", str(output), "--write"
        ])

    assert output.read_text(
        encoding="utf-8"
    ) == "existing important content"
