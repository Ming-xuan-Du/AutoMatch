
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.vehicles import router as vehicles_router
from backend.api.inventory import router as inventory_router
from backend.api.requirements import router as requirements_router
from backend.api.anomalies import router as anomalies_router


def mount_frontend(
    application: FastAPI,
    dist_dir: Path,
) -> None:
    """Serve the compiled React frontend.

    API routes must be registered before this root mount.
    """

    index_file = dist_dir / "index.html"

    if not index_file.is_file():
        raise RuntimeError(
            f"Frontend production build not found: "
            f"{index_file}. "
            "Run 'npm ci' and 'npm run build' "
            "inside the frontend directory first."
        )

    application.mount(
        "/",
        StaticFiles(
            directory=str(dist_dir),
            html=True,
        ),
        name="frontend",
    )


def create_app(
    *,
    public_demo: bool = False,
    serve_frontend: bool = False,
) -> FastAPI:
    """Create the AutoMatch application.

    Public demos intentionally omit the local-only
    anomaly review API.

    Existing local development behavior is preserved.
    """

    application = FastAPI(
        title="AutoMatch API",
        description=(
            "Vehicle inventory and deterministic "
            "partial-match search API."
        ),
        version="0.1.0",
    )

    application.include_router(vehicles_router)
    application.include_router(inventory_router)
    application.include_router(requirements_router)

    # This API uses a development-only shared key.
    # Never expose it in the public portfolio demo.
    if not public_demo:
        application.include_router(anomalies_router)

    @application.get("/health")
    def health_check():
        return {
            "status": "ok",
            "service": "AutoMatch API",
        }

    if serve_frontend:
        frontend_dist = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "dist"
        )

        mount_frontend(application, frontend_dist)

    return application


app = create_app(
    public_demo=(
        os.getenv(
            "AUTOMATCH_PUBLIC_DEMO", "0"
        ).strip() == "1"
    ),
    serve_frontend=(
        os.getenv(
            "AUTOMATCH_SERVE_FRONTEND", "0"
        ).strip() == "1"
    ),
)
