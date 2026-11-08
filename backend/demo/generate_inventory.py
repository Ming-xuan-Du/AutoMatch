
"""Generate deterministic synthetic AutoMatch inventory.

No scraping, network access, or database writes.
All vehicles are fictional demonstration records.
"""

import argparse
import json
from pathlib import Path


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "demo"
    / "synthetic_inventory_v1.json"
)

# Make, model, body style, drivetrain, base price (CAD).
VEHICLE_TEMPLATES = (
    ("Toyota", "RAV4", "SUV", "AWD", 27900),
    ("Honda", "CR-V", "SUV", "AWD", 28500),
    ("Mazda", "CX-5", "SUV", "AWD", 26800),
    ("Subaru", "Forester", "SUV", "AWD", 26500),
    ("Nissan", "Rogue", "SUV", "AWD", 24500),
    ("Toyota", "Corolla", "Sedan", "FWD", 18900),
    ("Honda", "Civic", "Sedan", "FWD", 19500),
    ("Hyundai", "Elantra", "Sedan", "FWD", 17500),
    ("Ford", "Escape", "SUV", "AWD", 23900),
    ("Kia", "Sportage", "SUV", "AWD", 25700),
)

YEARS = (2019, 2020, 2021, 2022, 2023)
PRICE_ADJUSTMENTS = (-5600, -3000, 0, 2600, 4600)
MILEAGES = (115000, 93000, 68000, 48000, 29000)
COLORS = ("White", "Black", "Silver", "Blue", "Red")


def build_demo_inventory() -> dict:
    """Generate 50 repeatable synthetic vehicles."""

    vehicles = []

    for make, model, body, drivetrain, price in (
        VEHICLE_TEMPLATES
    ):
        for variant, year in enumerate(YEARS):
            listing_id = f"DEMO-{len(vehicles) + 1:04d}"

            vehicles.append(
                {
                    "source_listing_id": listing_id,
                    "title": (
                        f"{year} {make} {model} "
                        "(Synthetic Demo)"
                    ),
                    "year": year,
                    "price_cash": (
                        price + PRICE_ADJUSTMENTS[variant]
                    ),
                    "price_finance": None,
                    "mileage_km": MILEAGES[variant],
                    "exterior_color": COLORS[variant],
                    "stock_no": listing_id,
                    "doors": 4,
                    "body_style": body,
                    "transmission": "Automatic",
                    "drivetrain": drivetrain,
                    "engine": None,
                    "vin": None,
                    "listing_url": (
                        "https://example.invalid/"
                        f"automatch/{listing_id.lower()}"
                    ),
                    "image_url": None,
                    "is_active": True,
                    "missing_streak": 0,
                }
            )

    return {
        "dataset_id": "automatch-synthetic-v1",
        "schema_version": 1,
        "is_synthetic": True,
        "description": (
            "Fictional vehicles for the AutoMatch "
            "portfolio demonstration. "
            "Not actual dealership inventory."
        ),
        "vehicles": vehicles,
    }


def serialize_demo_inventory() -> str:
    return (
        json.dumps(
            build_demo_inventory(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic AutoMatch inventory."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the generated JSON file.",
    )

    args = parser.parse_args(argv)
    payload = serialize_demo_inventory()
    count = len(build_demo_inventory()["vehicles"])

    print("AutoMatch Synthetic Inventory")
    print(f"Dataset: automatch-synthetic-v1")
    print(f"Vehicles: {count}")
    print(f"Output: {args.output}")

    if not args.write:
        print("DRY RUN: No file was written.")
        return 0

    if args.output.exists():
        existing = args.output.read_text(
            encoding="utf-8"
        )

        if existing != payload:
            raise SystemExit(
                "REFUSED: existing output differs. "
                "No file was overwritten."
            )

        print("Existing output is identical.")
        return 0

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        payload,
        encoding="utf-8",
    )

    print("Synthetic inventory file created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
