
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies import get_db
from backend.database.connection import Base
from backend.database.models import (
    AnomalyFlag,
    AnomalyReviewEvent,
    Vehicle,
)
from backend.main import app


TEST_KEY = "test-review-key-" + "a" * 32
HEADERS = {"X-AutoMatch-Review-Key": TEST_KEY}


@pytest.fixture
def api_client(monkeypatch):
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
        autoflush=False,
        expire_on_commit=False,
    )

    with Session() as session:
        vehicles = [
            Vehicle(
                source_listing_id=f"api-car-{i}",
                title=f"2020 Test Vehicle {i}",
                year=2020,
                price_cash=15000 + i * 1000,
                mileage_km=80000,
                listing_url=f"https://example.com/{i}",
                is_active=True,
                missing_streak=0,
            )
            for i in range(2)
        ]

        session.add_all(vehicles)
        session.flush()

        session.add_all([
            AnomalyFlag(
                vehicle_id=vehicles[0].id,
                detector="model",
                issue_type="statistical_outlier",
                explanation="Experimental ML flag",
                evidence={"price_cash": 15000},
                fingerprint="a" * 64,
                score=-0.12,
                model_version="iforest_v1",
            ),
            AnomalyFlag(
                vehicle_id=vehicles[1].id,
                detector="rule",
                issue_type="invalid_cash_price",
                explanation="Example rule finding",
                evidence={"price_cash": 16000},
                fingerprint="b" * 64,
            ),
        ])

        session.commit()

    def override_get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setenv(
        "AUTOMATCH_REVIEW_API_KEY",
        TEST_KEY,
    )

    try:
        with TestClient(app) as client:
            yield client, Session
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_list_anomalies(api_client):
    client, _ = api_client

    response = client.get(
        "/api/anomalies",
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["vehicle"]["title"]


def test_filter_and_paginate(api_client):
    client, _ = api_client

    response = client.get(
        "/api/anomalies",
        params={
            "detector": "model",
            "review_status": "pending",
            "limit": 1,
            "offset": 0,
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["detector"] == "model"


def test_anomaly_detail(api_client):
    client, _ = api_client

    response = client.get(
        "/api/anomalies/1",
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["score"] == pytest.approx(-0.12)
    assert data["review_events"] == []


def test_review_creates_history(api_client):
    client, Session = api_client

    response = client.patch(
        "/api/anomalies/1/review",
        json={
            "review_status": "false_alarm",
            "reviewer_note": "Verified original listing",
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["changed"] is True
    assert (
        data["finding"]["review_status"]
        == "false_alarm"
    )

    detail = client.get(
        "/api/anomalies/1",
        headers=HEADERS,
    ).json()

    assert len(detail["review_events"]) == 1
    assert (
        detail["review_events"][0]["new_status"]
        == "false_alarm"
    )

    with Session() as session:
        vehicle = session.get(Vehicle, 1)
        assert vehicle.price_cash == 15000


def test_identical_review_is_idempotent(api_client):
    client, Session = api_client

    payload = {"review_status": "valid_issue"}

    first = client.patch(
        "/api/anomalies/1/review",
        json=payload,
        headers=HEADERS,
    )

    second = client.patch(
        "/api/anomalies/1/review",
        json=payload,
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert first.json()["changed"] is True
    assert second.status_code == 200
    assert second.json()["changed"] is False

    with Session() as session:
        events = session.scalars(
            select(AnomalyReviewEvent)
        ).all()

        assert len(events) == 1


def test_note_only_update(api_client):
    client, _ = api_client

    response = client.patch(
        "/api/anomalies/1/review",
        json={
            "reviewer_note": "Needs verification"
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    finding = response.json()["finding"]

    assert finding["review_status"] == "pending"
    assert finding["reviewer_note"] == (
        "Needs verification"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"review_status": None},
        {"review_status": "approved"},
        {"reviewer_note": "   "},
    ],
)
def test_invalid_review_request(
    api_client,
    payload,
):
    client, _ = api_client

    response = client.patch(
        "/api/anomalies/1/review",
        json=payload,
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_missing_finding_returns_404(api_client):
    client, _ = api_client

    response = client.get(
        "/api/anomalies/999999",
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_missing_key_rejected(api_client):
    client, _ = api_client

    response = client.get("/api/anomalies")

    assert response.status_code == 401


def test_invalid_key_rejected(api_client):
    client, _ = api_client

    response = client.patch(
        "/api/anomalies/1/review",
        json={"review_status": "valid_issue"},
        headers={
            "X-AutoMatch-Review-Key": "wrong-key"
        },
    )

    assert response.status_code == 403


def test_unconfigured_api_is_disabled(
    api_client,
    monkeypatch,
):
    client, _ = api_client

    monkeypatch.delenv(
        "AUTOMATCH_REVIEW_API_KEY",
        raising=False,
    )

    response = client.get(
        "/api/anomalies",
        headers=HEADERS,
    )

    assert response.status_code == 503
