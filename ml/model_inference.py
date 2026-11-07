
"""Verified local Isolation Forest inference.

Uses the existing fitted model. Does not train models,
modify vehicles, or write to the database.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import platform
from typing import Iterable

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_feature_dataset,
)


# Fixed compatibility contract for the existing v1 model.
MODEL_VERSION = "iforest_v1"
REFERENCE_YEAR = 2026

MODEL_FILENAME = "isolation_forest_v1.joblib"
METADATA_FILENAME = "isolation_forest_v1_metadata.json"

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"


class ModelUnavailableError(RuntimeError):
    """Model is absent, incompatible, or cannot be used."""


@dataclass(frozen=True)
class VerifiedModel:
    pipeline: Pipeline
    metadata: dict


@dataclass(frozen=True)
class ModelFinding:
    source_listing_id: str
    issue_type: str
    explanation: str
    score: float
    model_version: str
    evidence: dict


@dataclass(frozen=True)
class ModelScanResult:
    findings: tuple[ModelFinding, ...]
    eligible_count: int
    excluded: dict[str, int]


def _sha256_file(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_verified_model(
    artifact_dir: Path = ARTIFACT_DIR,
) -> VerifiedModel:
    """Load only trusted local training artifacts.

    joblib uses pickle-based serialization, which can
    execute code when loading. Never load untrusted files.
    """

    artifact_dir = Path(artifact_dir)

    model_path = artifact_dir / MODEL_FILENAME
    metadata_path = artifact_dir / METADATA_FILENAME

    if (
        not model_path.is_file()
        or not metadata_path.is_file()
    ):
        raise ModelUnavailableError(
            "Model or metadata file is missing"
        )

    try:
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError, UnicodeError) as exc:
        raise ModelUnavailableError(
            "Cannot read model metadata"
        ) from exc

    if not isinstance(metadata, dict):
        raise ModelUnavailableError(
            "Model metadata must be an object"
        )

    required = {
        "model_version": MODEL_VERSION,
        "model_type": "IsolationForest",
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "reference_year": REFERENCE_YEAR,
        "model_file": MODEL_FILENAME,
    }

    for key, value in required.items():
        if metadata.get(key) != value:
            raise ModelUnavailableError(
                f"Model metadata mismatch: {key}"
            )

    environment = metadata.get("environment")

    expected_environment = {
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "numpy": np.__version__,
        "joblib": joblib.__version__,
    }

    if (
        not isinstance(environment, dict)
        or any(
            environment.get(key) != value
            for key, value in expected_environment.items()
        )
    ):
        raise ModelUnavailableError(
            "Model training environment is incompatible"
        )

    try:
        actual_hash = _sha256_file(model_path)
    except OSError as exc:
        raise ModelUnavailableError(
            "Cannot read model file"
        ) from exc

    if metadata.get("model_file_sha256") != actual_hash:
        raise ModelUnavailableError(
            "Model SHA-256 does not match metadata"
        )

    try:
        pipeline = joblib.load(model_path)
    except Exception as exc:
        raise ModelUnavailableError(
            "Could not load trusted local model"
        ) from exc

    if (
        not isinstance(pipeline, Pipeline)
        or list(pipeline.named_steps)
        != ["scaler", "isolation_forest"]
        or not isinstance(
            pipeline.named_steps["scaler"],
            StandardScaler,
        )
        or not isinstance(
            pipeline.named_steps["isolation_forest"],
            IsolationForest,
        )
        or getattr(pipeline, "n_features_in_", None)
        != len(FEATURE_NAMES)
    ):
        raise ModelUnavailableError(
            "Loaded model pipeline is incompatible"
        )

    metadata_params = metadata.get("model_parameters")

    model_params = pipeline.named_steps[
        "isolation_forest"
    ].get_params()

    if (
        not isinstance(metadata_params, dict)
        or any(
            key not in model_params
            or model_params[key] != value
            for key, value in metadata_params.items()
        )
    ):
        raise ModelUnavailableError(
            "Loaded model parameters do not match metadata"
        )

    return VerifiedModel(
        pipeline=pipeline,
        metadata=metadata,
    )


def detect_model_findings(
    vehicles: Iterable,
    verified: VerifiedModel,
) -> ModelScanResult:
    """Generate experimental ML findings without mutation."""

    dataset = build_feature_dataset(
        vehicles,
        reference_year=verified.metadata["reference_year"],
    )

    if not dataset.rows:
        return ModelScanResult(
            findings=(),
            eligible_count=0,
            excluded=dataset.excluded,
        )

    try:
        predictions = verified.pipeline.predict(
            dataset.feature_matrix
        )

        scores = verified.pipeline.decision_function(
            dataset.feature_matrix
        )

    except Exception as exc:
        raise ModelUnavailableError(
            "Model inference failed"
        ) from exc

    if (
        len(predictions) != len(dataset.rows)
        or len(scores) != len(dataset.rows)
    ):
        raise ModelUnavailableError(
            "Model output length is invalid"
        )

    findings = []

    for row, prediction, raw_score in zip(
        dataset.rows,
        predictions,
        scores,
    ):
        score = float(raw_score)

        if (
            prediction not in (-1, 1)
            or not isfinite(score)
        ):
            raise ModelUnavailableError(
                "Invalid model prediction or score"
            )

        if prediction == -1:
            findings.append(
                ModelFinding(
                    source_listing_id=row.source_listing_id,
                    issue_type="statistical_outlier",
                    explanation=(
                        "Isolation Forest flagged this listing "
                        "for human review; the decision score "
                        "is not a probability or confirmed error."
                    ),
                    score=score,
                    model_version=verified.metadata[
                        "model_version"
                    ],
                    evidence={
                        "feature_version": FEATURE_VERSION,
                        "reference_year": dataset.reference_year,
                        "year": row.year,
                        "price_cash": row.price_cash,
                        "mileage_km": row.mileage_km,
                        "features": dict(
                            zip(
                                FEATURE_NAMES,
                                row.vector(),
                            )
                        ),
                    },
                )
            )

    return ModelScanResult(
        findings=tuple(findings),
        eligible_count=len(dataset.rows),
        excluded=dataset.excluded,
    )
