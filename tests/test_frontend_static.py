
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import mount_frontend


def test_frontend_serves_build_and_preserves_api(
    tmp_path: Path,
):
    """React assets and existing APIs remain accessible."""

    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)

    (dist_dir / "index.html").write_text(
        "<!doctype html><html>"
        "<body>AutoMatch Test Frontend</body>"
        "</html>",
        encoding="utf-8",
    )

    (assets_dir / "app.js").write_text(
        "console.log('AutoMatch');",
        encoding="utf-8",
    )

    test_app = FastAPI()

    @test_app.get("/api/ping")
    def api_ping():
        return {"status": "ok"}

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    mount_frontend(test_app, dist_dir)

    with TestClient(test_app) as client:
        index_response = client.get("/")
        assert index_response.status_code == 200
        assert "AutoMatch Test Frontend" in (
            index_response.text
        )

        asset_response = client.get("/assets/app.js")
        assert asset_response.status_code == 200
        assert "console.log" in asset_response.text

        api_response = client.get("/api/ping")
        assert api_response.status_code == 200
        assert api_response.json() == {"status": "ok"}

        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}

        missing_api = client.get("/api/not-found")
        assert missing_api.status_code == 404


def test_missing_frontend_build_fails_fast(
    tmp_path: Path,
):
    """Production serving must not start without a build."""

    test_app = FastAPI()

    with pytest.raises(
        RuntimeError,
        match="Frontend production build not found",
    ):
        mount_frontend(test_app, tmp_path / "missing-dist")
