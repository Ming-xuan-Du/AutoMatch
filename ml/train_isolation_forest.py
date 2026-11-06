
"""Train AutoMatch Isolation Forest v1.

Run from repository root:
    python -m ml.train_isolation_forest

Reads PostgreSQL inventory without modifying it.
Fits only on training vehicles, never held-out cases.
Saves a local model artifact and JSON metadata.
"""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
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


MODEL_VERSION = "iforest_v1"
REFERENCE_YEAR = 2026

N_ESTIMATORS = 200
CONTAMINATION = 0.05
RANDOM_STATE = 42

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

MODEL_FILENAME = "isolation_forest_v1.joblib"
METADATA_FILENAME = "isolation_forest_v1_metadata.json"


def fit_isolation_forest(
    training_matrix,
    *,
    random_state=RANDOM_STATE,
):
    """Fit preprocessing and model on training rows only."""

    matrix = np.asarray(
        training_matrix,
        dtype=float,
    )

    if matrix.ndim != 2:
        raise ValueError("Training matrix must be 2D")

    if matrix.shape[1] != len(FEATURE_NAMES):
        raise ValueError(
            "Unexpected number of feature columns"
        )

    if matrix.shape[0] < 20:
        raise ValueError(
            "At least 20 training rows are required"
        )

    if not np.isfinite(matrix).all():
        raise ValueError(
            "Training matrix contains non-finite values"
        )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        (
            "isolation_forest",
            IsolationForest(
                n_estimators=N_ESTIMATORS,
                max_samples="auto",
                contamination=CONTAMINATION,
                random_state=random_state,
                n_jobs=1,
            ),
        ),
    ])

    pipeline.fit(matrix)
    return pipeline


def hash_training_ids(rows):
    """Fingerprint training identities without storing IDs."""

    ids = sorted(
        row.source_listing_id
        for row in rows
    )

    encoded = json.dumps(
        ids,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def make_training_metadata(model, evaluation):
    """Describe the fitted model and its input dataset."""

    matrix = np.asarray(
        evaluation.training_matrix,
        dtype=float,
    )

    predictions = model.predict(matrix)
    scores = model.decision_function(matrix)

    detector = model.named_steps["isolation_forest"]

    return {
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
        "model_type": "IsolationForest",
        "model_parameters": {
            "n_estimators": N_ESTIMATORS,
            "max_samples": "auto",
            "contamination": CONTAMINATION,
            "random_state": RANDOM_STATE,
            "n_jobs": 1,
        },
        "fitted_max_samples": int(detector.max_samples_),
        "training_diagnostics": {
            "outlier_predictions": int(
                np.sum(predictions == -1)
            ),
            "inlier_predictions": int(
                np.sum(predictions == 1)
            ),
            "decision_score_min": float(
                np.min(scores)
            ),
            "decision_score_median": float(
                np.median(scores)
            ),
            "decision_score_max": float(
                np.max(scores)
            ),
            "decision_threshold": 0.0,
        },
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "trained_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "evaluation_status": "not_evaluated",
        "note": (
            "Training outlier counts are not accuracy "
            "or recall metrics. The held-out evaluation "
            "cases were not used for fitting."
        ),
    }


def save_training_artifacts(
    model,
    metadata,
    *,
    output_dir=ARTIFACT_DIR,
):
    """Save the fitted pipeline and metadata locally."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / MODEL_FILENAME
    metadata_path = output_dir / METADATA_FILENAME

    joblib.dump(model, model_path)

    model_hash = hashlib.sha256(
        model_path.read_bytes()
    ).hexdigest()

    saved_metadata = {
        **metadata,
        "model_file": MODEL_FILENAME,
        "model_file_sha256": model_hash,
    }

    metadata_path.write_text(
        json.dumps(
            saved_metadata,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return model_path, metadata_path


def main():
    print("=== AUTOMATCH ISOLATION FOREST TRAINING ===")

    # Read-only data collection.
    with SessionLocal() as session:
        try:
            session.execute(
                text("SET TRANSACTION READ ONLY")
            )

            vehicles = session.scalars(
                select(Vehicle)
                .order_by(Vehicle.source_listing_id)
            ).all()

            feature_dataset = build_feature_dataset(
                vehicles,
                reference_year=REFERENCE_YEAR,
            )

        finally:
            session.rollback()

    # The split is identical to Milestone 7.3.
    evaluation = build_evaluation_dataset(
        feature_dataset,
        seed=SPLIT_SEED,
        holdout_fraction=HOLDOUT_FRACTION,
    )

    print("\n--- Dataset ---")
    print(f"Fingerprint: {evaluation.fingerprint}")
    print(
        f"Training rows: "
        f"{len(evaluation.training_rows)}"
    )
    print(
        f"Held-out rows reserved: "
        f"{len(evaluation.holdout_rows)}"
    )
    print(f"Features: {FEATURE_NAMES}")

    # Train exclusively on the 161 training rows.
    training_matrix = np.asarray(
        evaluation.training_matrix,
        dtype=float,
    )

    model = fit_isolation_forest(training_matrix)

    metadata = make_training_metadata(
        model,
        evaluation,
    )

    model_path, metadata_path = (
        save_training_artifacts(model, metadata)
    )

    # Verify the saved pipeline can reproduce training
    # predictions. Only reload artifacts created locally.
    loaded_model = joblib.load(model_path)

    original_predictions = model.predict(
        training_matrix
    )
    loaded_predictions = loaded_model.predict(
        training_matrix
    )

    original_scores = model.decision_function(
        training_matrix
    )
    loaded_scores = loaded_model.decision_function(
        training_matrix
    )

    assert np.array_equal(
        original_predictions,
        loaded_predictions,
    ), "Reloaded model predictions differ"

    assert np.allclose(
        original_scores,
        loaded_scores,
    ), "Reloaded model scores differ"

    diagnostics = metadata["training_diagnostics"]

    print("\n--- Model configuration ---")
    print(f"Version: {MODEL_VERSION}")
    print(f"Trees: {N_ESTIMATORS}")
    print(f"Contamination: {CONTAMINATION}")
    print(f"Random state: {RANDOM_STATE}")

    print("\n--- Training-only diagnostics ---")
    print(
        "Model-labeled training outliers: "
        f"{diagnostics['outlier_predictions']}"
    )
    print(
        "Model-labeled training inliers: "
        f"{diagnostics['inlier_predictions']}"
    )
    print(
        "Median decision score: "
        f"{diagnostics['decision_score_median']:.6f}"
    )

    print("\n--- Saved artifacts ---")
    print(f"Model: {model_path}")
    print(f"Metadata: {metadata_path}")
    print("Reload verification: passed")

    print("\nEvaluation cases used for fitting: 0")
    print("Held-out evaluation status: not evaluated")
    print("\nIsolation Forest training complete.")


if __name__ == "__main__":
    main()
