"""Deterministic partial-match eligibility engine.

Default policy:
- At least ceil(50% of requested conditions) must be met.
- Budget can exceed requested maximum by up to 10%.
- Mileage can exceed maximum by up to 15,000 km.
- Year can be up to 2 years below requested minimum.
- Text comparisons use normalized exact matching.
- Unknown values never count as met.
- Numeric differences beyond tolerance exclude a vehicle.
- Input order is preserved; maximum 5 candidates.
- No weighted scores or recommendation ranking.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import ceil
import re
from typing import Iterable

from backend.matching.schemas import (
    CriterionCheck,
    MatchRequest,
    VehicleCandidate,
)


@dataclass(frozen=True)
class MatchPolicy:
    min_met_fraction: Decimal = Decimal("0.50")
    max_budget_over_fraction: Decimal = Decimal("0.10")
    max_mileage_over_km: int = 15_000
    max_years_older: int = 2
    require_identity_overlap: bool = True

    def __post_init__(self):
        if not (0 < self.min_met_fraction <= 1):
            raise ValueError(
                "min_met_fraction must be in (0, 1]."
            )

        if self.max_budget_over_fraction < 0:
            raise ValueError(
                "Budget tolerance cannot be negative."
            )

        if (
            self.max_mileage_over_km < 0
            or self.max_years_older < 0
        ):
            raise ValueError(
                "Tolerances cannot be negative."
            )


def _decimal(value: object) -> Decimal | None:
    """Convert a numeric inventory value safely."""
    if value is None or isinstance(value, bool):
        return None

    try:
        number = Decimal(str(value))

        if number.is_finite() and number >= 0:
            return number

        return None

    except (InvalidOperation, TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    number = _decimal(value)

    if number is None:
        return None

    if number != number.to_integral_value():
        return None

    return int(number)


def _words(value: str) -> list[str]:
    """Normalize capitalization and punctuation."""
    return re.findall(r"[a-z0-9]+", value.casefold())


def _title_contains(title: str, phrase: str) -> bool:
    """Find a complete token sequence in a title."""
    words = _words(title)
    target = _words(phrase)

    return bool(target) and any(
        words[i:i + len(target)] == target
        for i in range(len(words) - len(target) + 1)
    )


def _label(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


_DRIVE_ALIASES = {
    "all wheel drive": "awd",
    "awd": "awd",
    "front wheel drive": "fwd",
    "fwd": "fwd",
    "rear wheel drive": "rwd",
    "rwd": "rwd",
    "four wheel drive": "4wd",
    "4wd": "4wd",
    "4x4": "4wd",
}


def _canonical(value: str, field: str) -> str:
    key = " ".join(_words(value))

    if field == "drivetrain":
        return _DRIVE_ALIASES.get(key, key)

    return key


def _check_text(
    field: str,
    requested: str,
    actual: str | None,
) -> CriterionCheck:

    if actual is None:
        return CriterionCheck(
            field=field,
            status="unknown",
            requested=requested,
            actual=None,
            explanation=f"{field} is missing in inventory.",
        )

    met = (
        _canonical(requested, field)
        == _canonical(actual, field)
    )

    return CriterionCheck(
        field=field,
        status="met" if met else "not_met",
        requested=requested,
        actual=actual,
        explanation=(
            f"{field} matches."
            if met
            else f"{field} differs from requested value."
        ),
    )


def _check_title(
    field: str,
    requested: str,
    title: str | None,
) -> CriterionCheck:

    if title is None:
        return CriterionCheck(
            field=field,
            status="unknown",
            requested=requested,
            actual=None,
            explanation=(
                "Vehicle title is missing; "
                "cannot check make/model."
            ),
        )

    met = _title_contains(title, requested)

    return CriterionCheck(
        field=field,
        status="met" if met else "not_met",
        requested=requested,
        actual=title,
        explanation=(
            f"{field} appears in title."
            if met
            else (
                f"{field} was not found as a "
                "complete phrase in title."
            )
        ),
    )


def _check_max(
    field: str,
    requested: int | Decimal,
    actual: int | Decimal | None,
    tolerance: int | Decimal,
    unit: str,
) -> tuple[CriterionCheck, bool]:
    """Check an upper bound.

    Returns:
        (comparison, exceeds_hard_tolerance)
    """

    if actual is None:
        return (
            CriterionCheck(
                field=field,
                status="unknown",
                requested=requested,
                actual=None,
                explanation=f"{field} is missing in inventory.",
            ),
            False,
        )

    if actual <= requested:
        return (
            CriterionCheck(
                field=field,
                status="met",
                requested=requested,
                actual=actual,
                explanation=f"Within {field} limit.",
            ),
            False,
        )

    excess = actual - requested

    check = CriterionCheck(
        field=field,
        status="not_met",
        requested=requested,
        actual=actual,
        difference=excess,
        explanation=(
            f"Exceeds {field} limit by {excess}{unit}."
        ),
    )

    return check, excess > tolerance


def _check_min_year(
    requested: int,
    actual: int | None,
    tolerance: int,
) -> tuple[CriterionCheck, bool]:

    if actual is None:
        return (
            CriterionCheck(
                field="min_year",
                status="unknown",
                requested=requested,
                actual=None,
                explanation="Vehicle year is missing.",
            ),
            False,
        )

    if actual >= requested:
        return (
            CriterionCheck(
                field="min_year",
                status="met",
                requested=requested,
                actual=actual,
                explanation="Meets minimum model year.",
            ),
            False,
        )

    gap = requested - actual

    return (
        CriterionCheck(
            field="min_year",
            status="not_met",
            requested=requested,
            actual=actual,
            difference=gap,
            explanation=(
                f"Vehicle is {gap} model year(s) "
                "older than requested."
            ),
        ),
        gap > tolerance,
    )


def find_candidates(
    vehicles: Iterable[object],
    request: MatchRequest,
    policy: MatchPolicy = MatchPolicy(),
) -> list[VehicleCandidate]:
    """Return up to five eligible candidates.

    The input must use a stable, business-neutral order,
    such as Vehicle.id ASC.
    """

    candidates: list[VehicleCandidate] = []
    seen: set[tuple[str, str]] = set()

    for vehicle in vehicles:

        # Defense in depth: verify inventory presence.
        if getattr(vehicle, "is_active", False) is not True:
            continue

        if getattr(vehicle, "missing_streak", None) != 0:
            continue

        vehicle_id = getattr(vehicle, "id", None)

        if vehicle_id is None:
            continue

        source_id = getattr(
            vehicle, "source_listing_id", None
        )

        key = (
            ("listing", str(source_id))
            if source_id
            else ("id", str(vehicle_id))
        )

        if key in seen:
            continue

        # Read inventory values without inventing data.
        title = _label(getattr(vehicle, "title", None))

        price = _decimal(
            getattr(vehicle, "price_cash", None)
        )

        if price == 0:
            # Treat zero-price placeholders as unknown.
            price = None

        year = _integer(
            getattr(vehicle, "year", None)
        )

        if year is not None and not 1900 <= year <= 2100:
            year = None

        mileage = _integer(
            getattr(vehicle, "mileage_km", None)
        )

        body = _label(
            getattr(vehicle, "body_style", None)
        )

        drive = _label(
            getattr(vehicle, "drivetrain", None)
        )

        checks: list[CriterionCheck] = []
        outside_tolerance = False

        # 1. Cash budget
        if request.max_budget is not None:
            check, excluded = _check_max(
                "budget",
                request.max_budget,
                price,
                (
                    request.max_budget
                    * policy.max_budget_over_fraction
                ),
                " CAD",
            )

            checks.append(check)
            outside_tolerance |= excluded

        # 2. Make, extracted from title
        if request.make is not None and request.make.strip():
            checks.append(
                _check_title("make", request.make, title)
            )

        # 3. Model, extracted from title
        if request.model is not None and request.model.strip():
            checks.append(
                _check_title("model", request.model, title)
            )

        # 4. Minimum model year
        if request.min_year is not None:
            check, excluded = _check_min_year(
                request.min_year,
                year,
                policy.max_years_older,
            )

            checks.append(check)
            outside_tolerance |= excluded

        # 5. Maximum mileage
        if request.max_mileage_km is not None:
            check, excluded = _check_max(
                "max_mileage_km",
                request.max_mileage_km,
                mileage,
                policy.max_mileage_over_km,
                " km",
            )

            checks.append(check)
            outside_tolerance |= excluded

        # 6. Body style
        if (
            request.body_style is not None
            and request.body_style.strip()
        ):
            checks.append(
                _check_text(
                    "body_style",
                    request.body_style,
                    body,
                )
            )

        # 7. Drivetrain
        if (
            request.drivetrain is not None
            and request.drivetrain.strip()
        ):
            checks.append(
                _check_text(
                    "drivetrain",
                    request.drivetrain,
                    drive,
                )
            )

        needed = ceil(
            Decimal(len(checks))
            * policy.min_met_fraction
        )

        met_count = sum(
            check.status == "met"
            for check in checks
        )

        # If make/model was specified, require at least
        # one of those identity conditions to match.
        identity_requested = (
            request.make is not None
            or request.model is not None
        )

        identity_met = any(
            check.field in ("make", "model")
            and check.status == "met"
            for check in checks
        )

        if (
            policy.require_identity_overlap
            and identity_requested
            and not identity_met
        ):
            continue

        # Eligibility only; no ranking.
        if outside_tolerance or met_count < needed:
            continue

        seen.add(key)

        candidates.append(
            VehicleCandidate(
                vehicle_id=(
                    vehicle_id
                    if isinstance(vehicle_id, (int, str))
                    else str(vehicle_id)
                ),
                title=title,
                year=year,
                price_cash=price,
                mileage_km=mileage,
                body_style=body,
                drivetrain=drive,
                listing_url=_label(
                    getattr(vehicle, "listing_url", None)
                ),
                image_url=_label(
                    getattr(vehicle, "image_url", None)
                ),
                checks=checks,
            )
        )

        # No Top-1 selection or score-based sorting.
        if len(candidates) == 5:
            break

    return candidates