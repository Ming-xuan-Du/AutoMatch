
from types import SimpleNamespace

import pytest

from ml.evaluation_metrics import (
    count_detections,
    group_pairs,
    paired_change_rule_flags,
    paired_score_movement,
    scenario_summary,
    snapshot_rule_flags,
)


def make_pair(
    vehicle_id,
    *,
    old_price=20000,
    new_price=20000,
    old_mileage=80000,
    new_mileage=80000,
    scenario="synthetic",
):
    common = {
        "source_listing_id": vehicle_id,
        "title": "2019 Test Vehicle",
        "year": 2019,
    }

    original = SimpleNamespace(
        **common,
        label=0,
        scenario="original",
        price_cash=old_price,
        mileage_km=old_mileage,
    )

    altered = SimpleNamespace(
        **common,
        label=1,
        scenario=scenario,
        price_cash=new_price,
        mileage_km=new_mileage,
    )

    return [original, altered]


def test_confusion_counts():
    cases = [
        SimpleNamespace(label=value)
        for value in (0, 1, 0, 1)
    ]

    results = count_detections(
        cases,
        [False, True, True, False],
    )

    assert results.tp == 1
    assert results.fp == 1
    assert results.tn == 1
    assert results.fn == 1

    metrics = results.as_dict()

    assert metrics["synthetic_recall"] == 0.5
    assert metrics["assumed_normal_flag_rate"] == 0.5
    assert metrics["balanced_set_precision"] == 0.5


def test_no_flags_has_undefined_precision():
    cases = [
        SimpleNamespace(label=0),
        SimpleNamespace(label=1),
    ]

    metrics = count_detections(
        cases, [False, False]
    ).as_dict()

    assert metrics["synthetic_recall"] == 0
    assert metrics["balanced_set_precision"] is None


def test_mismatched_prediction_count_rejected():
    cases = [SimpleNamespace(label=1)]

    with pytest.raises(ValueError):
        count_detections(cases, [])


def test_invalid_labels_rejected():
    cases = [SimpleNamespace(label=3)]

    with pytest.raises(ValueError):
        count_detections(cases, [True])


def test_snapshot_rules_do_not_flag_valid_extremes():
    cases = make_pair(
        "vehicle-a",
        old_price=20000,
        new_price=80000,
    )

    assert snapshot_rule_flags(
        cases,
        reference_year=2026,
    ) == [False, False]


def test_change_rules_detect_expected_scenarios():
    cases = []

    cases += make_pair(
        "a",
        new_price=80000,
        scenario="cash_price_x4",
    )

    cases += make_pair(
        "b",
        new_price=4000,
        scenario="cash_price_div5",
    )

    cases += make_pair(
        "c",
        new_mileage=320000,
        scenario="mileage_x4",
    )

    cases += make_pair(
        "d",
        new_mileage=16000,
        scenario="mileage_div5",
    )

    flags = paired_change_rule_flags(cases)

    assert flags == [
        False, True,
        False, True,
        False, False,
        False, True,
    ]


def test_invalid_pair_rejected():
    cases = make_pair("a")[:1]

    with pytest.raises(ValueError):
        group_pairs(cases)


def test_scenario_detection_summary():
    cases = (
        make_pair("a", scenario="cash_price_x4")
        + make_pair("b", scenario="cash_price_x4")
    )

    result = scenario_summary(
        cases,
        [False, True, False, False],
    )

    assert result["cash_price_x4"]["total"] == 2
    assert result["cash_price_x4"]["detected"] == 1
    assert result["cash_price_x4"]["recall"] == 0.5


def test_paired_score_direction():
    cases = (
        make_pair("a")
        + make_pair("b")
    )

    scores = [0.20, 0.10, 0.01, 0.20]

    movement = paired_score_movement(
        cases, scores
    )

    assert movement["pairs"] == 2
    assert movement["altered_more_anomalous"] == 1
    assert movement["altered_less_anomalous"] == 1
    assert movement["ties"] == 0
