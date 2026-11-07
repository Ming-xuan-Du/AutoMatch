
import pytest

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.anomalies.review_service import (
    ReviewNotFoundError,
    ReviewValidationError,
    update_anomaly_review,
)
from backend.database.connection import Base
from backend.database.models import (
    AnomalyFlag,
    AnomalyReviewEvent,
    Vehicle,
)


@pytest.fixture
def review_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    Session = sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )

    with Session() as session:
        vehicle = Vehicle(
            source_listing_id="review-test-001",
            title="2020 Toyota Corolla",
            year=2020,
            price_cash=0,
            mileage_km=90000,
            listing_url="https://example.com/car",
            is_active=True,
            missing_streak=0,
        )

        session.add(vehicle)
        session.flush()

        flag = AnomalyFlag(
            vehicle_id=vehicle.id,
            detector="rule",
            issue_type="invalid_cash_price",
            explanation="Cash price must be positive.",
            evidence={"price_cash": 0},
            fingerprint="a" * 64,
        )

        session.add(flag)
        session.commit()

        yield session, flag.id, vehicle.id

    engine.dispose()


def get_events(session, flag_id):
    return session.scalars(
        select(AnomalyReviewEvent)
        .where(
            AnomalyReviewEvent.anomaly_flag_id == flag_id
        )
        .order_by(AnomalyReviewEvent.id)
    ).all()


def test_confirm_valid_issue(review_db):
    session, flag_id, _ = review_db

    result = update_anomaly_review(
        session,
        flag_id,
        review_status="valid_issue",
        reviewer_note="Cash price confirmed invalid",
    )
    session.commit()

    assert result.changed is True
    assert result.flag.review_status == "valid_issue"
    assert result.flag.reviewed_at is not None

    events = get_events(session, flag_id)

    assert len(events) == 1
    assert events[0].previous_status == "pending"
    assert events[0].new_status == "valid_issue"


def test_dismiss_as_false_alarm(review_db):
    session, flag_id, _ = review_db

    result = update_anomaly_review(
        session,
        flag_id,
        review_status="false_alarm",
        reviewer_note="Verified with original listing",
    )
    session.commit()

    assert result.flag.review_status == "false_alarm"
    assert result.flag.reviewer_note == (
        "Verified with original listing"
    )

    assert len(get_events(session, flag_id)) == 1


def test_repeated_review_is_idempotent(review_db):
    session, flag_id, _ = review_db

    update_anomaly_review(
        session,
        flag_id,
        review_status="false_alarm",
    )
    session.commit()

    second = update_anomaly_review(
        session,
        flag_id,
        review_status="false_alarm",
    )
    session.commit()

    assert second.changed is False
    assert len(get_events(session, flag_id)) == 1


def test_review_can_return_to_pending(review_db):
    session, flag_id, _ = review_db

    update_anomaly_review(
        session,
        flag_id,
        review_status="valid_issue",
    )
    session.commit()

    result = update_anomaly_review(
        session,
        flag_id,
        review_status="pending",
    )
    session.commit()

    assert result.flag.review_status == "pending"
    assert result.flag.reviewed_at is None

    events = get_events(session, flag_id)

    assert len(events) == 2
    assert events[1].previous_status == "valid_issue"
    assert events[1].new_status == "pending"


def test_note_only_update_preserves_status(review_db):
    session, flag_id, _ = review_db

    result = update_anomaly_review(
        session,
        flag_id,
        reviewer_note="  Needs manual verification  ",
    )
    session.commit()

    assert result.changed is True
    assert result.flag.review_status == "pending"
    assert result.flag.reviewed_at is None
    assert result.flag.reviewer_note == (
        "Needs manual verification"
    )

    events = get_events(session, flag_id)

    assert len(events) == 1
    assert events[0].previous_status == "pending"
    assert events[0].new_status == "pending"


def test_note_can_be_cleared(review_db):
    session, flag_id, _ = review_db

    update_anomaly_review(
        session,
        flag_id,
        reviewer_note="Temporary note",
    )
    session.commit()

    result = update_anomaly_review(
        session,
        flag_id,
        reviewer_note=None,
    )
    session.commit()

    assert result.flag.reviewer_note is None

    events = get_events(session, flag_id)

    assert len(events) == 2
    assert events[1].previous_note == "Temporary note"
    assert events[1].new_note is None


@pytest.mark.parametrize(
    "invalid_status",
    [
        "approved",
        "dismissed",
        "",
        None,
    ],
)
def test_invalid_status_rejected(
    review_db,
    invalid_status,
):
    session, flag_id, _ = review_db

    with pytest.raises(ReviewValidationError):
        update_anomaly_review(
            session,
            flag_id,
            review_status=invalid_status,
        )

    assert len(get_events(session, flag_id)) == 0


@pytest.mark.parametrize(
    "invalid_note",
    [
        "",
        "    ",
        "x" * 2001,
        123,
    ],
)
def test_invalid_note_rejected(
    review_db,
    invalid_note,
):
    session, flag_id, _ = review_db

    with pytest.raises(ReviewValidationError):
        update_anomaly_review(
            session,
            flag_id,
            reviewer_note=invalid_note,
        )

    assert len(get_events(session, flag_id)) == 0


def test_missing_finding_rejected(review_db):
    session, _, _ = review_db

    with pytest.raises(ReviewNotFoundError):
        update_anomaly_review(
            session,
            999999,
            review_status="valid_issue",
        )


def test_empty_update_rejected(review_db):
    session, flag_id, _ = review_db

    with pytest.raises(ReviewValidationError):
        update_anomaly_review(
            session,
            flag_id,
        )


def test_rollback_restores_status_and_events(review_db):
    session, flag_id, _ = review_db

    update_anomaly_review(
        session,
        flag_id,
        review_status="valid_issue",
    )

    session.rollback()

    flag = session.get(AnomalyFlag, flag_id)

    assert flag.review_status == "pending"
    assert len(get_events(session, flag_id)) == 0


def test_vehicle_data_remains_unchanged(review_db):
    session, flag_id, vehicle_id = review_db

    update_anomaly_review(
        session,
        flag_id,
        review_status="valid_issue",
        reviewer_note="Needs correction",
    )
    session.commit()

    vehicle = session.get(Vehicle, vehicle_id)

    assert vehicle.price_cash == 0
    assert vehicle.mileage_km == 90000
    assert vehicle.is_active is True
    assert vehicle.missing_streak == 0
