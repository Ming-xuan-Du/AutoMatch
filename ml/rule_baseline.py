
"""Deterministic vehicle data-quality anomaly rules.

This module does not access or modify the database.
Missing cash prices are handled separately as data
completeness issues, not automatic anomalies.
"""

from dataclasses import dataclass
from typing import Protocol


class VehicleLike(Protocol):
    source_listing_id: str
    title: str
    listing_url: str
    year: int | None
    price_cash: int | None
    price_finance: int | None
    mileage_km: int | None
    missing_streak: int


@dataclass(frozen=True)
class RuleFinding:
    source_listing_id: str
    rule_id: str
    field: str
    observed_value: int | str | None
    explanation: str


def check_vehicle(
    vehicle: VehicleLike,
    *,
    reference_year: int,
) -> list[RuleFinding]:
    """Return deterministic invalid-data findings."""

    findings = []

    def add(rule_id, field, value, explanation):
        findings.append(
            RuleFinding(
                source_listing_id=vehicle.source_listing_id,
                rule_id=rule_id,
                field=field,
                observed_value=value,
                explanation=explanation,
            )
        )

    # Allow the next model year, but not arbitrary
    # future years. 1886 is a conservative historical
    # lower boundary for motor vehicles.
    if vehicle.year is not None:
        if (
            vehicle.year < 1886
            or vehicle.year > reference_year + 1
        ):
            add(
                "invalid_year",
                "year",
                vehicle.year,
                "Vehicle year falls outside the "
                "supported historical/future range.",
            )

    if (
        vehicle.price_cash is not None
        and vehicle.price_cash <= 0
    ):
        add(
            "invalid_cash_price",
            "price_cash",
            vehicle.price_cash,
            "Cash price must be positive when provided.",
        )

    if (
        vehicle.price_finance is not None
        and vehicle.price_finance <= 0
    ):
        add(
            "invalid_finance_price",
            "price_finance",
            vehicle.price_finance,
            "Finance price must be positive when provided.",
        )

    if (
        vehicle.mileage_km is not None
        and vehicle.mileage_km < 0
    ):
        add(
            "negative_mileage",
            "mileage_km",
            vehicle.mileage_km,
            "Vehicle mileage cannot be negative.",
        )

    if vehicle.missing_streak < 0:
        add(
            "negative_missing_streak",
            "missing_streak",
            vehicle.missing_streak,
            "Missing streak cannot be negative.",
        )

    if not vehicle.source_listing_id.strip():
        add(
            "empty_listing_id",
            "source_listing_id",
            vehicle.source_listing_id,
            "Source listing ID cannot be empty.",
        )

    if not vehicle.title.strip():
        add(
            "empty_title",
            "title",
            vehicle.title,
            "Vehicle title cannot be empty.",
        )

    if not vehicle.listing_url.strip():
        add(
            "empty_listing_url",
            "listing_url",
            vehicle.listing_url,
            "Listing URL cannot be empty.",
        )

    return findings
