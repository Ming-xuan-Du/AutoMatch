from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CriterionName = Literal[
    "budget",
    "make",
    "model",
    "min_year",
    "max_mileage_km",
    "body_style",
    "drivetrain",
]

Status = Literal["met", "not_met", "unknown"]


class MatchRequest(BaseModel):
    max_budget: Decimal | None = Field(default=None, gt=0)

    make: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)

    min_year: int | None = Field(
        default=None, ge=1900, le=2100
    )

    max_mileage_km: int | None = Field(
        default=None, ge=0
    )

    body_style: str | None = Field(default=None, min_length=1)
    drivetrain: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_at_least_one_filter(self):
        for name in type(self).model_fields:
            value = getattr(self, name)

            if value is not None and (
                not isinstance(value, str) or value.strip()
            ):
                return self

        raise ValueError(
            "Provide at least one vehicle requirement."
        )


class CriterionCheck(BaseModel):
    field: CriterionName
    status: Status

    requested: str | int | Decimal
    actual: str | int | Decimal | None

    # Positive excess/shortfall when not met.
    difference: int | Decimal | None = None

    explanation: str


class VehicleCandidate(BaseModel):
    vehicle_id: int | str

    title: str | None
    year: int | None
    price_cash: Decimal | None
    mileage_km: int | None

    body_style: str | None
    drivetrain: str | None

    listing_url: str | None
    image_url: str | None

    checks: list[CriterionCheck]


class MatchResponse(BaseModel):
    count: int
    candidates: list[VehicleCandidate]
    message: str | None = None