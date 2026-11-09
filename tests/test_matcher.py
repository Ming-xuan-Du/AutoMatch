from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.matching.matcher import (
    MatchPolicy,
    find_candidates,
)
from backend.matching.schemas import MatchRequest


def vehicle(id, **changes):
    data = dict(
        id=id,
        source_listing_id=f"listing-{id}",
        is_active=True,
        missing_streak=0,
        title="2020 Toyota RAV4 LE AWD",
        year=2020,
        price_cash=Decimal("26000"),
        mileage_km=110000,
        body_style="SUV",
        drivetrain="AWD",
        listing_url=f"https://example.org/vehicles/{id}",
        image_url=None,
    )
    data.update(changes)
    return SimpleNamespace(**data)


def statuses(candidate):
    return {
        check.field: check.status
        for check in candidate.checks
    }


def test_exact_and_partial_with_explicit_differences():
    query = MatchRequest(
        max_budget=25000,
        make="Toyota",
        model="RAV4",
        min_year=2021,
        body_style="SUV",
    )

    matches = find_candidates([vehicle(1)], query)

    assert len(matches) == 1

    assert statuses(matches[0]) == {
        "budget": "not_met",
        "make": "met",
        "model": "met",
        "min_year": "not_met",
        "body_style": "met",
    }

    budget = next(
        c for c in matches[0].checks
        if c.field == "budget"
    )

    assert budget.difference == Decimal("1000")


def test_missing_price_remains_unknown():
    matches = find_candidates(
        [vehicle(1, price_cash=None)],
        MatchRequest(
            max_budget=25000,
            make="Toyota",
            body_style="SUV",
        ),
    )

    assert len(matches) == 1
    assert statuses(matches[0])["budget"] == "unknown"
    assert matches[0].price_cash is None


def test_budget_beyond_tolerance_excludes():
    matches = find_candidates(
        [vehicle(1, price_cash=Decimal("28000"))],
        MatchRequest(
            max_budget=25000,
            make="Toyota",
            model="RAV4",
        ),
    )

    assert matches == []


def test_unconfirmed_inventory_never_appears():
    cars = [
        vehicle(1, is_active=False),
        vehicle(2, missing_streak=1),
        vehicle(3),
    ]

    matches = find_candidates(
        cars,
        MatchRequest(make="Toyota"),
    )

    assert [c.vehicle_id for c in matches] == [3]


def test_no_score_ordering_and_cap_five():
    cars = [vehicle(i) for i in range(1, 9)]

    matches = find_candidates(
        cars,
        MatchRequest(make="Toyota"),
    )

    assert [c.vehicle_id for c in matches] == [
        1, 2, 3, 4, 5
    ]


def test_duplicate_listing_not_returned_twice():
    cars = [
        vehicle(1),
        vehicle(2, source_listing_id="listing-1"),
    ]

    matches = find_candidates(
        cars,
        MatchRequest(make="Toyota"),
    )

    assert [c.vehicle_id for c in matches] == [1]


def test_title_boundaries_and_missing_fields():
    # RAV40 must not be mistaken for RAV4.
    matches = find_candidates(
        [vehicle(1, title="2020 Toyota RAV40")],
        MatchRequest(model="RAV4"),
    )

    assert matches == []

    # Missing title means make cannot be verified.
    car = vehicle(1, title=None)

    request = MatchRequest(
        make="Toyota",
        body_style="SUV",
    )

    # New default rule:
    # Vehicle is excluded because no requested
    # make/model condition is confirmed.
    matches = find_candidates([car], request)

    assert matches == []

    # When identity-overlap requirement is
    # explicitly disabled, unknown is still
    # reported correctly rather than marked met.
    matches = find_candidates(
        [car],
        request,
        MatchPolicy(require_identity_overlap=False),
    )

    assert len(matches) == 1

    assert statuses(matches[0])["make"] == "unknown"
    assert statuses(matches[0])["body_style"] == "met"


def test_custom_policy_and_request_validation():
    matches = find_candidates(
        [vehicle(1, price_cash=26000)],
        MatchRequest(
            max_budget=25000,
            make="Toyota",
        ),
        MatchPolicy(
            max_budget_over_fraction=Decimal("0.01")
        ),
    )

    assert matches == []

    with pytest.raises(ValidationError):
        MatchRequest()


def test_no_mileage_invention_or_awd_4wd_conflation():
    matches = find_candidates(
        [
            vehicle(
                1,
                mileage_km=None,
                drivetrain="4WD",
            )
        ],
        MatchRequest(
            make="Toyota",
            max_mileage_km=90000,
            drivetrain="AWD",
        ),
    )

    # Only 1/3 conditions met; 2 required.
    assert matches == []

def test_unrelated_make_model_excluded():
    car = vehicle(
        10,
        title="2025 Land Rover Defender 110 AWD",
        year=2025,
        price_cash=None,
        mileage_km=16888,
        body_style="SUV",
        drivetrain="AWD",
    )

    request = MatchRequest(
        max_budget=25000,
        make="Toyota",
        model="RAV4",
        min_year=2020,
        max_mileage_km=120000,
        body_style="SUV",
        drivetrain="AWD",
    )

    matches = find_candidates([car], request)

    assert matches == []


def test_same_make_different_model_can_qualify():
    car = vehicle(
        11,
        title="2023 Toyota Corolla AWD",
        year=2023,
        price_cash=24000,
        mileage_km=80000,
        body_style="SUV",
        drivetrain="AWD",
    )

    request = MatchRequest(
        max_budget=25000,
        make="Toyota",
        model="RAV4",
        min_year=2020,
        max_mileage_km=120000,
        body_style="SUV",
        drivetrain="AWD",
    )

    matches = find_candidates([car], request)

    assert len(matches) == 1
    assert statuses(matches[0])["make"] == "met"
    assert statuses(matches[0])["model"] == "not_met"

@pytest.mark.parametrize(
    "field",
    [
        "make",
        "model",
        "body_style",
        "drivetrain",
    ],
)
def test_blank_text_rejected_with_valid_budget(field):
    with pytest.raises(ValidationError):
        MatchRequest(
            max_budget=30000,
            **{field: "   "},
        )


def test_text_requirements_are_trimmed():
    request = MatchRequest(
        make="  Toyota  ",
        model="  RAV4  ",
        body_style="  SUV  ",
        drivetrain="  AWD  ",
    )

    assert request.make == "Toyota"
    assert request.model == "RAV4"
    assert request.body_style == "SUV"
    assert request.drivetrain == "AWD"

    matches = find_candidates(
        [vehicle(1)],
        request,
    )

    assert len(matches) == 1
    assert statuses(matches[0])["make"] == "met"