
"""Anomaly review API for AutoMatch.

All endpoints require a configured review API key.
Intended for controlled local development, not
production-grade authentication.
"""

import os
import secrets
from datetime import datetime
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.anomalies.review_service import (
    ReviewNotFoundError,
    ReviewValidationError,
    update_anomaly_review,
)
from backend.api.dependencies import get_db
from backend.database.models import (
    AnomalyFlag,
)


ReviewStatus = Literal[
    "pending",
    "valid_issue",
    "false_alarm",
]

DetectorType = Literal["rule", "model"]


def require_review_key(
    provided: str | None = Header(
        default=None,
        alias="X-AutoMatch-Review-Key",
    ),
):
    configured = os.getenv("AUTOMATCH_REVIEW_API_KEY")

    if not configured or len(configured) < 32:
        raise HTTPException(
            status_code=503,
            detail="Anomaly review API is not configured",
        )

    if provided is None:
        raise HTTPException(
            status_code=401,
            detail="Review API key is required",
        )

    if not secrets.compare_digest(
        provided.encode("utf-8"),
        configured.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid review API key",
        )


router = APIRouter(
    prefix="/api/anomalies",
    tags=["Anomaly Review"],
    dependencies=[Depends(require_review_key)],
)


class VehicleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_listing_id: str
    title: str
    year: int | None
    price_cash: int | None
    mileage_km: int | None
    body_style: str | None
    drivetrain: str | None
    listing_url: str
    image_url: str | None


class AnomalyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    inventory_change_id: int | None

    detector: DetectorType
    issue_type: str
    explanation: str
    evidence: dict[str, Any]

    score: float | None
    model_version: str | None

    first_detected_at: datetime
    last_detected_at: datetime

    review_status: ReviewStatus
    reviewer_note: str | None
    reviewed_at: datetime | None

    vehicle: VehicleSummary


class ReviewEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    previous_status: ReviewStatus
    new_status: ReviewStatus
    previous_note: str | None
    new_note: str | None
    changed_at: datetime


class AnomalyDetailRead(AnomalyRead):
    review_events: list[ReviewEventRead]


class AnomalyListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AnomalyRead]


class ReviewUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: ReviewStatus | None = None
    reviewer_note: str | None = Field(
        default=None,
        max_length=2000,
    )


class ReviewUpdateResponse(BaseModel):
    changed: bool
    finding: AnomalyRead


@router.get(
    "",
    response_model=AnomalyListResponse,
)
def list_anomalies(
    review_status: ReviewStatus | None = None,
    detector: DetectorType | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    conditions = []

    if review_status is not None:
        conditions.append(
            AnomalyFlag.review_status == review_status
        )

    if detector is not None:
        conditions.append(
            AnomalyFlag.detector == detector
        )

    total = session.scalar(
        select(func.count(AnomalyFlag.id))
        .where(*conditions)
    )

    flags = session.scalars(
        select(AnomalyFlag)
        .options(selectinload(AnomalyFlag.vehicle))
        .where(*conditions)
        .order_by(
            AnomalyFlag.first_detected_at.desc(),
            AnomalyFlag.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": flags,
    }


@router.get(
    "/{flag_id}",
    response_model=AnomalyDetailRead,
)
def get_anomaly(
    flag_id: int,
    session: Session = Depends(get_db),
):
    flag = session.scalar(
        select(AnomalyFlag)
        .options(
            selectinload(AnomalyFlag.vehicle),
            selectinload(AnomalyFlag.review_events),
        )
        .where(AnomalyFlag.id == flag_id)
    )

    if flag is None:
        raise HTTPException(
            status_code=404,
            detail="Anomaly finding not found",
        )

    return flag


@router.patch(
    "/{flag_id}/review",
    response_model=ReviewUpdateResponse,
)
def review_anomaly(
    flag_id: int,
    payload: ReviewUpdateRequest,
    session: Session = Depends(get_db),
):
    provided_fields = payload.model_fields_set

    if not provided_fields:
        raise HTTPException(
            status_code=422,
            detail="At least one review field is required",
        )

    if (
        "review_status" in provided_fields
        and payload.review_status is None
    ):
        raise HTTPException(
            status_code=422,
            detail="Review status cannot be null",
        )

    update_kwargs = {}

    if "review_status" in provided_fields:
        update_kwargs["review_status"] = (
            payload.review_status
        )

    if "reviewer_note" in provided_fields:
        update_kwargs["reviewer_note"] = (
            payload.reviewer_note
        )

    try:
        result = update_anomaly_review(
            session,
            flag_id,
            **update_kwargs,
        )

        session.commit()

        session.refresh(result.flag)

        return {
            "changed": result.changed,
            "finding": result.flag,
        }

    except ReviewNotFoundError as exc:
        session.rollback()
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ReviewValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception:
        session.rollback()
        raise
