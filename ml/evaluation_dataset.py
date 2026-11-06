
"""Reproducible evaluation dataset for AutoMatch ML.

No database access, model training, or file writes.

Original vehicles are assumed-normal controls, not
verified normal labels. Synthetic positives represent
deliberately altered vehicle attributes.
"""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from math import log1p
from random import Random
import json

from ml.features import (
    FEATURE_VERSION,
    FeatureDataset,
    FeatureRow,
)


SPLIT_SEED = 42
HOLDOUT_FRACTION = 0.20

SCENARIOS = (
    "cash_price_x4",
    "cash_price_div5",
    "mileage_x4",
    "mileage_div5",
)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    source_listing_id: str
    title: str
    body_style: str
    year: int
    price_cash: int
    mileage_km: int

    # 0 = assumed-normal original
    # 1 = deliberately altered synthetic example
    label: int
    scenario: str

    feature_vector: tuple[float, float, float]


@dataclass(frozen=True)
class EvaluationDataset:
    training_rows: tuple[FeatureRow, ...]
    holdout_rows: tuple[FeatureRow, ...]
    cases: tuple[EvaluationCase, ...]
    fingerprint: str
    seed: int
    reference_year: int

    @property
    def training_matrix(self) -> list[list[float]]:
        return [
            list(row.vector())
            for row in self.training_rows
        ]

    @property
    def evaluation_matrix(self) -> list[list[float]]:
        return [
            list(case.feature_vector)
            for case in self.cases
        ]

    @property
    def evaluation_labels(self) -> list[int]:
        return [case.label for case in self.cases]


def fingerprint_dataset(dataset: FeatureDataset) -> str:
    """Fingerprint input data and feature configuration."""

    ordered = sorted(
        dataset.rows,
        key=lambda row: row.source_listing_id,
    )

    payload = {
        "feature_version": FEATURE_VERSION,
        "reference_year": dataset.reference_year,
        "vehicles": [
            {
                "id": row.source_listing_id,
                "year": row.year,
                "price_cash": row.price_cash,
                "mileage_km": row.mileage_km,
                "body_style": row.body_style,
            }
            for row in ordered
        ],
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return sha256(encoded).hexdigest()


def make_case(
    row: FeatureRow,
    *,
    scenario: str,
    label: int,
    price_cash: int | None = None,
    mileage_km: int | None = None,
) -> EvaluationCase:
    """Create a case without mutating the source row."""

    price = (
        row.price_cash
        if price_cash is None
        else price_cash
    )

    mileage = (
        row.mileage_km
        if mileage_km is None
        else mileage_km
    )

    if price <= 0 or mileage < 0:
        raise ValueError("Invalid synthetic feature values")

    modified = replace(
        row,
        price_cash=price,
        mileage_km=mileage,
        log_cash_price=log1p(price),
        log_mileage_km=log1p(mileage),
    )

    return EvaluationCase(
        case_id=f"{row.source_listing_id}:{scenario}",
        source_listing_id=row.source_listing_id,
        title=row.title,
        body_style=row.body_style,
        year=row.year,
        price_cash=price,
        mileage_km=mileage,
        label=label,
        scenario=scenario,
        feature_vector=modified.vector(),
    )


def inject_anomaly(
    row: FeatureRow,
    scenario: str,
) -> EvaluationCase:
    """Generate one valid-valued synthetic alteration."""

    if scenario == "cash_price_x4":
        return make_case(
            row,
            scenario=scenario,
            label=1,
            price_cash=row.price_cash * 4,
        )

    if scenario == "cash_price_div5":
        return make_case(
            row,
            scenario=scenario,
            label=1,
            price_cash=max(1, row.price_cash // 5),
        )

    if scenario == "mileage_x4":
        return make_case(
            row,
            scenario=scenario,
            label=1,
            mileage_km=row.mileage_km * 4,
        )

    if scenario == "mileage_div5":
        return make_case(
            row,
            scenario=scenario,
            label=1,
            mileage_km=max(0, row.mileage_km // 5),
        )

    raise ValueError(f"Unknown scenario: {scenario}")


def build_evaluation_dataset(
    dataset: FeatureDataset,
    *,
    seed: int = SPLIT_SEED,
    holdout_fraction: float = HOLDOUT_FRACTION,
) -> EvaluationDataset:
    """Create identity-disjoint training and evaluation data."""

    if not 0 < holdout_fraction < 1:
        raise ValueError(
            "holdout_fraction must be between 0 and 1"
        )

    rows = sorted(
        dataset.rows,
        key=lambda row: row.source_listing_id,
    )

    if len(rows) < 20:
        raise ValueError(
            "At least 20 usable vehicles are required "
            "for this exploratory evaluation design."
        )

    ids = [row.source_listing_id for row in rows]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Duplicate source listing IDs in ML dataset"
        )

    shuffled = list(rows)
    Random(seed).shuffle(shuffled)

    holdout_count = round(
        len(shuffled) * holdout_fraction
    )

    if not 4 <= holdout_count < len(shuffled):
        raise ValueError(
            "Holdout size must contain at least four "
            "vehicles and leave training data."
        )

    holdout_rows = tuple(
        sorted(
            shuffled[:holdout_count],
            key=lambda row: row.source_listing_id,
        )
    )

    training_rows = tuple(
        sorted(
            shuffled[holdout_count:],
            key=lambda row: row.source_listing_id,
        )
    )

    cases = []

    for index, row in enumerate(holdout_rows):
        # Original control from the held-out inventory.
        cases.append(
            make_case(
                row,
                scenario="original",
                label=0,
            )
        )

        # One synthetic alteration per held-out vehicle.
        scenario = SCENARIOS[index % len(SCENARIOS)]

        cases.append(
            inject_anomaly(row, scenario)
        )

    return EvaluationDataset(
        training_rows=training_rows,
        holdout_rows=holdout_rows,
        cases=tuple(cases),
        fingerprint=fingerprint_dataset(dataset),
        seed=seed,
        reference_year=dataset.reference_year,
    )
