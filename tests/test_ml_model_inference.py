
import json
import platform
from types import SimpleNamespace

import joblib
import numpy as np
import pytest
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.model_inference import (
    MODEL_FILENAME,
    METADATA_FILENAME,
    ModelUnavailableError,
    detect_model_findings,
    load_verified_model,
    _sha256_file,
)


@pytest.fixture
def artifact_dir(tmp_path):
    """Create a small isolated test model."""

    rng = np.random.default_rng(42)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        (
            "isolation_forest",
            IsolationForest(
                n_estimators=20,
                random_state=42,
            ),
        ),
    ])

    pipeline.fit(rng.normal(size=(30, 3)))

    model_path = tmp_path / MODEL_FILENAME
    joblib.dump(pipeline, model_path)

    metadata = {
        "model_version": "iforest_v1",
        "model_type": "IsolationForest",
        "feature_version": "v1",
        "feature_names": [
            "vehicle_age",
            "log_cash_price",
            "log_mileage_km",
        ],
        "reference_year": 2026,
        "model_file": MODEL_FILENAME,
        "model_file_sha256": _sha256_file(model_path),
        "model_parameters": {
            "n_estimators": 20,
            "random_state": 42,
        },
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
    }

    (tmp_path / METADATA_FILENAME).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    return tmp_path


def test_load_verified_model(artifact_dir):
    verified = load_verified_model(artifact_dir)

    assert verified.metadata["model_version"] == "iforest_v1"
    assert verified.pipeline.n_features_in_ == 3


def test_missing_model_is_rejected(artifact_dir):
    (artifact_dir / MODEL_FILENAME).unlink()

    with pytest.raises(
        ModelUnavailableError,
        match="missing",
    ):
        load_verified_model(artifact_dir)


def test_bad_hash_is_rejected_before_loading(
    artifact_dir,
    monkeypatch,
):
    metadata_path = artifact_dir / METADATA_FILENAME

    metadata = json.loads(
        metadata_path.read_text()
    )

    metadata["model_file_sha256"] = "invalid"

    metadata_path.write_text(
        json.dumps(metadata)
    )

    monkeypatch.setattr(
        joblib,
        "load",
        lambda path: pytest.fail("must not load"),
    )

    with pytest.raises(
        ModelUnavailableError,
        match="SHA-256",
    ):
        load_verified_model(artifact_dir)


@pytest.mark.parametrize(
    "key,value",
    [
        ("feature_version", "v2"),
        (
            "feature_names",
            [
                "log_cash_price",
                "vehicle_age",
                "log_mileage_km",
            ],
        ),
        ("reference_year", 2027),
        ("model_version", "iforest_v2"),
    ],
)
def test_incompatible_metadata_is_rejected(
    artifact_dir,
    key,
    value,
):
    metadata_path = artifact_dir / METADATA_FILENAME

    metadata = json.loads(
        metadata_path.read_text()
    )

    metadata[key] = value

    metadata_path.write_text(
        json.dumps(metadata)
    )

    with pytest.raises(
        ModelUnavailableError,
        match="metadata mismatch",
    ):
        load_verified_model(artifact_dir)


def test_incompatible_environment_is_rejected(
    artifact_dir,
):
    metadata_path = artifact_dir / METADATA_FILENAME

    metadata = json.loads(
        metadata_path.read_text()
    )

    metadata["environment"]["scikit_learn"] = "0.0"

    metadata_path.write_text(
        json.dumps(metadata)
    )

    with pytest.raises(
        ModelUnavailableError,
        match="incompatible",
    ):
        load_verified_model(artifact_dir)


def car(listing, price):
    return SimpleNamespace(
        source_listing_id=listing,
        title="2020 Toyota Corolla",
        year=2020,
        price_cash=price,
        mileage_km=87000,
        body_style="sedan",
        is_active=True,
        missing_streak=0,
    )


def test_inference_excludes_missing_cash_prices(
    artifact_dir,
):
    verified = load_verified_model(artifact_dir)

    result = detect_model_findings(
        [
            car("a", 15000),
            car("b", None),
        ],
        verified,
    )

    assert result.eligible_count == 1
    assert result.excluded == {
        "missing_cash_price": 1
    }

    assert all(
        f.source_listing_id == "a"
        for f in result.findings
    )

    assert all(
        f.model_version == "iforest_v1"
        for f in result.findings
    )


def test_no_eligible_vehicles(artifact_dir):
    verified = load_verified_model(artifact_dir)

    result = detect_model_findings(
        [car("b", None)],
        verified,
    )

    assert result.eligible_count == 0
    assert result.findings == ()
    assert result.excluded == {
        "missing_cash_price": 1
    }
