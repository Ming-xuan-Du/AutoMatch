
"""Prepare and inspect AutoMatch ML features.

Run:
    python -m ml.prepare_features

This script does not train or save a model.
All database operations are read-only.
"""

from collections import Counter, defaultdict
from statistics import median

from sqlalchemy import select, text

from backend.database.connection import SessionLocal
from backend.database.models import Vehicle

from ml.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_feature_dataset,
)


REFERENCE_YEAR = 2026


def main():
    with SessionLocal() as session:
        try:
            session.execute(
                text("SET TRANSACTION READ ONLY")
            )

            # Fetch all records to account explicitly
            # for inactive and missing-streak exclusions.
            vehicles = session.scalars(
                select(Vehicle)
                .order_by(Vehicle.source_listing_id)
            ).all()

            dataset = build_feature_dataset(
                vehicles,
                reference_year=REFERENCE_YEAR,
            )

        finally:
            session.rollback()

    print("=== AUTOMATCH ML FEATURE PREPARATION ===")
    print(f"Feature version: {FEATURE_VERSION}")
    print(f"Reference year: {dataset.reference_year}")

    print("\n--- Dataset size ---")
    print(f"Input records: {dataset.total_records}")
    print(f"Usable records: {len(dataset.rows)}")
    print(
        "Excluded records: "
        f"{dataset.total_records - len(dataset.rows)}"
    )

    print("\n--- Exclusion reasons ---")
    if not dataset.excluded:
        print("No exclusions.")

    for reason, count in sorted(dataset.excluded.items()):
        print(f"{reason}: {count}")

    print("\n--- Feature columns ---")
    for index, name in enumerate(FEATURE_NAMES):
        print(f"{index}: {name}")

    matrix = dataset.feature_matrix

    if not matrix:
        print("\nNo usable records.")
        return

    print("\n--- Feature ranges ---")

    for index, name in enumerate(FEATURE_NAMES):
        values = [row[index] for row in matrix]

        print(
            f"{name:<20}"
            f"min={min(values):.3f} "
            f"median={median(values):.3f} "
            f"max={max(values):.3f}"
        )

    print("\n--- Vehicle groups ---")

    body_counts = Counter(
        row.body_style for row in dataset.rows
    )

    body_prices = defaultdict(list)

    for row in dataset.rows:
        body_prices[row.body_style].append(
            row.price_cash
        )

    for body, count in body_counts.most_common():
        prices = body_prices[body]

        print(
            f"{body:<20}"
            f"count={count:<4} "
            f"median_cash=${median(prices):,.0f}"
        )

    print("\n--- Dataset validation ---")
    print(f"Feature rows: {len(matrix)}")
    print(f"Feature columns: {len(FEATURE_NAMES)}")

    assert all(
        len(row) == len(FEATURE_NAMES)
        for row in matrix
    ), "Unexpected feature dimensions"

    assert (
        len(dataset.rows) + sum(dataset.excluded.values())
        == dataset.total_records
    ), "Dataset accounting mismatch"

    print("Feature dimensions: valid")
    print("Dataset accounting: valid")
    print("\nFeature preparation complete.")


if __name__ == "__main__":
    main()
