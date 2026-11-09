
"""Detect inventory anomalies and persist review findings.

The caller owns the transaction: this service flushes but
never commits. Use a dedicated database session.

Only anomaly_flags records are created or refreshed.
Original inventory and audit records are never modified.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import (
    AnomalyFlag,
    InventoryChange,
    Vehicle,
)
from ml.change_rules import check_inventory_change
from ml.model_inference import (
    ModelUnavailableError,
    detect_model_findings,
    load_verified_model,
)
from ml.rule_baseline import check_vehicle


@dataclass(frozen=True)
class ScanSummary:
    vehicles_checked: int
    audit_records_checked: int
    rule_findings: int
    model_findings: int
    created: int
    seen_again: int
    orphan_change_findings: int
    model_status: str
    model_message: str | None


def finding_fingerprint(identity: dict) -> str:
    """Hash stable finding identity, not scan time or text."""
    payload = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _save_finding(
    session: Session,
    *,
    vehicle_id: int,
    inventory_change_id: int | None,
    detector: str,
    issue_type: str,
    explanation: str,
    evidence: dict,
    fingerprint: str,
    detected_at: datetime,
    score: float | None = None,
    model_version: str | None = None,
) -> bool:
    existing = session.scalar(
        select(AnomalyFlag).where(
            AnomalyFlag.fingerprint == fingerprint
        )
    )

    if existing is not None:
        # Never overwrite human review decisions or notes.
        existing.last_detected_at = detected_at
        return False

    session.add(
        AnomalyFlag(
            vehicle_id=vehicle_id,
            inventory_change_id=inventory_change_id,
            detector=detector,
            issue_type=issue_type,
            explanation=explanation,
            evidence=evidence,
            fingerprint=fingerprint,
            score=score,
            model_version=model_version,
            first_detected_at=detected_at,
            last_detected_at=detected_at,
        )
    )
    return True


def run_anomaly_scan(
    session: Session,
    *,
    include_model: bool = True,
    reference_year: int | None = None,
    dry_run: bool = False,
) -> ScanSummary:
    """Scan inventory and stage findings for persistence.

    Only confirmed-present vehicles receive current-value
    checks. Historical audit rules examine all change records.

    Caller must commit or rollback the transaction.
    """
    if dry_run and (
        session.new or session.dirty or session.deleted
    ):
        raise ValueError(
            "Dry run requires a clean database session"
        )

    if reference_year is None:
        reference_year = datetime.now(timezone.utc).year

    if reference_year < 1886:
        raise ValueError("reference_year must be >= 1886")

    checked_at = datetime.now(timezone.utc)

    vehicles = session.scalars(
        select(Vehicle).order_by(Vehicle.id)
    ).all()

    by_listing = {
        vehicle.source_listing_id: vehicle
        for vehicle in vehicles
    }

    present = [
        vehicle
        for vehicle in vehicles
        if vehicle.is_active is True
        and vehicle.missing_streak == 0
    ]

    present_ids = {
        vehicle.id for vehicle in present
    }

    changes = session.scalars(
        select(InventoryChange).order_by(
            InventoryChange.id
        )
    ).all()

    created = 0
    seen_again = 0
    rule_count = 0
    model_count = 0
    orphan_changes = 0

    model_findings = ()
    model_status = "disabled"
    model_message = None
    model_hash = None

    # Model failure must not prevent deterministic checks.
    if include_model:
        try:
            verified = load_verified_model()

            model_result = detect_model_findings(
                present,
                verified,
            )

            model_findings = model_result.findings
            model_hash = verified.metadata[
                "model_file_sha256"
            ]
            model_status = "ok"

        except ModelUnavailableError as exc:
            model_status = "unavailable"
            model_message = str(exc)

        # Avoid duplicate findings within one scan.
    seen_this_scan = set()

    known_fingerprints = (
        set(
            session.scalars(
                select(AnomalyFlag.fingerprint)
            ).all()
        )
        if dry_run
        else None
    )

    def persist(**kwargs):
        nonlocal created, seen_again

        fingerprint = kwargs["fingerprint"]

        if fingerprint in seen_this_scan:
            seen_again += 1
            return

        seen_this_scan.add(fingerprint)

        if dry_run:
            if fingerprint in known_fingerprints:
                seen_again += 1
            else:
                created += 1
            return

        was_created = _save_finding(
            session,
            detected_at=checked_at,
            **kwargs,
        )

        if was_created:
            created += 1
        else:
            seen_again += 1


    # 1. Current vehicle validation rules.
    # Confirmed-present vehicles receive all rules.
    # Other vehicles are checked only for negative
    # missing streaks.
    for vehicle in vehicles:
        is_present = vehicle.id in present_ids

        if not is_present and (
            vehicle.missing_streak is None
            or vehicle.missing_streak >= 0
        ):
            continue

        findings = check_vehicle(
            vehicle,
            reference_year=reference_year,
        )

        for finding in findings:
            if (
                not is_present
                and finding.rule_id != "negative_missing_streak"
            ):
                continue

            rule_count += 1


            evidence = {
                "field": finding.field,
                "observed_value": finding.observed_value,
                "reference_year": reference_year,
            }

            identity = {
                "family": "vehicle_rule_v1",
                "vehicle_id": vehicle.id,
                "issue_type": finding.rule_id,
                "field": finding.field,
                "observed_value": finding.observed_value,
            }

            persist(
                vehicle_id=vehicle.id,
                inventory_change_id=None,
                detector="rule",
                issue_type=finding.rule_id,
                explanation=finding.explanation,
                evidence=evidence,
                fingerprint=finding_fingerprint(identity),
            )

    # 2. Historical inventory change rules.
    for change in changes:
        findings = check_inventory_change(change)

        for finding in findings:
            vehicle = by_listing.get(
                finding.source_listing_id
            )

            if vehicle is None:
                # Never create an invalid foreign key.
                orphan_changes += 1
                continue

            rule_count += 1

            evidence = {
                "field": finding.field,
                "old_value": finding.old_value,
                "new_value": finding.new_value,
                "snapshot_id": finding.snapshot_id,
                "audit_id": finding.audit_id,
            }

            identity = {
                "family": "inventory_change_rule_v1",
                "vehicle_id": vehicle.id,
                "audit_id": finding.audit_id,
                "issue_type": finding.rule_id,
                "field": finding.field,
                "old_value": finding.old_value,
                "new_value": finding.new_value,
            }

            persist(
                vehicle_id=vehicle.id,
                inventory_change_id=finding.audit_id,
                detector="rule",
                issue_type=finding.rule_id,
                explanation=finding.explanation,
                evidence=evidence,
                fingerprint=finding_fingerprint(identity),
            )

    # 3. Experimental Isolation Forest findings.
    for finding in model_findings:
        vehicle = by_listing.get(
            finding.source_listing_id
        )

        if (
            vehicle is None
            or vehicle.id not in present_ids
        ):
            raise ValueError(
                "Model returned a vehicle outside "
                "confirmed inventory"
            )

        model_count += 1

        evidence = {
            **finding.evidence,
            "model_file_sha256": model_hash,
        }

        identity = {
            "family": "isolation_forest_v1",
            "vehicle_id": vehicle.id,
            "issue_type": finding.issue_type,
            "model_version": finding.model_version,
            "model_file_sha256": model_hash,
            "year": finding.evidence.get("year"),
            "price_cash": finding.evidence.get(
                "price_cash"
            ),
            "mileage_km": finding.evidence.get(
                "mileage_km"
            ),
        }

        persist(
            vehicle_id=vehicle.id,
            inventory_change_id=None,
            detector="model",
            issue_type=finding.issue_type,
            explanation=finding.explanation,
            evidence=evidence,
            fingerprint=finding_fingerprint(identity),
            score=finding.score,
            model_version=finding.model_version,
        )

    # No commit here. The caller controls the transaction.
    if not dry_run:
        session.flush()

    return ScanSummary(
        vehicles_checked=len(present),
        audit_records_checked=len(changes),
        rule_findings=rule_count,
        model_findings=model_count,
        created=created,
        seen_again=seen_again,
        orphan_change_findings=orphan_changes,
        model_status=model_status,
        model_message=model_message,
    )
