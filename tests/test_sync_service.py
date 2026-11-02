
import pytest

from sqlalchemy import (
    create_engine,
    select,
    func,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.connection import Base
from backend.database.models import (
    Vehicle,
    InventorySnapshot as SnapshotRow,
    InventoryChange,
)
from backend.inventory.sync_service import (
    InventorySnapshot,
    sync_inventory,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    yield SessionLocal
    engine.dispose()


def car(cid, price=25000):
    return {
        "source_listing_id": cid,
        "title": "2020 Toyota RAV4",
        "year": 2020,
        "price_cash": price,
        "mileage_km": 80000,
        "listing_url": f"https://example.com/{cid}",
    }


def scan(cid, *cars, complete=True):
    return InventorySnapshot(
        snapshot_id=cid,
        vehicles=list(cars),
        pages_expected=1,
        pages_seen=1 if complete else 0,
        is_complete=complete,
    )


def getcar(db, cid):
    with db() as session:
        return session.scalar(
            select(Vehicle).where(
                Vehicle.source_listing_id == cid
            )
        )


def test_add_change_replay(db):
    original = scan("1", car("A"), car("B"))

    first = sync_inventory(db, original)
    assert first.added == 2

    replay = sync_inventory(db, original)
    assert replay.replayed
    assert replay.run_id == first.run_id

    second = sync_inventory(
        db,
        scan("2", car("A", 21000), car("B")),
    )

    assert second.updated == 1
    assert second.unchanged == 1
    assert getcar(db, "A").price_cash == 21000

    with db() as session:
        run_count = session.scalar(
            select(func.count()).select_from(SnapshotRow)
        )
        assert run_count == 2

        events = session.scalars(
            select(InventoryChange).where(
                InventoryChange.change_type == "updated"
            )
        ).all()

        assert len(events) == 1
        assert events[0].changes["price_cash"] == {
            "old": 25000,
            "new": 21000,
        }


def test_missing_and_reappear(db):
    sync_inventory(
        db,
        scan("1", car("A"), car("B")),
    )

    first_missing = sync_inventory(
        db,
        scan("2", car("A")),
    )

    assert first_missing.suspected_missing == 1
    assert getcar(db, "B").is_active
    assert getcar(db, "B").missing_streak == 1

    second_missing = sync_inventory(
        db,
        scan("3", car("A")),
    )

    assert second_missing.inactive == 1
    assert not getcar(db, "B").is_active

    reappeared = sync_inventory(
        db,
        scan("4", car("A"), car("B")),
    )

    assert reappeared.updated == 1
    assert getcar(db, "B").is_active
    assert getcar(db, "B").missing_streak == 0


def test_incomplete_and_empty_protected(db):
    sync_inventory(db, scan("1", car("A")))

    incomplete = sync_inventory(
        db,
        scan("2", complete=False),
    )
    assert incomplete.status == "partial"

    empty = sync_inventory(db, scan("3"))
    assert empty.status == "partial"

    assert getcar(db, "A").is_active
    assert getcar(db, "A").missing_streak == 0


def test_large_drop_protected(db):
    cars = [car(f"C{i}") for i in range(12)]

    sync_inventory(db, scan("1", *cars))

    result = sync_inventory(
        db,
        scan("2", cars[0]),
    )

    assert result.status == "partial"
    assert getcar(db, "C2").missing_streak == 0


def test_distinct_crawls_count_as_new_observations(db):
    sync_inventory(
        db, scan("1", car("A"), car("B"))
    )
    sync_inventory(db, scan("2", car("A")))

    result = sync_inventory(
        db, scan("3", car("A"))
    )

    assert result.inactive == 1


def test_omitted_field_preserves_existing_value(db):
    sync_inventory(db, scan("1", car("A")))

    incomplete_fields = {
        "source_listing_id": "A",
        "title": "2020 Toyota RAV4",
        "listing_url": "https://example.com/A",
    }

    result = sync_inventory(
        db,
        scan("2", incomplete_fields),
    )

    assert result.unchanged == 1
    assert getcar(db, "A").price_cash == 25000


def test_duplicate_listing_ids_rejected(db):
    result = sync_inventory(
        db,
        scan("1", car("A"), car("A")),
    )

    assert result.status == "partial"

    with db() as session:
        count = session.scalar(
            select(func.count()).select_from(Vehicle)
        )
        assert count == 0


def test_crawl_id_with_changed_payload_rejected(db):
    sync_inventory(db, scan("1", car("A")))

    with pytest.raises(
        ValueError,
        match="different contents",
    ):
        sync_inventory(
            db,
            scan("1", car("A", 22000)),
        )

    assert getcar(db, "A").price_cash == 25000
