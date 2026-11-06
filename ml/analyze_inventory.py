
"""Milestone 7.1: Read-only inventory distribution analysis.

Run:
    python -m ml.analyze_inventory

Uses the existing AutoMatch PostgreSQL connection.
Does not modify database records.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import median

from sqlalchemy import select, text

from backend.database.connection import SessionLocal
from backend.database.models import (
    Vehicle,
    InventorySnapshot,
    InventoryChange,
)


def is_missing(value):
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def percentile(values, fraction):
    """Linear-interpolation percentile for a small dataset."""
    ordered = sorted(values)

    if not ordered:
        return None

    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower

    return (
        ordered[lower] * (1 - weight)
        + ordered[upper] * weight
    )


def print_completeness(all_vehicles, present):
    print("\n=== DATA COMPLETENESS ===")

    fields = [
        "year",
        "price_cash",
        "price_finance",
        "mileage_km",
        "body_style",
        "drivetrain",
        "vin",
    ]

    for field in fields:
        all_missing = sum(
            is_missing(getattr(v, field))
            for v in all_vehicles
        )
        present_missing = sum(
            is_missing(getattr(v, field))
            for v in present
        )

        rate = (
            100 * present_missing / len(present)
            if present else 0
        )

        print(
            f"{field:<18}"
            f"all_missing={all_missing:<4} "
            f"present_missing={present_missing:<4} "
            f"present_rate={rate:.2f}%"
        )

    complete = sum(
        all(
            not is_missing(getattr(v, field))
            for field in (
                "year",
                "price_cash",
                "mileage_km",
                "body_style",
                "drivetrain",
            )
        )
        for v in present
    )

    print(
        "\nPresent vehicles with all five "
        f"core analytical fields: {complete}/{len(present)}"
    )


def print_numeric_distribution(vehicles):
    print("\n=== NUMERIC DISTRIBUTIONS: PRESENT VEHICLES ===")

    for field in ("year", "price_cash", "mileage_km"):
        values = [
            getattr(v, field)
            for v in vehicles
            if getattr(v, field) is not None
        ]

        if not values:
            print(f"{field}: no available values")
            continue

        print(f"\n{field} (n={len(values)})")

        for name, fraction in (
            ("min", 0),
            ("p10", 0.10),
            ("p25", 0.25),
            ("median", 0.50),
            ("p75", 0.75),
            ("p90", 0.90),
            ("max", 1),
        ):
            value = percentile(values, fraction)
            print(f"  {name:<8} {value:,.1f}")


def print_category_distribution(vehicles, field):
    print(f"\n=== {field.upper()} DISTRIBUTION ===")

    counts = Counter(
        str(getattr(v, field)).strip().casefold()
        if not is_missing(getattr(v, field))
        else "<missing>"
        for v in vehicles
    )

    print(f"Distinct categories: {len(counts)}")

    for name, count in counts.most_common():
        print(f"  {name:<25} {count}")


def print_body_style_prices(vehicles):
    print("\n=== CASH PRICES BY BODY STYLE ===")

    groups = defaultdict(list)

    for vehicle in vehicles:
        if vehicle.price_cash is None:
            continue

        body = (
            vehicle.body_style.strip().casefold()
            if vehicle.body_style else "<missing>"
        )

        groups[body].append(vehicle.price_cash)

    for body, prices in sorted(
        groups.items(),
        key=lambda item: -len(item[1]),
    ):
        print(
            f"{body:<25}"
            f"n={len(prices):<4} "
            f"median=${median(prices):,.0f} "
            f"min=${min(prices):,} "
            f"max=${max(prices):,}"
        )

    print(
        "\nNote: Category summaries are descriptive, "
        "not anomaly thresholds."
    )


def print_extremes(vehicles, field, highest=True):
    direction = "HIGHEST" if highest else "LOWEST"

    print(f"\n=== {direction} 5: {field.upper()} ===")

    available = [
        v for v in vehicles
        if getattr(v, field) is not None
    ]

    ordered = sorted(
        available,
        key=lambda v: getattr(v, field),
        reverse=highest,
    )

    for vehicle in ordered[:5]:
        print(
            f"  {vehicle.title[:65]} | "
            f"year={vehicle.year} | "
            f"cash={vehicle.price_cash} | "
            f"mileage={vehicle.mileage_km}"
        )


def print_title_examples(vehicles):
    print("\n=== REPRESENTATIVE TITLE FORMATS ===")

    ordered = sorted(
        vehicles,
        key=lambda v: v.title.casefold(),
    )

    if not ordered:
        return

    step = max(1, len(ordered) // 10)

    for vehicle in ordered[::step][:10]:
        print(f"  {vehicle.title}")


def print_basic_validity(vehicles):
    print("\n=== BASIC VALUE VALIDITY ===")

    current_year = datetime.now(timezone.utc).year

    checks = {
        "nonpositive_cash_price": sum(
            v.price_cash is not None
            and v.price_cash <= 0
            for v in vehicles
        ),
        "negative_mileage": sum(
            v.mileage_km is not None
            and v.mileage_km < 0
            for v in vehicles
        ),
        "future_year_beyond_next": sum(
            v.year is not None
            and v.year > current_year + 1
            for v in vehicles
        ),
    }

    for name, count in checks.items():
        print(f"{name}: {count}")


def print_audit_summary(snapshots, changes):
    print("\n=== INVENTORY SNAPSHOT HISTORY ===")

    for snapshot in snapshots:
        print(
            f"id={snapshot.id} "
            f"status={snapshot.status} "
            f"total={snapshot.total_vehicles} "
            f"added={snapshot.added} "
            f"updated={snapshot.updated} "
            f"unchanged={snapshot.unchanged} "
            f"missing={snapshot.suspected_missing} "
            f"inactive={snapshot.inactive}"
        )

    print("\n=== AUDIT CHANGE TYPES ===")

    counts = Counter(
        change.change_type
        for change in changes
    )

    for name, count in counts.most_common():
        print(f"{name}: {count}")

    print("\n=== AUDIT JSON STRUCTURE ===")

    key_counts = Counter()

    for change in changes:
        if isinstance(change.changes, dict):
            key_counts.update(change.changes.keys())

    for key, count in key_counts.most_common():
        print(f"{key}: {count}")

    print("\nSample audit record structures:")

    for change in changes[:5]:
        payload = change.changes

        if isinstance(payload, dict):
            keys = list(payload.keys())
        else:
            keys = [type(payload).__name__]

        print(
            f"  type={change.change_type}, "
            f"keys={keys}"
        )


def main():
    with SessionLocal() as session:
        try:
            # PostgreSQL read-only transaction.
            session.execute(
                text("SET TRANSACTION READ ONLY")
            )

            all_vehicles = session.scalars(
                select(Vehicle).order_by(Vehicle.id)
            ).all()

            snapshots = session.scalars(
                select(InventorySnapshot)
                .order_by(InventorySnapshot.id)
            ).all()

            changes = session.scalars(
                select(InventoryChange)
                .order_by(InventoryChange.id)
            ).all()

            present = [
                v for v in all_vehicles
                if v.is_active is True
                and v.missing_streak == 0
            ]

            print("=== AUTOMATCH MILESTONE 7.1 ===")
            print(f"Total vehicles: {len(all_vehicles)}")
            print(f"Confirmed-present vehicles: {len(present)}")

            print_completeness(all_vehicles, present)
            print_numeric_distribution(present)

            print_category_distribution(
                present, "body_style"
            )
            print_category_distribution(
                present, "drivetrain"
            )

            print_body_style_prices(present)
            print_extremes(present, "price_cash", True)
            print_extremes(present, "price_cash", False)
            print_extremes(present, "mileage_km", True)
            print_title_examples(present)
            print_basic_validity(present)
            print_audit_summary(snapshots, changes)

        finally:
            session.rollback()

    print("\nRead-only analysis complete.")


if __name__ == "__main__":
    main()
