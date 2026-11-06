
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ml.features import build_feature_dataset
from ml.evaluation_dataset import (
    SCENARIOS,
    build_evaluation_dataset,
    fingerprint_dataset,
)


def make_vehicle(index, **overrides):
    data = {
        "source_listing_id": f"vehicle-{index:03d}",
        "title": f"2018 Test Vehicle {index}",
        "year": 2010 + index % 10,
        "price_cash": 10000 + index * 1000,
        "mileage_km": 40000 + index * 300,
        "body_style": "SUV",
        "is_active": True,
        "missing_streak": 0,
    }

    data.update(overrides)
    return SimpleNamespace(**data)


def make_features(count=20):
    return build_feature_dataset(
        [make_vehicle(i) for i in range(count)],
        reference_year=2026,
    )


def make_evaluation(count=20):
    return build_evaluation_dataset(
        make_features(count)
    )


def test_training_and_holdout_counts():
    evaluation = make_evaluation()

    assert len(evaluation.training_rows) == 16
    assert len(evaluation.holdout_rows) == 4
    assert len(evaluation.cases) == 8


def test_no_identity_overlap():
    evaluation = make_evaluation()

    training_ids = {
        row.source_listing_id
        for row in evaluation.training_rows
    }

    holdout_ids = {
        row.source_listing_id
        for row in evaluation.holdout_rows
    }

    assert training_ids.isdisjoint(holdout_ids)


def test_evaluation_cases_have_balanced_labels():
    evaluation = make_evaluation()

    assert evaluation.evaluation_labels.count(0) == 4
    assert evaluation.evaluation_labels.count(1) == 4


def test_original_and_synthetic_cases_are_paired():
    evaluation = make_evaluation()

    for index in range(0, len(evaluation.cases), 2):
        original = evaluation.cases[index]
        altered = evaluation.cases[index + 1]

        assert original.label == 0
        assert altered.label == 1
        assert original.source_listing_id == (
            altered.source_listing_id
        )

        assert original.year == altered.year
        assert original.body_style == altered.body_style

        changed = sum([
            original.price_cash != altered.price_cash,
            original.mileage_km != altered.mileage_km,
        ])

        assert changed == 1


def test_all_scenarios_are_represented():
    evaluation = make_evaluation()

    observed = {
        case.scenario
        for case in evaluation.cases
        if case.label == 1
    }

    assert observed == set(SCENARIOS)


def test_synthetic_values_remain_valid():
    evaluation = make_evaluation()

    for case in evaluation.cases:
        assert case.price_cash > 0
        assert case.mileage_km >= 0
        assert case.year <= 2027


def test_original_heldout_values_are_preserved():
    evaluation = make_evaluation()

    original_by_id = {
        row.source_listing_id: row
        for row in evaluation.holdout_rows
    }

    for case in evaluation.cases:
        if case.label != 0:
            continue

        source = original_by_id[case.source_listing_id]

        assert case.price_cash == source.price_cash
        assert case.mileage_km == source.mileage_km
        assert case.feature_vector == source.vector()


def test_split_is_deterministic():
    features = make_features(40)

    first = build_evaluation_dataset(features)
    second = build_evaluation_dataset(features)

    assert first.training_rows == second.training_rows
    assert first.holdout_rows == second.holdout_rows
    assert first.cases == second.cases
    assert first.fingerprint == second.fingerprint


def test_input_order_does_not_change_split():
    features = make_features(40)

    reversed_features = replace(
        features,
        rows=tuple(reversed(features.rows)),
    )

    first = build_evaluation_dataset(features)
    second = build_evaluation_dataset(reversed_features)

    assert first.training_rows == second.training_rows
    assert first.cases == second.cases


def test_fingerprint_changes_with_data():
    original = make_features()

    modified_rows = list(original.rows)

    modified_rows[0] = replace(
        modified_rows[0],
        price_cash=modified_rows[0].price_cash + 100,
    )

    modified = replace(
        original,
        rows=tuple(modified_rows),
    )

    assert fingerprint_dataset(original) != (
        fingerprint_dataset(modified)
    )


def test_duplicate_vehicle_ids_are_rejected():
    features = make_features()

    duplicated = replace(
        features,
        rows=features.rows + (features.rows[0],),
    )

    with pytest.raises(ValueError):
        build_evaluation_dataset(duplicated)


def test_invalid_holdout_fraction_is_rejected():
    features = make_features()

    with pytest.raises(ValueError):
        build_evaluation_dataset(
            features,
            holdout_fraction=0,
        )


def test_small_dataset_is_rejected():
    with pytest.raises(ValueError):
        make_evaluation(10)


def test_matrix_dimensions():
    evaluation = make_evaluation()

    assert len(evaluation.training_matrix) == 16
    assert len(evaluation.evaluation_matrix) == 8

    assert all(
        len(row) == 3
        for row in evaluation.training_matrix
    )

    assert all(
        len(row) == 3
        for row in evaluation.evaluation_matrix
    )
