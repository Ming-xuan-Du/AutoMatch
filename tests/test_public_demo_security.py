
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


REVIEW_PATHS = {
    "/api/anomalies",
    "/api/anomalies/{flag_id}",
    "/api/anomalies/{flag_id}/review",
}


@pytest.mark.parametrize(
    ("public_demo", "review_enabled"),
    [
        (False, True),
        (True, False),
    ],
)
def test_review_routes_only_available_locally(
    public_demo,
    review_enabled,
):
    """Check whether review routes are registered."""

    app = create_app(public_demo=public_demo)

    registered_paths = set(app.openapi()["paths"])

    if review_enabled:
        assert REVIEW_PATHS.issubset(
            registered_paths
        )
    else:
        assert REVIEW_PATHS.isdisjoint(
            registered_paths
        )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_review_api_unavailable_even_with_key(
    monkeypatch,
):
    """A valid local key cannot reopen public routes."""

    monkeypatch.setenv(
        "AUTOMATCH_REVIEW_API_KEY",
        "x" * 40,
    )

    app = create_app(public_demo=True)

    headers = {
        "X-AutoMatch-Review-Key": "x" * 40,
    }

    with TestClient(app) as client:
        list_response = client.get(
            "/api/anomalies",
            headers=headers,
        )

        detail_response = client.get(
            "/api/anomalies/1",
            headers=headers,
        )

        review_response = client.patch(
            "/api/anomalies/1/review",
            headers=headers,
            json={
                "review_status": "false_alarm",
            },
        )

        health_response = client.get("/health")

    assert list_response.status_code == 404
    assert detail_response.status_code == 404
    assert review_response.status_code == 404
    assert health_response.status_code == 200
