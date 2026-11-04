from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.database.models import Vehicle, InventorySnapshot


router = APIRouter(
    prefix="/api/inventory",
    tags=["inventory"],
)


class SnapshotSummary(BaseModel):
    id: int
    scraped_at: datetime
    status: str | None
    total_vehicles: int
    pages_expected: int
    pages_seen: int


class InventoryStatusResponse(BaseModel):
    confirmed_present_count: int
    latest_snapshot: SnapshotSummary | None
    last_successful_snapshot: SnapshotSummary | None


def summarize_snapshot(
    snapshot: InventorySnapshot | None,
) -> SnapshotSummary | None:
    if snapshot is None:
        return None

    return SnapshotSummary(
        id=snapshot.id,
        scraped_at=snapshot.scraped_at,
        status=snapshot.status,
        total_vehicles=snapshot.total_vehicles,
        pages_expected=snapshot.pages_expected,
        pages_seen=snapshot.pages_seen,
    )


@router.get(
    "/status",
    response_model=InventoryStatusResponse,
)
def get_inventory_status(
    db: Session = Depends(get_db),
):
    # Same inventory eligibility filter as the matching API.
    confirmed_present_count = db.scalar(
        select(func.count(Vehicle.id)).where(
            Vehicle.is_active.is_(True),
            Vehicle.missing_streak == 0,
        )
    ) or 0

    # Most recent recorded snapshot, regardless of status.
    latest_snapshot = db.scalar(
        select(InventorySnapshot)
        .order_by(
            InventorySnapshot.scraped_at.desc(),
            InventorySnapshot.id.desc(),
        )
        .limit(1)
    )

    # Most recent recorded successful snapshot.
    last_successful_snapshot = db.scalar(
        select(InventorySnapshot)
        .where(InventorySnapshot.status == "success")
        .order_by(
            InventorySnapshot.scraped_at.desc(),
            InventorySnapshot.id.desc(),
        )
        .limit(1)
    )

    return InventoryStatusResponse(
        confirmed_present_count=confirmed_present_count,
        latest_snapshot=summarize_snapshot(latest_snapshot),
        last_successful_snapshot=summarize_snapshot(
            last_successful_snapshot
        ),
    )