
"""Feature engineering for AutoMatch anomaly detection.

This module:
- Does not access PostgreSQL.
- Does not train a model.
- Does not modify vehicle data.
- Produces reproducible numerical feature rows.

Feature version: v1
"""

from collections import Counter
from dataclasses import dataclass
from math import log1p
from typing import Iterable, Protocol


FEATURE_VERSION = "v1"

FEATURE_NAMES = (
    "vehicle_age",
    "log_cash_price",
    "log_mileage_km",
)


class VehicleLike(Protocol):
    source_listing_id: str
    title: str
    year: int | None
    price_cash: int | None
    mileage_km: int | None
    body_style: str | None
    is_active: bool
    missing_streak: int


@dataclass(frozen=True)
class FeatureRow:
    source_listing_id: str
    title: str
    body_style: str

    year: int
    price_cash: int
    mileage_km: int

    vehicle_age: int
    log_cash_price: float
    log_mileage_km: float

    def vector(self) -> tuple[float, float, float]:
        """Numerical features in a fixed column order."""
        return (
            float(self.vehicle_age),
            self.log_cash_price,
            self.log_mileage_km,
        )


@dataclass(frozen=True)
class FeatureDataset:
    rows: tuple[FeatureRow, ...]
    total_records: int
    excluded: dict[str, int]
    reference_year: int

    @property
    def feature_matrix(self) -> list[list[float]]:
        return [
            list(row.vector())
            for row in self.rows
        ]


def exclusion_reason(
    vehicle: VehicleLike,
    *,
    reference_year: int,
) -> str | None:
    """Identify records unsuitable for the initial model."""

    if vehicle.is_active is not True:
        return "inactive"

    if vehicle.missing_streak != 0:
        return "not_confirmed_present"

    if vehicle.year is None:
        return "missing_year"

    if (
        type(vehicle.year) is not int
        or vehicle.year < 1886
        or vehicle.year > reference_year + 1
    ):
        return "invalid_year"

    if vehicle.price_cash is None:
        return "missing_cash_price"

    if (
        type(vehicle.price_cash) is not int
        or vehicle.price_cash <= 0
    ):
        return "invalid_cash_price"

    if vehicle.mileage_km is None:
        return "missing_mileage"

    if (
        type(vehicle.mileage_km) is not int
        or vehicle.mileage_km < 0
    ):
        return "invalid_mileage"

    return None


def build_feature_dataset(
    vehicles: Iterable[VehicleLike],
    *,
    reference_year: int,
) -> FeatureDataset:
    """Build deterministic features from vehicle records.

    The reference year must be explicitly provided so
    that repeated experiments use the same vehicle ages.
    """

    if reference_year < 1886:
        raise ValueError("Invalid reference year")

    vehicle_list = list(vehicles)

    # Stable ordering, independent of query result order.
    vehicle_list.sort(
        key=lambda vehicle: vehicle.source_listing_id
    )

    rows = []
    excluded = Counter()

    for vehicle in vehicle_list:
        reason = exclusion_reason(
            vehicle,
            reference_year=reference_year,
        )

        if reason is not None:
            excluded[reason] += 1
            continue

        age = max(0, reference_year - vehicle.year)

        body_style = (
            vehicle.body_style.strip().casefold()
            if isinstance(vehicle.body_style, str)
            and vehicle.body_style.strip()
            else "unknown"
        )

        rows.append(
            FeatureRow(
                source_listing_id=vehicle.source_listing_id,
                title=vehicle.title,
                body_style=body_style,
                year=vehicle.year,
                price_cash=vehicle.price_cash,
                mileage_km=vehicle.mileage_km,
                vehicle_age=age,
                log_cash_price=log1p(vehicle.price_cash),
                log_mileage_km=log1p(vehicle.mileage_km),
            )
        )

    return FeatureDataset(
        rows=tuple(rows),
        total_records=len(vehicle_list),
        excluded=dict(excluded),
        reference_year=reference_year,
    )
