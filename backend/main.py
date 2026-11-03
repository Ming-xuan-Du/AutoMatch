from fastapi import FastAPI

from backend.api.vehicles import router as vehicles_router


app = FastAPI(
    title="AutoMatch API",
    description=(
        "Vehicle inventory and deterministic "
        "partial-match search API."
    ),
    version="0.1.0",
)


app.include_router(vehicles_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "AutoMatch API",
    }