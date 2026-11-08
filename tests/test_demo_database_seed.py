
"""Safe synthetic demo database initialization tests."""

import pytest

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from backend.database.connection import (
    Base,
    engine,
)
from backend.database.models import (
    InventorySnapshot,
    Vehicle,
)
from backend.demo.seed_database import (
    DemoSeedRefused,
    load_demo_data,
    seed_demo_database,
    verify_demo_target,
)


@pytest.fixture
def demo_sessions():
    """Create an isolated PostgreSQL test schema."""

    schema = f"automatch_seed_test_{uuid4().hex}"

    with engine.begin() as connection:
        connection.exec_driver_sql(
            f'CREATE SCHEMA "{schema}"'
        )

    isolated_engine = engine.execution_options(
        schema_translate_map={None: schema}
    )

    try:
        Base.metadata.create_all(isolated_engine)

        yield sessionmaker(
            bind=isolated_engine,
            expire_on_commit=False,
        )

    finally:
        # Only the randomly generated test schema is removed.
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f'DROP SCHEMA "{schema}" CASCADE'
            )


def test_demo_dataset_is_verified():
    vehicles, payload_hash = load_demo_data()

    assert len(vehicles) == 50
    assert len(payload_hash) == 64
    assert all(
        vehicle["source_listing_id"].startswith(
            "DEMO-"
        )
        for vehicle in vehicles
    )


def test_dry_run_does_not_write(demo_sessions):
    result = seed_demo_database(demo_sessions)

    assert result.applied is False
    assert result.vehicle_count == 50

    with demo_sessions() as session:
        count = session.scalar(
            select(func.count()).select_from(Vehicle)
        )

    assert count == 0


def test_apply_creates_50_vehicles_and_snapshot(
    demo_sessions,
):
    result = seed_demo_database(
        demo_sessions,
        apply=True,
    )

    assert result.applied is True
    assert result.vehicle_count == 50

    with demo_sessions() as session:
        vehicles = session.scalars(
            select(Vehicle)
        ).all()

        snapshots = session.scalars(
            select(InventorySnapshot)
        ).all()

    assert len(vehicles) == 50
    assert len(snapshots) == 1

    assert all(
        vehicle.is_active
        and vehicle.missing_streak == 0
        for vehicle in vehicles
    )

    assert snapshots[0].total_vehicles == 50
    assert snapshots[0].status == "success"
    assert snapshots[0].source_file.startswith(
        "synthetic:"
    )

    assert any(
        "Toyota RAV4" in vehicle.title
        and vehicle.year >= 2020
        and vehicle.price_cash <= 30000
        for vehicle in vehicles
    )


def test_existing_inventory_is_never_overwritten(
    demo_sessions,
):
    seed_demo_database(
        demo_sessions,
        apply=True,
    )

    with pytest.raises(
        DemoSeedRefused,
        match="not empty",
    ):
        seed_demo_database(
            demo_sessions,
            apply=True,
        )

    with demo_sessions() as session:
        count = session.scalar(
            select(func.count()).select_from(Vehicle)
        )

    assert count == 50


def test_target_requires_explicit_confirmation(
    monkeypatch,
):
    remote_url = make_url(
        "postgresql+psycopg://demo:test"
        "@db.example.com/automatch_demo"
    )

    monkeypatch.delenv(
        "AUTOMATCH_DEMO_SEED_ALLOWED",
        raising=False,
    )

    with pytest.raises(DemoSeedRefused):
        verify_demo_target(
            remote_url,
            "automatch_demo",
        )

    monkeypatch.setenv(
        "AUTOMATCH_DEMO_SEED_ALLOWED", "1"
    )

    with pytest.raises(DemoSeedRefused):
        verify_demo_target(
            remote_url,
            "automatch",
        )

    local_url = make_url(
        "postgresql+psycopg://demo:test"
        "@127.0.0.1/automatch_demo"
    )

    with pytest.raises(DemoSeedRefused):
        verify_demo_target(
            local_url,
            "automatch_demo",
        )

    # A named remote demo database can pass the guard.
    verify_demo_target(
        remote_url,
        "automatch_demo",
    )
