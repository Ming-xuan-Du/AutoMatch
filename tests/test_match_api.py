import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies import get_db
from backend.database.connection import Base
from backend.database.models import Vehicle
from backend.main import app


def make_vehicle(vehicle_id: int, **changes):
    data = {
        "id": vehicle_id,
        "source_listing_id": f"listing-{vehicle_id}",
        "title": "2020 Toyota RAV4 LE AWD",
        "year": 2020,
        "price_cash": 26000,
        "price_finance": None,
        "mileage_km": 110000,
        "body_style": "SUV",
        "drivetrain": "AWD",
        "listing_url": (
            f"https://example.org/vehicles/{vehicle_id}"
        ),
        "image_url": None,
        "is_active": True,
        "missing_streak": 0,
    }

    data.update(changes)

    return Vehicle(**data)


@pytest.fixture
def client():
    # Isolated SQLite database, shared between
    # TestClient and the test setup.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    # Seed test vehicles.
    # Six valid Toyotas exercise the five-car cap.
    with TestSession.begin() as session:
        vehicles = [
            make_vehicle(i)
            for i in range(1, 7)
        ]

        # Two Honda listings must be excluded.
        vehicles.append(
            make_vehicle(
                7,
                title="2020 Honda Civic",
                is_active=False,
            )
        )

        vehicles.append(
            make_vehicle(
                8,
                title="2020 Honda Civic",
                missing_streak=1,
            )
        )

        # Null cash price must remain unknown,
        # even when finance price exists.
        vehicles.append(
            make_vehicle(
                9,
                title="2019 Subaru Forester AWD",
                year=2019,
                price_cash=None,
                price_finance=18000,
            )
        )

        session.add_all(vehicles)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_match_returns_at_most_five(client):
    response = client.post(
        "/api/vehicles/match",
        json={"make": "Toyota"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 5
    assert len(data["candidates"]) == 5

    assert [
        car["vehicle_id"]
        for car in data["candidates"]
    ] == [1, 2, 3, 4, 5]


def test_inactive_and_missing_are_excluded(client):
    response = client.post(
        "/api/vehicles/match",
        json={"make": "Honda"},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_null_price_is_unknown(client):
    response = client.post(
        "/api/vehicles/match",
        json={
            "make": "Subaru",
            "max_budget": 25000,
            "body_style": "SUV",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1

    candidate = data["candidates"][0]

    assert candidate["vehicle_id"] == 9
    assert candidate["price_cash"] is None

    checks = {
        check["field"]: check
        for check in candidate["checks"]
    }

    assert checks["budget"]["status"] == "unknown"
    assert checks["make"]["status"] == "met"
    assert checks["body_style"]["status"] == "met"


def test_partial_match_explanations(client):
    response = client.post(
        "/api/vehicles/match",
        json={
            "max_budget": 25000,
            "make": "Toyota",
            "min_year": 2021,
            "body_style": "SUV",
        },
    )

    assert response.status_code == 200

    candidate = response.json()["candidates"][0]

    checks = {
        check["field"]: check
        for check in candidate["checks"]
    }

    assert checks["budget"]["status"] == "not_met"
    assert checks["budget"]["difference"] == "1000"

    assert checks["min_year"]["status"] == "not_met"
    assert checks["min_year"]["difference"] == 1

    assert checks["make"]["status"] == "met"
    assert checks["body_style"]["status"] == "met"


def test_beyond_budget_tolerance(client):
    response = client.post(
        "/api/vehicles/match",
        json={
            "max_budget": 20000,
            "make": "Toyota",
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_invalid_request_returns_422(client):
    response = client.post(
        "/api/vehicles/match",
        json={},
    )

    assert response.status_code == 422


def test_no_candidates_has_message(client):
    response = client.post(
        "/api/vehicles/match",
        json={"make": "Mazda"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 0
    assert data["candidates"] == []
    assert data["message"] is not None


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_blank_make_with_budget_returns_422(client):
    response = client.post(
        "/api/vehicles/match",
        json={
            "make": "   ",
            "max_budget": 30000,
        },
    )

    assert response.status_code == 422


def test_make_with_spaces_is_normalized(client):
    response = client.post(
        "/api/vehicles/match",
        json={
            "make": "  Toyota  ",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 5

    for candidate in data["candidates"]:
        make_check = next(
            check
            for check in candidate["checks"]
            if check["field"] == "make"
        )

        assert make_check["requested"] == "Toyota"
        assert make_check["status"] == "met"