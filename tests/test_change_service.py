
import pytest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.database.connection import Base
from backend.database.models import (
    InventoryChange,
    InventorySnapshot,
)
from backend.inventory.change_service import record_inventory_changes


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        yield db

    engine.dispose()


def test_record_added_removed_updated(session):
    old_inventory = [
        {
            "source_listing_id": "101",
            "title": "2022 BMW 330i",
            "price_cash": 35000,
        },
        {
            "source_listing_id": "102",
            "title": "2021 Mercedes C300",
            "price_cash": 42000,
        },
    ]

    new_inventory = [
        {
            "source_listing_id": "101",
            "title": "2022 BMW 330i",
            "price_cash": 32000,
        },
        {
            "source_listing_id": "103",
            "title": "2023 Lexus IS350",
            "price_cash": 46000,
        },
    ]

    snapshot = InventorySnapshot(total_vehicles=2)
    session.add(snapshot)
    session.flush()

    result = record_inventory_changes(
        session,
        old_inventory,
        new_inventory,
        snapshot.id,
    )

    session.commit()

    assert result["summary"]["added"] == 1
    assert result["summary"]["removed"] == 1
    assert result["summary"]["updated"] == 1

    records = session.scalars(
        select(InventoryChange)
    ).all()

    assert len(records) == 3

    types = {record.change_type for record in records}

    assert types == {"added", "removed", "updated"}

    updated = next(
        record for record in records
        if record.change_type == "updated"
    )

    assert updated.changes["price_cash"] == {
        "old": 35000,
        "new": 32000,
    }


def test_reject_missing_snapshot(session):
    with pytest.raises(ValueError, match="does not exist"):
        record_inventory_changes(
            session, [], [], snapshot_id=999
        )


def test_reject_duplicate_recording(session):
    snapshot = InventorySnapshot(total_vehicles=1)
    session.add(snapshot)
    session.flush()

    record_inventory_changes(
        session,
        [],
        [{"source_listing_id": "101", "title": "BMW"}],
        snapshot.id,
    )

    with pytest.raises(ValueError, match="already recorded"):
        record_inventory_changes(
            session,
            [],
            [{"source_listing_id": "101", "title": "BMW"}],
            snapshot.id,
        )
