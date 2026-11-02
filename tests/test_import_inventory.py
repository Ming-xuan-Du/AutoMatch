
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.connection import Base
from backend.database.models import (
    InventoryChange,
    InventorySnapshot,
    Vehicle,
)
import backend.database.import_inventory as importer


def test_inventory_import_records_price_change(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    test_session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        importer,
        "SessionLocal",
        test_session_factory,
    )

    # Use real inventory schema, but synthetic test vehicles.
    original = [
        {
            "source_listing_id": "TEST101",
            "title": "2022 BMW 330i",
            "year": 2022,
            "price_cash": 35000,
            "price_finance": None,
            "mileage_km": 45000,
            "listing_url": "https://example.com/car/101",
        }
    ]

    modified = [
        {
            **original[0],
            "price_cash": 32000,
        }
    ]

    first_file = tmp_path / "first.json"
    second_file = tmp_path / "second.json"

    first_file.write_text(json.dumps(original), encoding="utf-8")
    second_file.write_text(json.dumps(modified), encoding="utf-8")

    try:
        importer.import_inventory(first_file)
        importer.import_inventory(second_file)

        with Session(engine) as session:
            snapshots = session.scalars(
                select(InventorySnapshot)
            ).all()

            changes = session.scalars(
                select(InventoryChange)
            ).all()

            vehicle = session.scalar(
                select(Vehicle).where(
                    Vehicle.source_listing_id == "TEST101"
                )
            )

            assert len(snapshots) == 2
            assert len(changes) == 1

            assert changes[0].change_type == "updated"
            assert changes[0].changes["price_cash"] == {
                "old": 35000,
                "new": 32000,
            }

            assert vehicle.price_cash == 32000

        # Reimporting identical inventory should be skipped.
        result = importer.import_inventory(second_file)

        assert result["skipped"] is True

        with Session(engine) as session:
            assert len(
                session.scalars(select(InventorySnapshot)).all()
            ) == 2

    finally:
        engine.dispose()
