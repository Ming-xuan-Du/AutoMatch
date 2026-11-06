
"""Rule-based detection of suspicious inventory changes.

Consumes InventoryChange audit records but does not
modify the database.

Findings are review candidates, not confirmed errors.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol


LARGE_CASH_CHANGE_RATIO = 0.50


class AuditChangeLike(Protocol):
    id: int
    snapshot_id: int
    source_listing_id: str
    change_type: str
    changes: dict | None


@dataclass(frozen=True)
class ChangeFinding:
    audit_id: int
    snapshot_id: int
    source_listing_id: str
    rule_id: str
    field: str
    old_value: int
    new_value: int
    explanation: str


def get_numeric_transition(payload: dict, field: str):
    """Return (old, new) only for valid integer pairs.

    Missing previous values are intentionally excluded.
    In particular, None -> price is not a price jump.
    """
    transition = payload.get(field)

    if not isinstance(transition, dict):
        return None

    if "old" not in transition or "new" not in transition:
        return None

    old = transition["old"]
    new = transition["new"]

    # Reject booleans and malformed numeric values.
    if type(old) is not int or type(new) is not int:
        return None

    return old, new


def check_inventory_change(
    change: AuditChangeLike,
    *,
    large_cash_change_ratio: float = LARGE_CASH_CHANGE_RATIO,
) -> list[ChangeFinding]:
    """Detect suspicious changes requiring manual review."""

    if (
        not isfinite(large_cash_change_ratio)
        or large_cash_change_ratio <= 0
    ):
        raise ValueError(
            "large_cash_change_ratio must be finite and positive"
        )

    if change.change_type != "updated":
        return []

    payload = change.changes

    if not isinstance(payload, dict):
        return []

    findings = []

    def add(rule_id, field, old, new, explanation):
        findings.append(
            ChangeFinding(
                audit_id=change.id,
                snapshot_id=change.snapshot_id,
                source_listing_id=change.source_listing_id,
                rule_id=rule_id,
                field=field,
                old_value=old,
                new_value=new,
                explanation=explanation,
            )
        )

    # Rule 1: Large cash-price change.
    price_transition = get_numeric_transition(
        payload, "price_cash"
    )

    if price_transition is not None:
        old_price, new_price = price_transition

        # A positive previous value is necessary to
        # calculate a meaningful relative change.
        if old_price > 0:
            change_ratio = (
                abs(new_price - old_price) / old_price
            )

            if change_ratio >= large_cash_change_ratio:
                add(
                    "large_cash_price_change",
                    "price_cash",
                    old_price,
                    new_price,
                    (
                        f"Cash price changed by "
                        f"{change_ratio:.1%}, meeting the "
                        f"{large_cash_change_ratio:.0%} "
                        "review threshold."
                    ),
                )

    # Rule 2: Mileage decrease.
    mileage_transition = get_numeric_transition(
        payload, "mileage_km"
    )

    if mileage_transition is not None:
        old_mileage, new_mileage = mileage_transition

        if new_mileage < old_mileage:
            add(
                "mileage_decrease",
                "mileage_km",
                old_mileage,
                new_mileage,
                (
                    "Recorded mileage decreased. "
                    "Verify whether this reflects a "
                    "data correction or a listing error."
                ),
            )

    return findings
