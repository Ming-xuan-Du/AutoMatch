from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.api.dependencies import get_db
from backend.database.connection import Base
from backend.database.models import (
    InventorySnapshot,
    Vehicle,
)


@pytest.fixture
def inventory_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_inventory_status_returns_latest_snapshots(
    inventory_client,
):
    client, session_factory = inventory_client

    now = datetime.now(timezone.utc)

    with session_factory() as db:
        vehicles = [
            Vehicle(
                source_listing_id="A001",
                title="2020 Toyota Corolla",
                listing_url="https://example.com/a001",
                is_active=True,
                missing_streak=0,
            ),
            Vehicle(
                source_listing_id="A002",
                title="2019 Toyota C-HR",
                listing_url="https://example.com/a002",
                is_active=True,
                missing_streak=0,
            ),
            Vehicle(
                source_listing_id="A003",
                title="2021 Honda Civic",
                listing_url="https://example.com/a003",
                is_active=True,
                missing_streak=1,
            ),
            Vehicle(
                source_listing_id="A004",
                title="2018 Ford Escape",
                listing_url="https://example.com/a004",
                is_active=False,
                missing_streak=2,
            ),
        ]

        successful = InventorySnapshot(
            scraped_at=now - timedelta(days=1),
            total_vehicles=219,
            status="success",
            pages_expected=11,
            pages_seen=11,
        )

        partial = InventorySnapshot(
            scraped_at=now,
            total_vehicles=45,
            status="partial",
            pages_expected=11,
            pages_seen=3,
        )

        db.add_all(vehicles + [successful, partial])
        db.commit()

        success_id = successful.id
        partial_id = partial.id

    response = client.get("/api/inventory/status")

    assert response.status_code == 200

    body = response.json()

    assert body["confirmed_present_count"] == 2

    assert body["latest_snapshot"]["id"] == partial_id
    assert body["latest_snapshot"]["status"] == "partial"

    assert (
        body["last_successful_snapshot"]["id"]
        == success_id
    )

    assert (
        body["last_successful_snapshot"]["total_vehicles"]
        == 219
    )


def test_inventory_status_handles_empty_database(
    inventory_client,
):
    client, _ = inventory_client

    response = client.get("/api/inventory/status")

    assert response.status_code == 200

    body = response.json()

    assert body["confirmed_present_count"] == 0
    assert body["latest_snapshot"] is None
    assert body["last_successful_snapshot"] is None


def test_inventory_status_does_not_treat_partial_as_success(
    inventory_client,
):
    client, session_factory = inventory_client

    with session_factory() as db:
        db.add(
            InventorySnapshot(
                total_vehicles=50,
                status="partial",
                pages_expected=10,
                pages_seen=4,
            )
        )
        db.commit()

    response = client.get("/api/inventory/status")

    assert response.status_code == 200

    body = response.json()

    assert body["latest_snapshot"]["status"] == "partial"
    assert body["last_successful_snapshot"] is None