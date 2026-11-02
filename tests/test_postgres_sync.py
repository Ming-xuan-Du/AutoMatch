
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.database import connection
from backend.database.models import (
    Vehicle,
    InventorySnapshot as SnapshotRow,
    InventoryChange,
)
from backend.inventory.sync_service import (
    InventorySnapshot,
    sync_inventory,
)


def get_engine():
    engine = getattr(connection, "engine", None)

    if engine is None:
        factory = getattr(
            connection, "SessionLocal", None
        )
        if factory is not None:
            engine = factory.kw.get("bind")

    if engine is None:
        raise RuntimeError(
            "Cannot find PostgreSQL engine. "
            "Check backend/database/connection.py"
        )

    return engine


def test_postgres_sync_with_rollback():
    engine = get_engine()

    # Do not accidentally run against SQLite.
    assert engine.dialect.name == "postgresql"

    unique_id = uuid4().hex
    listing_id = f"TEST-{unique_id}"
    crawl_id = f"pytest-{unique_id}"

    snapshot = InventorySnapshot(
        snapshot_id=crawl_id,
        vehicles=[
            {
                "source_listing_id": listing_id,
                "title": "2020 Toyota RAV4 TEST",
                "year": 2020,
                "price_cash": 25000,
                "mileage_km": 80000,
                "listing_url": (
                    f"https://example.com/{listing_id}"
                ),
            }
        ],
        pages_expected=1,
        pages_seen=1,
        is_complete=True,
    )

    # Open an outer transaction.
    # All changes will be rolled back at the end.
    with engine.connect() as db_connection:
        outer_transaction = db_connection.begin()

        try:
            TestSession = sessionmaker(
                bind=db_connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            # Disable the inventory-drop guard for
            # this isolated integration test only.
            result = sync_inventory(
                TestSession,
                snapshot,
                drop_guard_min_previous=10**9,
            )

            assert result.status == "success"
            assert result.added == 1

            with TestSession() as session:
                vehicle = session.scalar(
                    select(Vehicle).where(
                        Vehicle.source_listing_id
                        == listing_id
                    )
                )

                assert vehicle is not None
                assert vehicle.price_cash == 25000
                assert vehicle.is_active is True

                run = session.scalar(
                    select(SnapshotRow).where(
                        SnapshotRow.crawl_id == crawl_id
                    )
                )

                assert run is not None
                assert run.status == "success"

                change = session.scalar(
                    select(InventoryChange).where(
                        InventoryChange.snapshot_id
                        == result.run_id
                    )
                )

                assert change is not None
                assert change.change_type == "added"

        finally:
            # Undo the entire test, including any
            # temporary changes to existing vehicles.
            outer_transaction.rollback()

    # Confirm the test vehicle was not persisted.
    with engine.connect() as verify_connection:
        remaining = verify_connection.execute(
            select(Vehicle.id).where(
                Vehicle.source_listing_id == listing_id
            )
        ).first()

        assert remaining is None
