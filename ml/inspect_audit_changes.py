
"""Inspect AutoMatch inventory audit JSON safely.

Run:
    python -m ml.inspect_audit_changes

Read-only PostgreSQL queries.
Prints field names and selected numeric change values.
Does not print VINs, listing URLs, or full audit payloads.
"""

from collections import Counter

from sqlalchemy import select, text

from backend.database.connection import SessionLocal
from backend.database.models import InventoryChange


SAFE_VALUE_FIELDS = {
    "price_cash",
    "price_finance",
    "mileage_km",
    "missing_streak",
}


def main():
    with SessionLocal() as session:
        try:
            session.execute(text("SET TRANSACTION READ ONLY"))

            records = session.scalars(
                select(InventoryChange)
                .order_by(InventoryChange.id)
            ).all()

            print("=== INVENTORY AUDIT INSPECTION ===")
            print(f"Total audit records: {len(records)}")

            change_types = Counter(
                record.change_type for record in records
            )

            print("\n--- Change types ---")
            for name, count in sorted(change_types.items()):
                print(f"{name}: {count}")

            print("\n--- Audit record structure ---")

            for record in records:
                payload = record.changes

                print(
                    f"\nAudit ID: {record.id}"
                    f" | Snapshot: {record.snapshot_id}"
                    f" | Type: {record.change_type}"
                )

                if not isinstance(payload, dict):
                    print(f"Payload type: {type(payload).__name__}")
                    continue

                print(f"Fields: {list(payload.keys())}")

                for field, value in payload.items():
                    if isinstance(value, dict):
                        print(
                            f"  {field}: nested keys="
                            f"{list(value.keys())}"
                        )
                    else:
                        print(
                            f"  {field}: type="
                            f"{type(value).__name__}"
                        )

                    # Only display selected numeric audit fields.
                    # Other potentially identifying fields remain hidden.
                    if field in SAFE_VALUE_FIELDS:
                        print(f"    value: {value!r}")

        finally:
            session.rollback()

    print("\nRead-only audit inspection complete.")


if __name__ == "__main__":
    main()
