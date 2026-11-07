
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.anomalies.scan_service as scan
from backend.database.connection import Base
from backend.database.models import (
    AnomalyFlag,
    AnomalyReviewEvent,
    InventoryChange,
    InventorySnapshot,
    Vehicle,
)
from ml.model_inference import (
    ModelFinding,
    ModelUnavailableError,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    Session = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with Session() as session:
        yield session

    engine.dispose()


def add_car(db, source_id, cash):
    vehicle = Vehicle(
        source_listing_id=source_id,
        title="2020 Toyota Corolla",
        year=2020,
        price_cash=cash,
        mileage_km=80000,
        listing_url="https://example.com/listing",
        is_active=True,
        missing_streak=0,
    )
    db.add(vehicle)
    db.commit()
    return vehicle


def run_rules(db):
    return scan.run_anomaly_scan(
        db,
        include_model=False,
        reference_year=2026,
    )


def test_rules_write_only_flags_and_are_idempotent(db):
    car = add_car(db, "x", 0)

    result = run_rules(db)
    db.commit()

    assert result.created == 1
    assert result.rule_findings == 1
    assert result.model_status == "disabled"

    again = run_rules(db)
    db.commit()

    assert again.created == 0
    assert again.seen_again == 1

    count = db.scalar(
        select(func.count()).select_from(AnomalyFlag)
    )
    assert count == 1

    db.refresh(car)
    assert car.price_cash == 0
    assert car.is_active is True
    assert car.missing_streak == 0


def test_review_decisions_survive_rescan(db):
    add_car(db, "x", -1)

    run_rules(db)
    db.commit()

    flag = db.scalar(select(AnomalyFlag))

    flag.review_status = "false_alarm"
    flag.reviewer_note = "Checked by staff"

    event = AnomalyReviewEvent(
        anomaly_flag_id=flag.id,
        previous_status="pending",
        new_status="false_alarm",
        new_note="Checked by staff",
    )

    db.add(event)
    db.commit()

    result = run_rules(db)
    db.commit()
    db.refresh(flag)

    assert result.created == 0
    assert flag.review_status == "false_alarm"
    assert flag.reviewer_note == "Checked by staff"

    event_count = db.scalar(
        select(func.count()).select_from(
            AnomalyReviewEvent
        )
    )
    assert event_count == 1


def test_new_evidence_creates_new_flag(db):
    car = add_car(db, "x", -1)

    run_rules(db)
    db.commit()

    old = db.scalar(select(AnomalyFlag))
    old.review_status = "valid_issue"
    db.commit()

    car.price_cash = -2
    db.commit()

    result = run_rules(db)
    db.commit()

    flags = db.scalars(
        select(AnomalyFlag).order_by(AnomalyFlag.id)
    ).all()

    assert result.created == 1
    assert len(flags) == 2

    assert flags[0].review_status == "valid_issue"
    assert flags[1].review_status == "pending"


def test_historical_change_links_audit_record(db):
    car = add_car(db, "x", 19000)

    snapshot = InventorySnapshot(total_vehicles=1)
    db.add(snapshot)
    db.flush()

    audit = InventoryChange(
        snapshot_id=snapshot.id,
        source_listing_id="x",
        change_type="updated",
        changes={
            "price_cash": {
                "old": 10000,
                "new": 19000,
            }
        },
    )

    db.add(audit)
    db.commit()

    result = run_rules(db)
    db.commit()

    assert result.rule_findings == 1
    assert result.created == 1

    flag = db.scalar(select(AnomalyFlag))

    assert flag.inventory_change_id == audit.id
    assert flag.vehicle_id == car.id
    assert flag.issue_type == "large_cash_price_change"
    assert flag.evidence["old_value"] == 10000

    assert run_rules(db).created == 0


def test_missing_cash_is_not_automatic_anomaly(db):
    add_car(db, "x", None)

    result = run_rules(db)

    assert result.created == 0
    assert result.rule_findings == 0


def test_unavailable_ml_does_not_block_rules(
    db,
    monkeypatch,
):
    add_car(db, "x", 0)

    def fail():
        raise ModelUnavailableError(
            "Unavailable for test"
        )

    monkeypatch.setattr(
        scan,
        "load_verified_model",
        fail,
    )

    result = scan.run_anomaly_scan(
        db,
        reference_year=2026,
    )
    db.commit()

    assert result.created == 1
    assert result.rule_findings == 1
    assert result.model_status == "unavailable"
    assert "Unavailable" in result.model_message


def test_model_flags_do_not_duplicate(
    db,
    monkeypatch,
):
    add_car(db, "x", 20000)

    verified = SimpleNamespace(
        metadata={
            "model_file_sha256": "a" * 64,
        }
    )

    monkeypatch.setattr(
        scan,
        "load_verified_model",
        lambda: verified,
    )

    findings = (
        ModelFinding(
            source_listing_id="x",
            issue_type="statistical_outlier",
            explanation="Experimental only",
            score=-0.12,
            model_version="iforest_v1",
            evidence={
                "year": 2020,
                "price_cash": 20000,
                "mileage_km": 80000,
                "features": {"vehicle_age": 6},
            },
        ),
    )

    monkeypatch.setattr(
        scan,
        "detect_model_findings",
        lambda cars, model: SimpleNamespace(
            findings=findings
        ),
    )

    first = scan.run_anomaly_scan(
        db,
        reference_year=2026,
    )
    db.commit()

    second = scan.run_anomaly_scan(
        db,
        reference_year=2026,
    )
    db.commit()

    assert first.model_findings == 1
    assert first.created == 1
    assert second.created == 0
    assert second.seen_again == 1

    flag = db.scalar(select(AnomalyFlag))

    assert flag.detector == "model"
    assert flag.model_version == "iforest_v1"
    assert flag.score == pytest.approx(-0.12)


def test_inactive_vehicle_is_excluded(db):
    car = add_car(db, "x", -1)

    car.is_active = False
    db.commit()

    result = run_rules(db)

    assert result.vehicles_checked == 0
    assert result.created == 0


def test_orphan_audit_is_skipped(db):
    snapshot = InventorySnapshot(total_vehicles=1)
    db.add(snapshot)
    db.flush()

    audit = InventoryChange(
        snapshot_id=snapshot.id,
        source_listing_id="missing",
        change_type="updated",
        changes={
            "mileage_km": {
                "old": 50000,
                "new": 20000,
            }
        },
    )

    db.add(audit)
    db.commit()

    result = run_rules(db)

    assert result.orphan_change_findings == 1
    assert result.created == 0


def test_invalid_reference_year_rejected(db):
    add_car(db, "x", 0)

    with pytest.raises(
        ValueError,
        match="reference_year",
    ):
        scan.run_anomaly_scan(
            db,
            include_model=False,
            reference_year=0,
        )

    count = db.scalar(
        select(func.count()).select_from(AnomalyFlag)
    )
    assert count == 0
