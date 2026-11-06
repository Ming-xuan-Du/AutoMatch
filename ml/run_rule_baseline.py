
"""Run AutoMatch deterministic anomaly baseline.

Usage:
    python -m ml.run_rule_baseline

Read-only PostgreSQL queries.
No vehicle or audit records are modified.
"""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select, text

from backend.database.connection import SessionLocal
from backend.database.models import (
    Vehicle,
    InventoryChange,
)
from ml.rule_baseline import check_vehicle
from ml.change_rules import check_inventory_change


def main():
    with SessionLocal() as session:
        try:
            session.execute(
                text("SET TRANSACTION READ ONLY")
            )

            vehicles = session.scalars(
                select(Vehicle)
                .where(
                    Vehicle.is_active.is_(True),
                    Vehicle.missing_streak == 0,
                )
                .order_by(Vehicle.id)
            ).all()

            audit_changes = session.scalars(
                select(InventoryChange)
                .order_by(InventoryChange.id)
            ).all()

            reference_year = datetime.now(
                timezone.utc
            ).year

            # 1. Current vehicle validation.
            vehicle_findings = [
                finding
                for vehicle in vehicles
                for finding in check_vehicle(
                    vehicle,
                    reference_year=reference_year,
                )
            ]

            # 2. Historical change validation.
            change_findings = [
                finding
                for change in audit_changes
                for finding in check_inventory_change(change)
            ]

            missing_cash = sum(
                vehicle.price_cash is None
                for vehicle in vehicles
            )

            print("=== AUTOMATCH RULE BASELINE ===")
            print(f"Reference year: {reference_year}")
            print(f"Current vehicles checked: {len(vehicles)}")
            print(f"Historical audit records: {len(audit_changes)}")

            print("\n--- Current vehicle rules ---")
            print(f"Findings: {len(vehicle_findings)}")
            print(
                "Flagged vehicles: "
                f"{len({f.source_listing_id for f in vehicle_findings})}"
            )

            vehicle_counts = Counter(
                f.rule_id for f in vehicle_findings
            )

            for name, count in sorted(vehicle_counts.items()):
                print(f"{name}: {count}")

            if not vehicle_findings:
                print("No invalid-value findings.")

            print("\n--- Historical change rules ---")
            print(f"Review findings: {len(change_findings)}")

            change_counts = Counter(
                f.rule_id for f in change_findings
            )

            for name, count in sorted(change_counts.items()):
                print(f"{name}: {count}")

            if not change_findings:
                print("No suspicious changes detected.")

            print("\n--- Data completeness ---")
            print(f"Missing cash prices: {missing_cash}")
            print(
                "Missing cash price is not "
                "automatically an anomaly."
            )

            print("\n--- Current vehicle findings ---")
            for finding in vehicle_findings:
                print(
                    f"Listing={finding.source_listing_id} "
                    f"Rule={finding.rule_id} "
                    f"Value={finding.observed_value} "
                    f"Reason={finding.explanation}"
                )

            print("\n--- Historical change findings ---")
            for finding in change_findings:
                print(
                    f"Audit={finding.audit_id} "
                    f"Listing={finding.source_listing_id} "
                    f"Rule={finding.rule_id} "
                    f"Old={finding.old_value} "
                    f"New={finding.new_value}"
                )
                print(f"  {finding.explanation}")

        finally:
            session.rollback()

    print("\nRead-only rule evaluation complete.")


if __name__ == "__main__":
    main()
