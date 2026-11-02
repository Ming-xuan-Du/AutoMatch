
import json

import pytest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.connection import Base
from backend.database.models import Vehicle
from backend.scraper import scraper as snapshot_writer
from backend.inventory.snapshot_loader import (
    load_certified_snapshot,
)
from backend.inventory.sync_service import sync_inventory


def make_vehicle(cid):
    return {
        "source_listing_id": cid,
        "title": "2020 Toyota RAV4",
        "year": 2020,
        "price_cash": 25000,
        "mileage_km": 80000,
        "listing_url": f"https://example.com/{cid}",
    }


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    yield factory
    engine.dispose()


@pytest.fixture
def temp_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        snapshot_writer,
        "SNAPSHOT_DIR",
        tmp_path,
    )
    return tmp_path


def save_certified(vehicles):
    # Synthetic certified fixtures used only in testing.
    return snapshot_writer.save_snapshot(
        vehicles,
        expected_count=len(vehicles),
        validated=True,
        source_url="https://cccmotors.ca/cars",
    )


def test_snapshot_to_database(db, temp_snapshots):
    path = save_certified([
        make_vehicle("A"),
        make_vehicle("B"),
    ])

    # Step 1: Load saved JSON and metadata.
    snapshot = load_certified_snapshot(path)

    assert len(snapshot.vehicles) == 2
    assert snapshot.is_complete is True

    # Step 2: Synchronize with test database.
    result = sync_inventory(db, snapshot)

    assert result.status == "success"
    assert result.added == 2

    # Step 3: Verify data exists.
    with db() as session:
        vehicles = session.scalars(
            select(Vehicle)
        ).all()

        assert len(vehicles) == 2

    # Step 4: Replay does not duplicate data.
    replay = sync_inventory(db, snapshot)

    assert replay.replayed is True


def test_old_snapshot_without_metadata_rejected(
    temp_snapshots,
):
    path = snapshot_writer.save_snapshot([
        make_vehicle("A"),
    ])

    with pytest.raises(
        ValueError,
        match="Missing completeness metadata",
    ):
        load_certified_snapshot(path)


def test_modified_snapshot_rejected(temp_snapshots):
    path = save_certified([
        make_vehicle("A"),
    ])

    # Modify the JSON after its checksum was recorded.
    path.write_text(
        json.dumps([make_vehicle("CHANGED")]),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="checksum mismatch",
    ):
        load_certified_snapshot(path)


def test_incorrect_metadata_count_rejected(
    temp_snapshots,
):
    path = save_certified([
        make_vehicle("A"),
    ])

    receipt_path = path.with_suffix(".meta.json")

    receipt = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )

    receipt["expected_count"] = 99

    receipt_path.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Inventory count mismatch",
    ):
        load_certified_snapshot(path)
