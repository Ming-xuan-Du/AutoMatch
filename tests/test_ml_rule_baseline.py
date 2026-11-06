
from types import SimpleNamespace

from ml.rule_baseline import check_vehicle


def make_vehicle(**overrides):
    data = {
        "source_listing_id": "test-001",
        "title": "2019 Toyota RAV4",
        "listing_url": "https://example.com/car/1",
        "year": 2019,
        "price_cash": 20000,
        "price_finance": 18500,
        "mileage_km": 80000,
        "missing_streak": 0,
    }

    data.update(overrides)
    return SimpleNamespace(**data)


def rule_ids(vehicle, reference_year=2026):
    return {
        finding.rule_id
        for finding in check_vehicle(
            vehicle,
            reference_year=reference_year,
        )
    }


def test_valid_vehicle_has_no_findings():
    assert rule_ids(make_vehicle()) == set()


def test_negative_mileage_is_invalid():
    vehicle = make_vehicle(mileage_km=-100)

    assert "negative_mileage" in rule_ids(vehicle)


def test_nonpositive_cash_price_is_invalid():
    vehicle = make_vehicle(price_cash=0)

    assert "invalid_cash_price" in rule_ids(vehicle)


def test_nonpositive_finance_price_is_invalid():
    vehicle = make_vehicle(price_finance=-200)

    assert "invalid_finance_price" in rule_ids(vehicle)


def test_impossible_future_year_is_invalid():
    vehicle = make_vehicle(year=2050)

    assert "invalid_year" in rule_ids(vehicle)


def test_next_model_year_is_allowed():
    vehicle = make_vehicle(year=2027)

    assert rule_ids(vehicle) == set()


def test_missing_cash_price_is_not_automatic_anomaly():
    vehicle = make_vehicle(price_cash=None)

    assert rule_ids(vehicle) == set()


def test_legitimate_expensive_vehicle_is_not_flagged():
    vehicle = make_vehicle(
        year=2012,
        price_cash=380380,
        mileage_km=14618,
    )

    assert rule_ids(vehicle) == set()


def test_legitimate_high_mileage_is_not_flagged():
    vehicle = make_vehicle(
        year=2009,
        price_cash=5380,
        mileage_km=310233,
    )

    assert rule_ids(vehicle) == set()


def test_negative_missing_streak_is_invalid():
    vehicle = make_vehicle(missing_streak=-1)

    assert "negative_missing_streak" in rule_ids(vehicle)


def test_blank_identity_fields_are_invalid():
    vehicle = make_vehicle(
        source_listing_id="",
        title=" ",
        listing_url="",
    )

    assert rule_ids(vehicle) == {
        "empty_listing_id",
        "empty_title",
        "empty_listing_url",
    }
