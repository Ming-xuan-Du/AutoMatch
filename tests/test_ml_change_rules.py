
from types import SimpleNamespace

import pytest

from ml.change_rules import check_inventory_change


def make_change(**overrides):
    data = {
        "id": 100,
        "snapshot_id": 6,
        "source_listing_id": "test-vehicle",
        "change_type": "updated",
        "changes": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def rule_ids(change):
    return {
        finding.rule_id
        for finding in check_inventory_change(change)
    }


def test_normal_price_reduction_not_flagged():
    change = make_change(
        changes={
            "price_cash": {
                "old": 18080,
                "new": 17180,
            }
        }
    )

    assert rule_ids(change) == set()


def test_newly_populated_price_not_flagged():
    change = make_change(
        changes={
            "price_cash": {
                "old": None,
                "new": 27380,
            }
        }
    )

    assert rule_ids(change) == set()


def test_large_price_drop_flagged():
    change = make_change(
        changes={
            "price_cash": {
                "old": 20000,
                "new": 9000,
            }
        }
    )

    assert "large_cash_price_change" in rule_ids(change)


def test_large_price_increase_flagged():
    change = make_change(
        changes={
            "price_cash": {
                "old": 20000,
                "new": 31000,
            }
        }
    )

    assert "large_cash_price_change" in rule_ids(change)


def test_price_change_at_threshold_flagged():
    change = make_change(
        changes={
            "price_cash": {
                "old": 20000,
                "new": 10000,
            }
        }
    )

    assert "large_cash_price_change" in rule_ids(change)


def test_normal_mileage_increase_not_flagged():
    change = make_change(
        changes={
            "mileage_km": {
                "old": 45818,
                "new": 49978,
            }
        }
    )

    assert rule_ids(change) == set()


def test_mileage_decrease_flagged():
    change = make_change(
        changes={
            "mileage_km": {
                "old": 80000,
                "new": 79000,
            }
        }
    )

    assert "mileage_decrease" in rule_ids(change)


def test_added_record_not_flagged():
    change = make_change(
        change_type="added",
        changes={
            "new": {
                "price_cash": 20000,
            }
        },
    )

    assert rule_ids(change) == set()


def test_suspected_missing_not_flagged():
    change = make_change(
        change_type="suspected_missing",
        changes={
            "missing_streak": {
                "old": 0,
                "new": 1,
            }
        },
    )

    assert rule_ids(change) == set()


def test_malformed_transition_does_not_crash():
    change = make_change(
        changes={
            "price_cash": {
                "old": "20000",
                "new": 10000,
            }
        }
    )

    assert rule_ids(change) == set()


def test_missing_transition_value_does_not_crash():
    change = make_change(
        changes={
            "mileage_km": {
                "old": 80000,
            }
        }
    )

    assert rule_ids(change) == set()


def test_multiple_anomalies_in_single_update():
    change = make_change(
        changes={
            "price_cash": {
                "old": 30000,
                "new": 10000,
            },
            "mileage_km": {
                "old": 90000,
                "new": 70000,
            },
        }
    )

    assert rule_ids(change) == {
        "large_cash_price_change",
        "mileage_decrease",
    }


def test_invalid_threshold_rejected():
    change = make_change()

    with pytest.raises(ValueError):
        check_inventory_change(
            change,
            large_cash_change_ratio=0,
        )

def test_reappeared_large_price_drop_flagged():
    change = make_change(
        change_type="reappeared",
        changes={
            "price_cash": {
                "old": 20000,
                "new": 9000,
            },
            "missing_streak": {
                "old": 2,
                "new": 0,
            },
            "is_active": {
                "old": False,
                "new": True,
            },
        },
    )

    assert rule_ids(change) == {
        "large_cash_price_change",
    }

def test_reappeared_mileage_decrease_flagged():
    change = make_change(
        change_type="reappeared",
        changes={
            "mileage_km": {
                "old": 80000,
                "new": 65000,
            },
            "missing_streak": {
                "old": 1,
                "new": 0,
            },
        },
    )

    assert rule_ids(change) == {
        "mileage_decrease",
    }

def test_reappeared_without_anomaly_not_flagged():
    change = make_change(
        change_type="reappeared",
        changes={
            "price_cash": {
                "old": 20000,
                "new": 19500,
            },
            "mileage_km": {
                "old": 80000,
                "new": 82000,
            },
            "missing_streak": {
                "old": 2,
                "new": 0,
            },
            "is_active": {
                "old": False,
                "new": True,
            },
        },
    )

    assert rule_ids(change) == set()