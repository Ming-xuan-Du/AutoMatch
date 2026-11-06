
from math import isclose, log1p
from types import SimpleNamespace

import pytest

from ml.features import (
    FEATURE_NAMES,
    build_feature_dataset,
)


def make_vehicle(**overrides):
    data = {
        "source_listing_id": "vehicle-001",
        "title": "2019 Toyota RAV4",
        "year": 2019,
        "price_cash": 20000,
        "mileage_km": 80000,
        "body_style": "SUV",
        "is_active": True,
        "missing_streak": 0,
    }

    data.update(overrides)
    return SimpleNamespace(**data)


def prepare(*vehicles):
    return build_feature_dataset(
        vehicles,
        reference_year=2026,
    )


def test_valid_vehicle_produces_features():
    dataset = prepare(make_vehicle())

    assert len(dataset.rows) == 1
    assert len(dataset.feature_matrix) == 1
    assert len(dataset.feature_matrix[0]) == 3

    row = dataset.rows[0]

    assert row.vehicle_age == 7
    assert row.body_style == "suv"

    assert isclose(
        row.log_cash_price,
        log1p(20000),
    )
    assert isclose(
        row.log_mileage_km,
        log1p(80000),
    )


def test_missing_cash_price_is_excluded():
    dataset = prepare(
        make_vehicle(price_cash=None)
    )

    assert len(dataset.rows) == 0
    assert dataset.excluded["missing_cash_price"] == 1


def test_nonpositive_cash_price_is_excluded():
    dataset = prepare(
        make_vehicle(price_cash=0)
    )

    assert dataset.excluded["invalid_cash_price"] == 1


def test_negative_mileage_is_excluded():
    dataset = prepare(
        make_vehicle(mileage_km=-50)
    )

    assert dataset.excluded["invalid_mileage"] == 1


def test_missing_year_is_excluded():
    dataset = prepare(
        make_vehicle(year=None)
    )

    assert dataset.excluded["missing_year"] == 1


def test_invalid_year_is_excluded():
    dataset = prepare(
        make_vehicle(year=2050)
    )

    assert dataset.excluded["invalid_year"] == 1


def test_next_model_year_is_supported():
    dataset = prepare(
        make_vehicle(year=2027)
    )

    assert len(dataset.rows) == 1
    assert dataset.rows[0].vehicle_age == 0


def test_unconfirmed_vehicle_is_excluded():
    dataset = prepare(
        make_vehicle(missing_streak=1)
    )

    assert dataset.excluded["not_confirmed_present"] == 1


def test_inactive_vehicle_is_excluded():
    dataset = prepare(
        make_vehicle(is_active=False)
    )

    assert dataset.excluded["inactive"] == 1


def test_feature_order_is_stable():
    first = make_vehicle(
        source_listing_id="vehicle-b"
    )
    second = make_vehicle(
        source_listing_id="vehicle-a"
    )

    dataset = prepare(first, second)

    assert [
        row.source_listing_id for row in dataset.rows
    ] == ["vehicle-a", "vehicle-b"]

    assert FEATURE_NAMES == (
        "vehicle_age",
        "log_cash_price",
        "log_mileage_km",
    )


def test_extreme_valid_vehicle_is_retained():
    dataset = prepare(
        make_vehicle(
            title="2012 Lamborghini Aventador",
            year=2012,
            price_cash=380380,
            mileage_km=14618,
        )
    )

    assert len(dataset.rows) == 1
    assert dataset.excluded == {}


def test_invalid_reference_year_rejected():
    with pytest.raises(ValueError):
        build_feature_dataset(
            [make_vehicle()],
            reference_year=1800,
        )
