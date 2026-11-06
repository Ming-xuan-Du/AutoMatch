
"""Read-only exploratory profile of the AutoMatch inventory.

Run from the repository root:
    python -m ml.explore_inventory

No database records are inserted, updated, or deleted.
"""

from sqlalchemy import String, func, select

from backend.database.connection import SessionLocal
from backend.database.models import (
    Vehicle,
    InventorySnapshot,
    InventoryChange,
)


PROFILE_FIELDS = (
    "source_listing_id",
    "title",
    "year",
    "price_cash",
    "price_finance",
    "mileage_km",
    "body_style",
    "drivetrain",
    "vin",
    "stock_no",
    "listing_url",
)

NUMERIC_FIELDS = (
    "year",
    "price_cash",
    "price_finance",
    "mileage_km",
)


def print_schema(model):
    """Display columns from the real SQLAlchemy model."""
    table = model.__table__

    print(f"\nTABLE: {table.name}")

    for column in table.columns:
        print(
            f"  {column.name:<25}"
            f"{str(column.type):<20}"
            f"nullable={column.nullable}"
        )


def count_rows(connection, table):
    return connection.execute(
        select(func.count()).select_from(table)
    ).scalar_one()


def profile_missing_values(connection, table, total):
    print("\n--- Vehicle missing values ---")

    for name in PROFILE_FIELDS:
        if name not in table.c:
            print(f"{name:<20} NOT IN SCHEMA")
            continue

        column = table.c[name]

        null_count = connection.execute(
            select(func.count())
            .select_from(table)
            .where(column.is_(None))
        ).scalar_one()

        blank_count = 0

        if isinstance(column.type, String):
            blank_count = connection.execute(
                select(func.count())
                .select_from(table)
                .where(func.trim(column) == "")
            ).scalar_one()

        missing_count = null_count + blank_count
        percentage = (
            100.0 * missing_count / total
            if total
            else 0.0
        )

        print(
            f"{name:<20}"
            f"missing={missing_count:<6}"
            f"rate={percentage:.2f}%"
        )


def profile_numeric_ranges(connection, table):
    print("\n--- Numeric value ranges ---")

    for name in NUMERIC_FIELDS:
        if name not in table.c:
            continue

        column = table.c[name]

        row = connection.execute(
            select(
                func.count(column),
                func.min(column),
                func.max(column),
            ).select_from(table)
        ).one()

        print(
            f"{name:<20}"
            f"non_null={row[0]} "
            f"min={row[1]} "
            f"max={row[2]}"
        )


def profile_inventory_status(connection, table):
    print("\n--- Inventory status ---")

    required = {"is_active", "missing_streak"}

    if not required.issubset(table.c.keys()):
        print("Expected status columns not found.")
        return

    statement = (
        select(
            table.c.is_active,
            table.c.missing_streak,
            func.count().label("count"),
        )
        .select_from(table)
        .group_by(
            table.c.is_active,
            table.c.missing_streak,
        )
        .order_by(
            table.c.is_active,
            table.c.missing_streak,
        )
    )

    for row in connection.execute(statement):
        print(
            f"is_active={row.is_active}, "
            f"missing_streak={row.missing_streak}, "
            f"count={row.count}"
        )

    present_count = connection.execute(
        select(func.count())
        .select_from(table)
        .where(
            table.c.is_active.is_(True),
            table.c.missing_streak == 0,
        )
    ).scalar_one()

    print(f"\nConfirmed-present vehicles: {present_count}")


def profile_duplicates(connection, table):
    print("\n--- Source listing ID duplicates ---")

    if "source_listing_id" not in table.c:
        print("Source listing ID column not found.")
        return

    column = table.c.source_listing_id

    duplicate_groups = (
        select(column)
        .where(column.is_not(None))
        .group_by(column)
        .having(func.count() > 1)
        .subquery()
    )

    duplicate_count = connection.execute(
        select(func.count()).select_from(duplicate_groups)
    ).scalar_one()

    print(f"Duplicate listing ID groups: {duplicate_count}")


def main():
    with SessionLocal() as session:
        connection = session.connection()

        # PostgreSQL enforces read-only behavior
        # for this transaction.
        connection.exec_driver_sql(
            "SET TRANSACTION READ ONLY"
        )

        try:
            print("=== AUTOMATCH INVENTORY EXPLORATION ===")

            for model in (
                Vehicle,
                InventorySnapshot,
                InventoryChange,
            ):
                print_schema(model)

                total = count_rows(
                    connection,
                    model.__table__,
                )

                print(f"Total rows: {total}")

            vehicle_table = Vehicle.__table__
            vehicle_total = count_rows(
                connection,
                vehicle_table,
            )

            profile_inventory_status(
                connection,
                vehicle_table,
            )

            profile_missing_values(
                connection,
                vehicle_table,
                vehicle_total,
            )

            profile_numeric_ranges(
                connection,
                vehicle_table,
            )

            profile_duplicates(
                connection,
                vehicle_table,
            )

        finally:
            session.rollback()

    print("\nRead-only exploration complete.")


if __name__ == "__main__":
    main()
