
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.anomalies.scan_cli as cli
import backend.anomalies.scan_service as scan
from backend.database.connection import Base
from backend.database.models import AnomalyFlag, Vehicle
from ml.model_inference import ModelFinding


@pytest.fixture
def db_factory(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    monkeypatch.setattr(
        cli,
        "SessionLocal",
        factory,
    )

    with factory() as session:
        session.add(
            Vehicle(
                source_listing_id="scan-test-001",
                title="2020 Toyota Corolla",
                year=2020,
                price_cash=-1,
                mileage_km=80000,
                listing_url="https://example.com/car",
                is_active=True,
                missing_streak=0,
            )
        )
        session.commit()

    yield factory

    engine.dispose()


def get_flags(factory):
    with factory() as session:
        return session.scalars(
            select(AnomalyFlag).order_by(AnomalyFlag.id)
        ).all()


def test_preview_creates_no_records(
    db_factory,
    capsys,
):
    assert cli.main(["--no-model"]) == 0

    output = capsys.readouterr().out

    assert "DRY RUN" in output
    assert "Would create: 1" in output
    assert len(get_flags(db_factory)) == 0


def test_apply_is_idempotent_and_preserves_review(
    db_factory,
):
    assert cli.main(
        ["--apply", "--no-model"]
    ) == 0

    with db_factory() as session:
        flag = session.scalar(select(AnomalyFlag))

        assert flag is not None
        flag.review_status = "false_alarm"
        flag.reviewer_note = "Reviewed by staff"
        session.commit()

    assert cli.main(
        ["--apply", "--no-model"]
    ) == 0

    flags = get_flags(db_factory)

    assert len(flags) == 1
    assert flags[0].review_status == "false_alarm"
    assert flags[0].reviewer_note == "Reviewed by staff"


def test_preview_does_not_update_existing_finding(
    db_factory,
):
    cli.main(["--apply", "--no-model"])

    with db_factory() as session:
        flag = session.scalar(select(AnomalyFlag))

        flag.last_detected_at = datetime(
            2026, 1, 1, tzinfo=timezone.utc
        )

        session.commit()
        flag_id = flag.id

    with db_factory() as session:
        before = session.get(
            AnomalyFlag,
            flag_id,
        ).last_detected_at

    cli.main(["--no-model"])

    with db_factory() as session:
        after = session.get(
            AnomalyFlag,
            flag_id,
        ).last_detected_at

    assert before == after
    assert len(get_flags(db_factory)) == 1


def test_changed_evidence_creates_new_flag(
    db_factory,
):
    cli.main(["--apply", "--no-model"])

    with db_factory() as session:
        vehicle = session.scalar(select(Vehicle))
        vehicle.price_cash = -2
        session.commit()

    cli.main(["--apply", "--no-model"])

    flags = get_flags(db_factory)

    assert len(flags) == 2
    assert flags[0].fingerprint != flags[1].fingerprint


def test_duplicate_finding_with_autoflush_disabled(
    db_factory,
    monkeypatch,
):
    with db_factory() as session:
        vehicle = session.scalar(select(Vehicle))
        vehicle.price_cash = 20000
        session.commit()

    verified = SimpleNamespace(
        metadata={
            "model_file_sha256": "a" * 64,
        }
    )

    finding = ModelFinding(
        source_listing_id="scan-test-001",
        issue_type="statistical_outlier",
        explanation="Experimental model flag",
        score=-0.12,
        model_version="iforest_v1",
        evidence={
            "year": 2020,
            "price_cash": 20000,
            "mileage_km": 80000,
        },
    )

    monkeypatch.setattr(
        scan,
        "load_verified_model",
        lambda: verified,
    )

    monkeypatch.setattr(
        scan,
        "detect_model_findings",
        lambda vehicles, model: SimpleNamespace(
            findings=(finding, finding)
        ),
    )

    with db_factory() as session:
        result = scan.run_anomaly_scan(
            session,
            reference_year=2026,
        )

        session.commit()

        count = session.scalar(
            select(func.count()).select_from(
                AnomalyFlag
            )
        )

    assert result.created == 1
    assert result.seen_again == 1
    assert count == 1
