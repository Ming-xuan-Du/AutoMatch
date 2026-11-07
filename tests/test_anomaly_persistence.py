
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.connection import Base
from backend.database.models import (
    AnomalyFlag,
    AnomalyReviewEvent,
    Vehicle,
    utc_now,
)


@pytest.fixture
def db_session():
    """Isolated SQLite database with foreign keys enabled."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with Session() as session:
        yield session

    engine.dispose()


def create_vehicle(db):
    vehicle = Vehicle(
        source_listing_id="test-vehicle-001",
        title="2020 Toyota Corolla",
        year=2020,
        price_cash=0,
        mileage_km=87000,
        listing_url="https://example.com/vehicle/001",
        is_active=True,
        missing_streak=0,
    )

    db.add(vehicle)
    db.commit()
    return vehicle


def make_flag(vehicle_id, seed="finding-001"):
    fingerprint = sha256(
        seed.encode("utf-8")
    ).hexdigest()

    return AnomalyFlag(
        vehicle_id=vehicle_id,
        detector="rule",
        issue_type="nonpositive_cash_price",
        explanation="Cash price must be positive.",
        evidence={"price_cash": 0},
        fingerprint=fingerprint,
    )


def test_anomaly_flag_persists_without_modifying_vehicle(db_session):
    vehicle = create_vehicle(db_session)
    flag = make_flag(vehicle.id)

    db_session.add(flag)
    db_session.commit()

    stored = db_session.get(AnomalyFlag, flag.id)

    assert stored is not None
    assert stored.vehicle_id == vehicle.id
    assert stored.detector == "rule"
    assert stored.review_status == "pending"
    assert stored.evidence == {"price_cash": 0}
    assert stored.first_detected_at is not None
    assert stored.last_detected_at is not None

    db_session.refresh(vehicle)

    assert vehicle.price_cash == 0
    assert vehicle.is_active is True
    assert vehicle.missing_streak == 0


def test_duplicate_fingerprint_is_rejected(db_session):
    vehicle = create_vehicle(db_session)

    first_flag = make_flag(vehicle.id, "same-finding")
    db_session.add(first_flag)
    db_session.commit()

    duplicate = make_flag(vehicle.id, "same-finding")
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    stored = db_session.scalars(
        select(AnomalyFlag)
    ).all()

    assert len(stored) == 1


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("detector", "unknown_detector"),
        ("review_status", "unrecognized_status"),
    ],
)
def test_invalid_flag_values_are_rejected(
    db_session,
    field,
    invalid_value,
):
    vehicle = create_vehicle(db_session)
    flag = make_flag(vehicle.id)

    setattr(flag, field, invalid_value)
    db_session.add(flag)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_vehicle_foreign_key_is_rejected(db_session):
    flag = make_flag(vehicle_id=999999)
    db_session.add(flag)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_inventory_change_reference_is_rejected(db_session):
    vehicle = create_vehicle(db_session)

    flag = make_flag(vehicle.id)
    flag.inventory_change_id = 999999

    db_session.add(flag)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_review_history_and_notes_are_preserved(db_session):
    vehicle = create_vehicle(db_session)
    flag = make_flag(vehicle.id)

    db_session.add(flag)
    db_session.commit()

    # First review: dismiss as a false alarm.
    flag.review_status = "false_alarm"
    flag.reviewer_note = "Verified against source listing."
    flag.reviewed_at = utc_now()

    first_event = AnomalyReviewEvent(
        anomaly_flag_id=flag.id,
        previous_status="pending",
        new_status="false_alarm",
        previous_note=None,
        new_note="Verified against source listing.",
    )

    db_session.add(first_event)
    db_session.commit()

    # Second review: mark as a valid issue.
    flag.review_status = "valid_issue"
    flag.reviewer_note = "Incorrect source value confirmed."
    flag.reviewed_at = utc_now()

    second_event = AnomalyReviewEvent(
        anomaly_flag_id=flag.id,
        previous_status="false_alarm",
        new_status="valid_issue",
        previous_note="Verified against source listing.",
        new_note="Incorrect source value confirmed.",
    )

    db_session.add(second_event)
    db_session.commit()

    events = db_session.scalars(
        select(AnomalyReviewEvent)
        .where(AnomalyReviewEvent.anomaly_flag_id == flag.id)
        .order_by(AnomalyReviewEvent.id)
    ).all()

    assert len(events) == 2

    assert events[0].previous_status == "pending"
    assert events[0].new_status == "false_alarm"

    assert events[1].previous_status == "false_alarm"
    assert events[1].new_status == "valid_issue"

    assert events[0].new_note == "Verified against source listing."
    assert events[1].changed_at is not None

    db_session.refresh(flag)

    assert flag.review_status == "valid_issue"
    assert flag.reviewer_note == "Incorrect source value confirmed."
    assert flag.reviewed_at is not None


def test_vehicle_with_anomaly_cannot_be_deleted(db_session):
    vehicle = create_vehicle(db_session)
    flag = make_flag(vehicle.id)

    db_session.add(flag)
    db_session.commit()

    db_session.delete(vehicle)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    assert db_session.get(Vehicle, vehicle.id) is not None


def test_ml_anomaly_fields_are_preserved(db_session):
    vehicle = create_vehicle(db_session)

    flag = make_flag(vehicle.id, "model-finding-001")
    flag.detector = "model"
    flag.issue_type = "statistical_outlier"
    flag.score = -0.25
    flag.model_version = "iforest_v1"
    flag.evidence = {
        "feature_version": "v1",
        "vehicle_age": 6,
    }

    db_session.add(flag)
    db_session.commit()

    stored = db_session.get(AnomalyFlag, flag.id)

    assert stored.detector == "model"
    assert stored.score == pytest.approx(-0.25)
    assert stored.model_version == "iforest_v1"
    assert stored.evidence["feature_version"] == "v1"
    assert stored.review_status == "pending"
