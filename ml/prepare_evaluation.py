
"""Inspect AutoMatch training and evaluation split.

Run:
    python -m ml.prepare_evaluation

No model training or database writes.
"""

from collections import Counter

from sqlalchemy import select, text

from backend.database.connection import SessionLocal
from backend.database.models import Vehicle

from ml.features import (
    FEATURE_NAMES,
    build_feature_dataset,
)
from ml.evaluation_dataset import (
    build_evaluation_dataset,
)


REFERENCE_YEAR = 2026


def main():
    with SessionLocal() as session:
        try:
            session.execute(
                text("SET TRANSACTION READ ONLY")
            )

            vehicles = session.scalars(
                select(Vehicle)
                .order_by(Vehicle.source_listing_id)
            ).all()

            features = build_feature_dataset(
                vehicles,
                reference_year=REFERENCE_YEAR,
            )

        finally:
            session.rollback()

    evaluation = build_evaluation_dataset(features)

    print("=== AUTOMATCH ML EVALUATION DATASET ===")

    print("\n--- Configuration ---")
    print(f"Reference year: {evaluation.reference_year}")
    print(f"Random seed: {evaluation.seed}")
    print(f"Dataset SHA-256: {evaluation.fingerprint}")

    print("\n--- Dataset split ---")
    print(f"Input vehicles: {features.total_records}")
    print(f"Usable vehicles: {len(features.rows)}")
    print(
        f"Training vehicles: {len(evaluation.training_rows)}"
    )
    print(
        f"Held-out vehicles: {len(evaluation.holdout_rows)}"
    )
    print(f"Evaluation cases: {len(evaluation.cases)}")

    print("\n--- Case labels ---")
    counts = Counter(
        case.label for case in evaluation.cases
    )

    print(f"Assumed-normal controls: {counts[0]}")
    print(f"Synthetic anomalies: {counts[1]}")

    print("\n--- Synthetic scenarios ---")
    scenarios = Counter(
        case.scenario
        for case in evaluation.cases
        if case.label == 1
    )

    for scenario, count in sorted(scenarios.items()):
        print(f"{scenario}: {count}")

    print("\n--- Leakage checks ---")

    train_ids = {
        row.source_listing_id
        for row in evaluation.training_rows
    }

    holdout_ids = {
        row.source_listing_id
        for row in evaluation.holdout_rows
    }

    overlap = train_ids.intersection(holdout_ids)

    print(f"Train/holdout identity overlap: {len(overlap)}")

    assert not overlap, "Training/evaluation leakage"

    assert len(train_ids) == len(evaluation.training_rows)
    assert len(holdout_ids) == len(evaluation.holdout_rows)

    assert all(
        case.source_listing_id in holdout_ids
        for case in evaluation.cases
    )

    print("\n--- Matrix dimensions ---")
    print(f"Feature names: {FEATURE_NAMES}")

    train_matrix = evaluation.training_matrix
    eval_matrix = evaluation.evaluation_matrix

    print(
        f"Training: {len(train_matrix)} "
        f"x {len(FEATURE_NAMES)}"
    )

    print(
        f"Evaluation: {len(eval_matrix)} "
        f"x {len(FEATURE_NAMES)}"
    )

    assert all(
        len(row) == len(FEATURE_NAMES)
        for row in train_matrix + eval_matrix
    )

    print("\n--- Interpretation ---")
    print(
        "Original control vehicles are not verified "
        "to be anomaly-free."
    )
    print(
        "Synthetic anomalies are intentionally "
        "altered vehicle attributes."
    )
    print(
        "This dataset cannot establish real-world "
        "production precision or recall."
    )

    print("\nEvaluation dataset preparation complete.")


if __name__ == "__main__":
    main()
