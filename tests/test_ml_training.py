
import json
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.train_isolation_forest import (
    CONTAMINATION,
    MODEL_VERSION,
    N_ESTIMATORS,
    fit_isolation_forest,
    hash_training_ids,
    make_training_metadata,
    save_training_artifacts,
)


@pytest.fixture
def training_matrix():
    rng = np.random.default_rng(123)

    return np.column_stack([
        rng.integers(0, 25, size=40),
        rng.normal(10.0, 0.7, size=40),
        rng.normal(11.3, 0.8, size=40),
    ])


def test_pipeline_configuration(training_matrix):
    model = fit_isolation_forest(training_matrix)

    assert isinstance(
        model.named_steps["scaler"],
        StandardScaler,
    )

    detector = model.named_steps["isolation_forest"]

    assert isinstance(detector, IsolationForest)
    assert detector.n_estimators == N_ESTIMATORS
    assert detector.contamination == CONTAMINATION
    assert detector.random_state == 42


def test_model_produces_valid_predictions(training_matrix):
    model = fit_isolation_forest(training_matrix)

    predictions = model.predict(training_matrix)
    scores = model.decision_function(training_matrix)

    assert len(predictions) == 40
    assert len(scores) == 40
    assert set(predictions).issubset({-1, 1})
    assert np.isfinite(scores).all()


def test_training_is_deterministic(training_matrix):
    first = fit_isolation_forest(
        training_matrix,
        random_state=42,
    )
    second = fit_isolation_forest(
        training_matrix,
        random_state=42,
    )

    np.testing.assert_array_equal(
        first.predict(training_matrix),
        second.predict(training_matrix),
    )

    np.testing.assert_allclose(
        first.decision_function(training_matrix),
        second.decision_function(training_matrix),
    )


def test_training_does_not_mutate_input(training_matrix):
    original = training_matrix.copy()

    fit_isolation_forest(training_matrix)

    np.testing.assert_array_equal(
        training_matrix,
        original,
    )


def test_wrong_feature_count_rejected():
    matrix = np.ones((30, 2))

    with pytest.raises(ValueError):
        fit_isolation_forest(matrix)


def test_too_few_training_rows_rejected():
    matrix = np.ones((10, 3))

    with pytest.raises(ValueError):
        fit_isolation_forest(matrix)


def test_nonfinite_values_rejected():
    matrix = np.ones((30, 3))
    matrix[0, 1] = np.nan

    with pytest.raises(ValueError):
        fit_isolation_forest(matrix)


def test_saved_model_preserves_predictions(
    training_matrix,
    tmp_path,
):
    model = fit_isolation_forest(training_matrix)

    model_path, metadata_path = save_training_artifacts(
        model,
        {"test_run": True},
        output_dir=tmp_path,
    )

    assert model_path.exists()
    assert metadata_path.exists()

    loaded = joblib.load(model_path)

    np.testing.assert_array_equal(
        model.predict(training_matrix),
        loaded.predict(training_matrix),
    )

    np.testing.assert_allclose(
        model.decision_function(training_matrix),
        loaded.decision_function(training_matrix),
    )

    metadata = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    assert metadata["test_run"] is True
    assert len(metadata["model_file_sha256"]) == 64


def test_training_metadata_and_identity_hash(training_matrix):
    rows = tuple(
        SimpleNamespace(
            source_listing_id=f"vehicle-{i:03d}"
        )
        for i in range(40)
    )

    reversed_rows = tuple(reversed(rows))

    assert hash_training_ids(rows) == (
        hash_training_ids(reversed_rows)
    )

    evaluation = SimpleNamespace(
        training_matrix=training_matrix.tolist(),
        training_rows=rows,
        holdout_rows=tuple(range(8)),
        reference_year=2026,
        fingerprint="test-dataset-fingerprint",
        seed=42,
    )

    model = fit_isolation_forest(training_matrix)

    metadata = make_training_metadata(
        model,
        evaluation,
    )

    assert metadata["model_version"] == MODEL_VERSION
    assert metadata["training_rows"] == 40
    assert metadata["holdout_rows_reserved"] == 8
    assert metadata["dataset_sha256"] == (
        "test-dataset-fingerprint"
    )
    assert metadata["evaluation_status"] == "not_evaluated"

    diagnostics = metadata["training_diagnostics"]

    assert (
        diagnostics["outlier_predictions"]
        + diagnostics["inlier_predictions"]
        == 40
    )
