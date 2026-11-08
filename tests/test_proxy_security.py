
"""Proxy header safety checks for AutoMatch.

These tests verify local configuration behavior.
Real Render proxy behavior requires deployment testing.
"""

from pathlib import Path

import pytest
from starlette.requests import Request

from backend.ai.quota_service import AIQuotaUnavailable
from backend.api.requirements import get_visitor_address


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_request(client_address):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/requirements/extract",
            "headers": [
                (
                    b"x-forwarded-for",
                    b"203.0.113.99",
                )
            ],
            "client": client_address,
        }
    )


def test_application_does_not_read_forged_header():
    """Application reads the ASGI client, not XFF."""

    request = make_request(
        ("192.0.2.10", 12345)
    )

    assert get_visitor_address(request) == (
        "192.0.2.10"
    )


def test_missing_client_address_fails_closed():
    """Missing client identity must block AI usage."""

    request = make_request(None)

    with pytest.raises(AIQuotaUnavailable):
        get_visitor_address(request)


def test_render_disables_proxy_header_processing():
    """Render startup explicitly disables proxy headers."""

    content = (
        PROJECT_ROOT / "render.yaml"
    ).read_text(encoding="utf-8")

    start_command = content.split(
        "startCommand: >-", 1
    )[1].split(
        "healthCheckPath:", 1
    )[0]

    arguments = start_command.split()

    assert "--no-proxy-headers" in arguments
    assert "--proxy-headers" not in arguments
