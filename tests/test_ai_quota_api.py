
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai.extractor import ExtractionUnavailable
from backend.ai.quota_service import (
    AIQuotaExceeded,
    AIQuotaUnavailable,
)
from backend.ai.schemas import (
    ExtractResponse,
    ExtractedRequirements,
    REQUIREMENT_FIELDS,
)
from backend.api import requirements as api


TEXT = "I need a Toyota SUV."


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "AUTOMATCH_PUBLIC_DEMO", "1"
    )
    monkeypatch.setenv(
        "AUTOMATCH_PUBLIC_AI_ENABLED", "1"
    )
    monkeypatch.setenv(
        "AI_PROVIDER", "openai"
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY", "fake-test-key"
    )
    monkeypatch.setenv(
        "AUTOMATCH_VISITOR_HASH_SECRET",
        "s" * 40,
    )

    monkeypatch.setattr(
        api,
        "get_visitor_address",
        lambda request: "192.0.2.10",
    )

    app = FastAPI()
    app.include_router(api.router)

    return TestClient(app)


def post_extract(client, text=TEXT):
    return client.post(
        "/api/requirements/extract",
        json={"customer_text": text},
    )


def test_public_ai_reserves_and_finishes(
    client,
    monkeypatch,
):
    events = []

    def fake_reserve(factory, visitor_hash):
        assert len(visitor_hash) == 64
        events.append("reserve")
        return 123

    def fake_finish(factory, reservation_id, *, succeeded):
        events.append(
            ("finish", reservation_id, succeeded)
        )
        return True

    async def fake_extract(customer_text):
        events.append("extract")

        states = {
            field: "missing"
            for field in REQUIREMENT_FIELDS
        }
        states["make"] = "explicit"

        return ExtractResponse(
            requirements=ExtractedRequirements(
                make="Toyota",
            ),
            field_states=states,
            evidence={"make": "Toyota"},
            review_notes=[],
        )

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )
    monkeypatch.setattr(
        api, "finish_ai_extraction", fake_finish
    )
    monkeypatch.setattr(
        api, "extract_requirements", fake_extract
    )

    response = post_extract(client)

    assert response.status_code == 200
    assert response.json()["requirements"]["make"] == "Toyota"

    assert events == [
        "reserve",
        "extract",
        ("finish", 123, True),
    ]


def test_quota_exceeded_blocks_provider(
    client,
    monkeypatch,
):
    def fake_reserve(*args):
        raise AIQuotaExceeded("visitor_hour")

    async def fake_extract(*args):
        pytest.fail("AI must not be called.")

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )
    monkeypatch.setattr(
        api, "extract_requirements", fake_extract
    )

    assert post_extract(client).status_code == 429


def test_database_failure_blocks_provider(
    client,
    monkeypatch,
):
    def fake_reserve(*args):
        raise AIQuotaUnavailable("Database unavailable")

    async def fake_extract(*args):
        pytest.fail("AI must not be called.")

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )
    monkeypatch.setattr(
        api, "extract_requirements", fake_extract
    )

    assert post_extract(client).status_code == 503


def test_pii_is_rejected_before_reservation(
    client,
    monkeypatch,
):
    def fake_reserve(*args):
        pytest.fail("PII must not consume quota.")

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )

    response = post_extract(
        client,
        "Call 416-555-0123 about an SUV.",
    )

    assert response.status_code == 400


def test_missing_secret_fails_closed(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "AUTOMATCH_VISITOR_HASH_SECRET",
        raising=False,
    )

    response = post_extract(client)

    assert response.status_code == 503


def test_ollama_is_not_enabled_for_public_ai(
    client,
    monkeypatch,
):
    monkeypatch.setenv("AI_PROVIDER", "ollama")

    response = post_extract(client)

    assert response.status_code == 503


def test_provider_failure_marks_reservation_failed(
    client,
    monkeypatch,
):
    events = []

    def fake_reserve(*args):
        return 321

    def fake_finish(factory, reservation_id, *, succeeded):
        events.append(
            (reservation_id, succeeded)
        )
        return True

    async def fake_extract(*args):
        raise ExtractionUnavailable("Provider unavailable")

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )
    monkeypatch.setattr(
        api, "finish_ai_extraction", fake_finish
    )
    monkeypatch.setattr(
        api, "extract_requirements", fake_extract
    )

    response = post_extract(client)

    assert response.status_code == 503
    assert events == [(321, False)]
