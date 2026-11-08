import asyncio

from starlette.requests import Request
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


def test_public_ai_timeout_marks_reservation_failed(
    client,
    monkeypatch,
):
    """Timed-out public requests consume their reservation."""

    events = []

    monkeypatch.setattr(
        api,
        "PUBLIC_AI_TIMEOUT_SECONDS",
        0.01,
    )

    def fake_reserve(*args):
        events.append("reserve")
        return 456

    def fake_finish(factory, reservation_id, *, succeeded):
        events.append(
            ("finish", reservation_id, succeeded)
        )
        return True

    async def slow_extract(customer_text):
        events.append("extract")
        await asyncio.sleep(1)

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )
    monkeypatch.setattr(
        api, "finish_ai_extraction", fake_finish
    )
    monkeypatch.setattr(
        api, "extract_requirements", slow_extract
    )

    response = post_extract(client)

    assert response.status_code == 504
    assert events == [
        "reserve",
        "extract",
        ("finish", 456, False),
    ]


def test_public_ai_cancellation_marks_reservation_failed(
    client,
    monkeypatch,
):
    """Cancelling an API task finalizes its reservation."""

    events = []

    def fake_reserve(*args):
        return 789

    def fake_finish(factory, reservation_id, *, succeeded):
        events.append(
            (reservation_id, succeeded)
        )
        return True

    monkeypatch.setattr(
        api, "reserve_ai_extraction", fake_reserve
    )
    monkeypatch.setattr(
        api, "finish_ai_extraction", fake_finish
    )

    async def scenario():
        started = asyncio.Event()

        async def slow_extract(customer_text):
            started.set()
            await asyncio.sleep(60)

        monkeypatch.setattr(
            api, "extract_requirements", slow_extract
        )

        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/requirements/extract",
            "headers": [],
            "client": ("192.0.2.10", 12345),
        })

        task = asyncio.create_task(
            api.extract_customer_requirements(
                request=api.ExtractRequest(
                    customer_text=TEXT
                ),
                http_request=request,
            )
        )

        await asyncio.wait_for(
            started.wait(),
            timeout=3,
        )

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    assert events == [(789, False)]


def test_public_ai_deadline_precedes_lease_expiry():
    """Normal AI execution must finish before lease expiry."""

    from backend.ai.quota_service import QuotaLimits

    limits = QuotaLimits()

    assert (
        0 < api.PUBLIC_AI_TIMEOUT_SECONDS
        < limits.lease_seconds
    )
