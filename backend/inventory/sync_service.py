
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from backend.database.models import (
    Vehicle,
    InventorySnapshot as SnapshotRow,
    InventoryChange,
)


# These are the actual fields in your Vehicle model.
VEHICLE_FIELDS = (
    "title",
    "year",
    "price_cash",
    "price_finance",
    "mileage_km",
    "exterior_color",
    "stock_no",
    "doors",
    "body_style",
    "transmission",
    "drivetrain",
    "engine",
    "vin",
    "listing_url",
    "image_url",
)


@dataclass(frozen=True)
class InventorySnapshot:
    snapshot_id: str
    vehicles: Sequence[Mapping[str, Any]]
    pages_expected: int
    pages_seen: int
    is_complete: bool
    errors: Sequence[str] = field(default_factory=tuple)
    source_file: str | None = None


@dataclass(frozen=True)
class SyncResult:
    run_id: int
    status: str
    added: int
    updated: int
    unchanged: int
    suspected_missing: int
    inactive: int
    replayed: bool = False
    error_detail: str | None = None


def _now():
    return datetime.now(timezone.utc)


def _fingerprint(snapshot: InventorySnapshot) -> str:
    """Generate a stable fingerprint of the crawl contents."""

    records = [
        dict(v) if isinstance(v, Mapping)
        else {"invalid_record": repr(v)}
        for v in snapshot.vehicles
    ]

    payload = {
        "vehicles": sorted(
            records,
            key=lambda v: str(
                v.get("source_listing_id", "")
            ),
        ),
        "pages_expected": snapshot.pages_expected,
        "pages_seen": snapshot.pages_seen,
        "is_complete": snapshot.is_complete,
        "errors": list(snapshot.errors),
    }

    data = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return sha256(data.encode("utf-8")).hexdigest()


def _validate(snapshot: InventorySnapshot):
    """Reject incomplete, empty or invalid snapshots."""

    if (
        not snapshot.snapshot_id
        or not snapshot.snapshot_id.strip()
    ):
        raise ValueError("snapshot_id must not be empty")

    if (
        snapshot.pages_expected < 1
        or snapshot.pages_seen != snapshot.pages_expected
    ):
        return [], "Incomplete pagination"

    if not snapshot.is_complete or snapshot.errors:
        return [], "Crawler did not finish successfully"

    if not snapshot.vehicles:
        return [], "Empty inventory snapshot"

    seen = set()
    records = []

    for index, raw in enumerate(snapshot.vehicles):
        if not isinstance(raw, Mapping):
            return [], f"Invalid record at index {index}"

        listing_id = str(
            raw.get("source_listing_id") or ""
        ).strip()

        if not listing_id or listing_id in seen:
            return [], (
                f"Missing/duplicate listing ID: {listing_id!r}"
            )

        seen.add(listing_id)

        record = {
            key: raw[key]
            for key in VEHICLE_FIELDS
            if key in raw
        }

        record["source_listing_id"] = listing_id

        # Your Vehicle model requires title,
        # but does not have make/model columns.
        title = str(record.get("title") or "").strip()

        if not title:
            make = str(raw.get("make") or "").strip()
            model = str(raw.get("model") or "").strip()

            if make and model:
                title = " ".join(
                    str(value)
                    for value in (
                        raw.get("year"), make, model
                    )
                    if value
                )
            else:
                return [], f"Missing title for {listing_id}"

        record["title"] = title

        if not str(
            record.get("listing_url") or ""
        ).strip():
            return [], (
                f"Missing listing_url for {listing_id}"
            )

        records.append(record)

    return records, None


def _result(row: SnapshotRow, replayed=False):
    return SyncResult(
        run_id=row.id,
        status=row.status,
        added=row.added,
        updated=row.updated,
        unchanged=row.unchanged,
        suspected_missing=row.suspected_missing,
        inactive=row.inactive,
        replayed=replayed,
        error_detail=row.error_detail,
    )


def _write_change(
    session,
    run_id,
    listing_id,
    kind,
    changes,
    at,
):
    """Record a vehicle event in your existing JSON audit table."""

    session.add(
        InventoryChange(
            snapshot_id=run_id,
            source_listing_id=listing_id,
            change_type=kind,
            changes=changes,
            detected_at=at,
        )
    )


def sync_inventory(
    session_factory: sessionmaker,
    snapshot: InventorySnapshot,
    *,
    missing_threshold: int = 2,
    drop_ratio: float = 0.5,
    drop_guard_min_previous: int = 10,
) -> SyncResult:
    """Atomically apply one validated crawl to inventory."""

    if missing_threshold < 2:
        raise ValueError(
            "missing_threshold must be >= 2"
        )

    if not 0 < drop_ratio < 1:
        raise ValueError(
            "drop_ratio must be between 0 and 1"
        )

    if drop_guard_min_previous < 1:
        raise ValueError(
            "drop_guard_min_previous must be >= 1"
        )

    records, problem = _validate(snapshot)
    digest = _fingerprint(snapshot)
    now = _now()

    with session_factory.begin() as session:

        # Prevent concurrent sync jobs on PostgreSQL.
        if session.bind.dialect.name == "postgresql":
            acquired = session.execute(
                text(
                    "SELECT pg_try_advisory_xact_lock(:lock_id)"
                ),
                {"lock_id": 817263491},
            ).scalar_one()

            if not acquired:
                raise RuntimeError(
                    "Another inventory sync is running"
                )

        # Prevent replay of the same saved crawl.
        existing_run = session.scalar(
            select(SnapshotRow).where(
                SnapshotRow.crawl_id
                == snapshot.snapshot_id
            )
        )

        if existing_run is not None:
            if existing_run.payload_hash != digest:
                raise ValueError(
                    "Crawl ID already used for different contents"
                )

            return _result(
                existing_run,
                replayed=True,
            )

        # Read the existing inventory.
        existing_cars = {
            vehicle.source_listing_id: vehicle
            for vehicle in session.scalars(
                select(Vehicle)
            ).all()
        }

        previous_success = session.scalar(
            select(SnapshotRow)
            .where(SnapshotRow.status == "success")
            .order_by(SnapshotRow.id.desc())
            .limit(1)
        )

        if previous_success is not None:
            baseline_count = (
                previous_success.total_vehicles
            )
        else:
            baseline_count = sum(
                bool(vehicle.is_active)
                for vehicle in existing_cars.values()
            )

        # Block suspiciously small snapshots.
        if (
            problem is None
            and baseline_count
                >= drop_guard_min_previous
            and len(records)
                < baseline_count * drop_ratio
        ):
            problem = (
                "Suspicious inventory drop: "
                f"{baseline_count} -> {len(records)}"
            )

        # Store the synchronization run.
        run = SnapshotRow(
            crawl_id=snapshot.snapshot_id,
            payload_hash=digest,
            scraped_at=now,
            total_vehicles=len(snapshot.vehicles),
            source_file=snapshot.source_file,
            status="partial" if problem else "success",
            pages_expected=snapshot.pages_expected,
            pages_seen=snapshot.pages_seen,
            added=0,
            updated=0,
            unchanged=0,
            suspected_missing=0,
            inactive=0,
            error_detail=problem,
        )

        session.add(run)
        session.flush()

        # Invalid snapshots cannot change inventory.
        if problem:
            return _result(run)

        observed = set()

        # INSERT / UPDATE / REAPPEARANCE
        for record in records:
            listing_id = record["source_listing_id"]
            observed.add(listing_id)

            car = existing_cars.get(listing_id)

            if car is None:
                session.add(
                    Vehicle(
                        **record,
                        first_seen_at=now,
                        last_seen_at=now,
                        is_active=True,
                        missing_streak=0,
                    )
                )

                _write_change(
                    session,
                    run.id,
                    listing_id,
                    "added",
                    {"new": record},
                    now,
                )

                run.added += 1
                continue

            changes = {}

            for field_name in VEHICLE_FIELDS:
                if field_name not in record:
                    # Omitted field should not overwrite
                    # existing data with None.
                    continue

                old = getattr(car, field_name)
                new = record[field_name]

                if old != new:
                    changes[field_name] = {
                        "old": old,
                        "new": new,
                    }

                    setattr(car, field_name, new)

            was_inactive = not car.is_active
            was_missing = (
                was_inactive
                or bool(car.missing_streak)
            )

            if was_inactive:
                changes["is_active"] = {
                    "old": False,
                    "new": True,
                }

                car.is_active = True

            if car.missing_streak:
                changes["missing_streak"] = {
                    "old": car.missing_streak,
                    "new": 0,
                }

                car.missing_streak = 0

            car.last_seen_at = now

            if changes:
                kind = (
                    "reappeared"
                    if was_missing
                    else "updated"
                )

                _write_change(
                    session,
                    run.id,
                    listing_id,
                    kind,
                    changes,
                    now,
                )

                run.updated += 1
            else:
                run.unchanged += 1

        # HANDLE MISSING LISTINGS
        for listing_id, car in existing_cars.items():
            if listing_id in observed:
                continue

            # Already inactive, no need to increment.
            if not car.is_active:
                continue

            old_streak = car.missing_streak or 0
            car.missing_streak = old_streak + 1

            becomes_inactive = (
                car.missing_streak >= missing_threshold
            )

            changes = {
                "missing_streak": {
                    "old": old_streak,
                    "new": car.missing_streak,
                }
            }

            if becomes_inactive:
                car.is_active = False

                changes["is_active"] = {
                    "old": True,
                    "new": False,
                }

                run.inactive += 1
            else:
                run.suspected_missing += 1

            _write_change(
                session,
                run.id,
                listing_id,
                (
                    "inactive"
                    if becomes_inactive
                    else "suspected_missing"
                ),
                changes,
                now,
            )

        session.flush()

        return _result(run)
