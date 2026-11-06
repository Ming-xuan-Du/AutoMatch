
"""Evaluate the frozen AutoMatch Isolation Forest model.

Run:
    python -m ml.evaluate_anomalies

Does not retrain, tune, or modify PostgreSQL.
Only load locally generated, trusted model artifacts.
"""

import hashlib
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import sklearn
from sqlalchemy import select, text

from backend.database.connection import SessionLocal
from backend.database.models import Vehicle

from ml.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_feature_dataset,
)
from ml.evaluation_dataset import (
    HOLDOUT_FRACTION,
    SPLIT_SEED,
    build_evaluation_dataset,
)
from ml.evaluation_metrics import (
    count_detections,
    paired_change_rule_flags,
    paired_score_movement,
    scenario_summary,
    snapshot_rule_flags,
)
from ml.train_isolation_forest import (
    ARTIFACT_DIR,
    METADATA_FILENAME,
    MODEL_FILENAME,
    MODEL_VERSION,
    REFERENCE_YEAR,
    hash_training_ids,
)


REPORT_FILENAME = "isolation_forest_v1_evaluation.json"


def verify_model_metadata(metadata, evaluation, model_path):
    """Reject stale or mismatched training artifacts."""

    expected = {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "reference_year": evaluation.reference_year,
        "dataset_sha256": evaluation.fingerprint,
        "training_ids_sha256": hash_training_ids(
            evaluation.training_rows
        ),
        "split_seed": evaluation.seed,
        "holdout_fraction": HOLDOUT_FRACTION,
        "training_rows": len(evaluation.training_rows),
        "holdout_rows_reserved": len(
            evaluation.holdout_rows
        ),
        "model_file": MODEL_FILENAME,
    }

    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(
                f"Model metadata mismatch: {key}. "
                "Do not evaluate against a different "
                "inventory or training configuration."
            )

    trained_version = metadata.get(
        "environment", {}
    ).get("scikit_learn")

    if trained_version != sklearn.__version__:
        raise ValueError(
            "scikit-learn version differs from training."
        )

    actual_hash = hashlib.sha256(
        model_path.read_bytes()
    ).hexdigest()

    if actual_hash != metadata.get("model_file_sha256"):
        raise ValueError(
            "Saved model hash does not match metadata."
        )


def load_verified_model(evaluation):
    """Load the existing trusted local model."""

    model_path = ARTIFACT_DIR / MODEL_FILENAME
    metadata_path = ARTIFACT_DIR / METADATA_FILENAME

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Trained model not found: {model_path}"
        )

    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Model metadata not found: {metadata_path}"
        )

    metadata = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    verify_model_metadata(
        metadata,
        evaluation,
        model_path,
    )

    # Joblib is pickle-based. Only load the trusted
    # locally generated model, never arbitrary uploads.
    model = joblib.load(model_path)

    return model, metadata


def format_rate(value):
    return "N/A" if value is None else f"{value:.2%}"


def print_metrics(name, metrics):
    values = metrics.as_dict()

    print(f"\n--- {name} ---")
    print(f"True positives:  {values['true_positive']}")
    print(f"False negatives: {values['false_negative']}")
    print(f"False positives: {values['false_positive']}")
    print(f"True negatives:  {values['true_negative']}")

    print(
        "Synthetic recall: "
        f"{format_rate(values['synthetic_recall'])}"
    )
    print(
        "Assumed-normal flag rate: "
        f"{format_rate(values['assumed_normal_flag_rate'])}"
    )
    print(
        "Balanced synthetic-set precision: "
        f"{format_rate(values['balanced_set_precision'])}"
    )


def print_scenarios(title, scenarios):
    print(f"\n--- {title} ---")

    for name, result in sorted(scenarios.items()):
        print(
            f"{name:<20}"
            f"{result['detected']}/{result['total']} "
            f"({format_rate(result['recall'])})"
        )


def main():
    print("=== AUTOMATCH MILESTONE 7.5 EVALUATION ===")

    # Read-only inventory collection.
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

    evaluation = build_evaluation_dataset(
        features,
        seed=SPLIT_SEED,
        holdout_fraction=HOLDOUT_FRACTION,
    )

    model, metadata = load_verified_model(evaluation)

    cases = evaluation.cases

    print("\n--- Verified experiment ---")
    print(f"Dataset: {evaluation.fingerprint}")
    print(f"Model: {metadata['model_version']}")
    print(f"Training rows: {len(evaluation.training_rows)}")
    print(f"Evaluation cases: {len(cases)}")
    print("Model/dataset verification: passed")

    # No fit() call is permitted in this evaluation.
    matrix = np.asarray(
        evaluation.evaluation_matrix,
        dtype=float,
    )

    raw_predictions = model.predict(matrix)
    raw_scores = model.decision_function(matrix)

    if (
        len(raw_predictions) != len(cases)
        or len(raw_scores) != len(cases)
        or not np.isfinite(raw_scores).all()
        or not np.isin(
            raw_predictions, [-1, 1]
        ).all()
    ):
        raise ValueError("Invalid model evaluation output")

    ml_flags = [
        bool(prediction == -1)
        for prediction in raw_predictions
    ]

    scores = [
        float(score)
        for score in raw_scores
    ]

    snapshot_flags = snapshot_rule_flags(
        cases,
        reference_year=REFERENCE_YEAR,
    )

    change_flags = paired_change_rule_flags(cases)

    ml_metrics = count_detections(cases, ml_flags)
    snapshot_metrics = count_detections(
        cases, snapshot_flags
    )
    change_metrics = count_detections(
        cases, change_flags
    )

    print("\n=== EVALUATION RESULTS ===")

    print_metrics(
        "Snapshot validation rules",
        snapshot_metrics,
    )
    print_metrics(
        "Isolation Forest",
        ml_metrics,
    )
    print_metrics(
        "Paired historical change rules",
        change_metrics,
    )

    ml_scenarios = scenario_summary(cases, ml_flags)
    snapshot_scenarios = scenario_summary(
        cases, snapshot_flags
    )
    change_scenarios = scenario_summary(
        cases, change_flags
    )

    print_scenarios(
        "Isolation Forest by scenario",
        ml_scenarios,
    )
    print_scenarios(
        "Snapshot rules by scenario",
        snapshot_scenarios,
    )
    print_scenarios(
        "Paired change rules by scenario",
        change_scenarios,
    )

    movements = paired_score_movement(cases, scores)

    print("\n--- Paired anomaly-score movement ---")
    print(
        "Alterations scoring more anomalous: "
        f"{movements['altered_more_anomalous']}"
    )
    print(
        "Alterations scoring less anomalous: "
        f"{movements['altered_less_anomalous']}"
    )
    print(f"Ties: {movements['ties']}")

    print("\n--- Flagged original controls ---")

    flagged_controls = sorted(
        (
            (case, score)
            for case, score, flagged in zip(
                cases, scores, ml_flags
            )
            if case.label == 0 and flagged
        ),
        key=lambda item: item[1],
    )

    if not flagged_controls:
        print("No original controls flagged.")
    else:
        for case, score in flagged_controls[:5]:
            print(
                f"{case.title[:70]} | "
                f"cash=${case.price_cash:,} | "
                f"mileage={case.mileage_km:,} | "
                f"score={score:.5f}"
            )

    report = {
        "evaluation_version": "heldout_v1",
        "evaluated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_version": MODEL_VERSION,
        "dataset_sha256": evaluation.fingerprint,
        "model_file_sha256": metadata[
            "model_file_sha256"
        ],
        "reference_year": REFERENCE_YEAR,
        "split_seed": SPLIT_SEED,
        "training_rows": len(evaluation.training_rows),
        "holdout_vehicles": len(evaluation.holdout_rows),
        "evaluation_cases": len(cases),
        "feature_names": list(FEATURE_NAMES),
        "metrics": {
            "snapshot_rules": snapshot_metrics.as_dict(),
            "isolation_forest": ml_metrics.as_dict(),
            "paired_change_rules": change_metrics.as_dict(),
        },
        "scenario_results": {
            "snapshot_rules": snapshot_scenarios,
            "isolation_forest": ml_scenarios,
            "paired_change_rules": change_scenarios,
        },
        "paired_score_movement": movements,
        "limitations": [
            "Original controls are not verified normal.",
            "Synthetic changes are not real confirmed errors.",
            "The evaluation prevalence is artificially 50%.",
            "Paired change rules use extra prior-state data.",
            "No production precision or recall is established.",
            "No threshold tuning was performed on holdout data.",
        ],
    }

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = ARTIFACT_DIR / REPORT_FILENAME

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("\n--- Report ---")
    print(report_path)
    print("PostgreSQL modifications: none")
    print("Model retraining: none")
    print("\nEvaluation complete.")


if __name__ == "__main__":
    main()
