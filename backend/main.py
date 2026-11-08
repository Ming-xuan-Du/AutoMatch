
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.vehicles import router as vehicles_router
from backend.api.inventory import router as inventory_router
from backend.api.requirements import router as requirements_router
from backend.api.anomalies import router as anomalies_router


app = FastAPI(
    title="AutoMatch API",
    description=(
        "Vehicle inventory and deterministic "
        "partial-match search API."
    ),
    version="0.1.0",
)


app.include_router(vehicles_router)
app.include_router(inventory_router)
app.include_router(requirements_router)
app.include_router(anomalies_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "AutoMatch API",
    }


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


# Opt-in: local API development and backend CI remain unchanged.
if os.getenv(
    "AUTOMATCH_SERVE_FRONTEND", "0"
).strip() == "1":
    frontend_dist = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "dist"
    )

    mount_frontend(app, frontend_dist)
