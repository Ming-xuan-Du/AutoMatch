
from urllib.parse import urlparse


class SnapshotValidationError(ValueError):
    """Raised when a vehicle snapshot fails validation."""


REQUIRED_FIELDS = (
    "source_listing_id",
    "title",
    "listing_url",
)


def validate_snapshot(vehicles, expected_count=None):
    """
    Validate a complete inventory snapshot.

    Returns the vehicles if valid.
    Raises SnapshotValidationError otherwise.
    """

    if not isinstance(vehicles, list):
        raise SnapshotValidationError(
            "Snapshot must be a list"
        )

    if not vehicles:
        raise SnapshotValidationError(
            "Snapshot cannot be empty"
        )

    if (
        expected_count is not None
        and len(vehicles) != expected_count
    ):
        raise SnapshotValidationError(
            f"Expected {expected_count} vehicles, "
            f"received {len(vehicles)}"
        )

    seen_ids = set()
    errors = []

    for index, vehicle in enumerate(vehicles):
        if not isinstance(vehicle, dict):
            errors.append(
                f"Vehicle {index}: must be a dictionary"
            )
            continue

        vehicle_id = vehicle.get("source_listing_id")
        label = f"Vehicle {index} ({vehicle_id})"

        for field in REQUIRED_FIELDS:
            value = vehicle.get(field)

            if value is None or (
                isinstance(value, str)
                and not value.strip()
            ):
                errors.append(
                    f"{label}: missing {field}"
                )

        # At least one price must be available
        if vehicle_id is not None:
            if not isinstance(vehicle_id, str) or not vehicle_id.strip():
                errors.append(
                    f"{label}: invalid source_listing_id"
                )
            elif vehicle_id in seen_ids:
                errors.append(
                    f"{label}: duplicate listing ID"
                )
            else:
                seen_ids.add(vehicle_id)

        for field in ("price_cash", "price_finance", "mileage_km"):
            value = vehicle.get(field)

            if value is not None:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    errors.append(
                        f"{label}: invalid {field}"
                    )

        year = vehicle.get("year")

        if year is not None:
            if (
                isinstance(year, bool)
                or not isinstance(year, int)
                or not 1886 <= year <= 2100
            ):
                errors.append(
                    f"{label}: invalid year"
                )

        listing_url = vehicle.get("listing_url")

        if isinstance(listing_url, str) and listing_url.strip():
            parsed = urlparse(listing_url)

            if (
                parsed.scheme not in ("http", "https")
                or not parsed.netloc
            ):
                errors.append(
                    f"{label}: invalid listing_url"
                )

    if errors:
        raise SnapshotValidationError(
            "Snapshot validation failed:\n"
            + "\n".join(errors[:20])
        )

    return vehicles