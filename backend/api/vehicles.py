from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.database.models import Vehicle

from backend.matching.matcher import find_candidates
from backend.matching.schemas import (
    MatchRequest,
    MatchResponse,
)


router = APIRouter(
    prefix="/api/vehicles",
    tags=["vehicles"],
)


@router.post(
    "/match",
    response_model=MatchResponse,
)
def match_vehicles(
    request: MatchRequest,
    db: Session = Depends(get_db),
) -> MatchResponse:
    """
    Return up to five eligible partial-match vehicles.

    Only confirmed-present active vehicles are queried.
    No ranking or recommendation scoring is applied.
    """

    statement = (
        select(Vehicle)
        .where(
            Vehicle.is_active.is_(True),
            Vehicle.missing_streak == 0,
        )
        .order_by(Vehicle.id.asc())
    )

    vehicles = db.scalars(statement).all()

    candidates = find_candidates(
        vehicles=vehicles,
        request=request,
    )

    message = None

    if not candidates:
        message = (
            "No vehicles met the current matching rules."
        )

    return MatchResponse(
        count=len(candidates),
        candidates=candidates,
        message=message,
    )