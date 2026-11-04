
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai import extractor
from backend.ai.schemas import (
    ExtractResponse,
    ExtractedRequirements,
)
from backend.api import requirements as requirements_api


@pytest.fixture
def client():
    # Router-level tests do not need a database.
    app = FastAPI()
    app.include_router(requirements_api.router)

    return TestClient(app)


def test_extract_endpoint_success(
    client,
    monkeypatch,
):
    async def fake_extract(customer_text):
        return ExtractResponse(
            requirements=ExtractedRequirements(
                make="Toyota",
                body_style="SUV",
            ),
            field_states={
                "max_budget": "missing",
                "make": "explicit",
                "model": "missing",
                "min_year": "missing",
                "max_mileage_km": "missing",
                "body_style": "explicit",
                "drivetrain": "missing",
            },
            evidence={
                "make": "Toyota",
                "body_style": "SUV",
            },
            review_notes=[],
        )

    monkeypatch.setattr(
        requirements_api,
        "extract_requirements",
        fake_extract,
    )

    response = client.post(
        "/api/requirements/extract",
        json={
            "customer_text": "I need a Toyota SUV."
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["requirements"]["make"] == "Toyota"
    assert body["requirements"]["body_style"] == "SUV"
    assert body["requirements"]["model"] is None


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (
            extractor.ExtractionUnavailable(
                "AI not configured"
            ),
            503,
        ),
        (
            extractor.ExtractionTimeout(
                "AI timed out"
            ),
            504,
        ),
        (
            extractor.ExtractionInvalidResponse(
                "Invalid AI response"
            ),
            502,
        ),
        (
            extractor.PersonalInformationDetected(
                "Remove personal information"
            ),
            400,
        ),
    ],
)
def test_api_error_mapping(
    client,
    monkeypatch,
    exception,
    expected_status,
):
    async def fake_extract(customer_text):
        raise exception

    monkeypatch.setattr(
        requirements_api,
        "extract_requirements",
        fake_extract,
    )

    response = client.post(
        "/api/requirements/extract",
        json={
            "customer_text": "I need a Toyota SUV."
        },
    )

    assert response.status_code == expected_status
    assert "detail" in response.json()


def test_empty_description_rejected(client):
    response = client.post(
        "/api/requirements/extract",
        json={"customer_text": "   "},
    )

    assert response.status_code == 422


def test_description_too_long_rejected(client):
    response = client.post(
        "/api/requirements/extract",
        json={"customer_text": "SUV " * 400},
    )

    assert response.status_code == 422


def test_missing_credentials_returns_503(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    response = client.post(
        "/api/requirements/extract",
        json={
            "customer_text": "I need a Toyota SUV."
        },
    )

    assert response.status_code == 503


def test_pii_rejected_before_provider_call(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    response = client.post(
        "/api/requirements/extract",
        json={
            "customer_text": (
                "My phone is 416-555-0123. "
                "I want an SUV."
            )
        },
    )

    assert response.status_code == 400
