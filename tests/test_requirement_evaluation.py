
from evaluation.requirement_cases import (
    CASES,
    FIELDS,
    case,
)
from evaluation.run_extraction_eval import (
    normalize,
    summarize,
)


def test_dataset_has_fifty_unique_cases():
    assert len(CASES) == 50
    assert len({row["id"] for row in CASES}) == 50

    for row in CASES:
        assert set(row["requirements"]) == set(FIELDS)
        assert set(row["field_states"]) == set(FIELDS)

        for field in FIELDS:
            status = row["field_states"][field]
            value = row["requirements"][field]

            assert status in {
                "explicit",
                "missing",
                "ambiguous",
                "preference",
            }

            assert (value is not None) == (
                status == "explicit"
            )


def test_normalization_does_not_merge_awd_and_4wd():
    assert normalize(
        "drivetrain",
        "All-wheel drive",
    ) == "awd"

    assert normalize(
        "drivetrain",
        "4WD",
    ) != normalize(
        "drivetrain",
        "AWD",
    )

    assert normalize(
        "body_style",
        "Pickup truck",
    ) == "truck"


def test_perfect_predictions_are_scored_as_perfect():
    predictions = [
        {
            "requirements": row["requirements"],
            "field_states": row["field_states"],
            "error": None,
        }
        for row in CASES
    ]

    metrics = summarize(CASES, predictions)

    assert metrics["field_decision_accuracy"] == 1.0
    assert metrics["hallucination_rate"] == 0.0
    assert metrics["omission_rate"] == 0.0
    assert metrics["total_field_decisions"] == 350


def test_missing_predictions_count_as_omissions():
    row = CASES[0]

    prediction = {
        "requirements": {
            field: None
            for field in FIELDS
        },
        "field_states": {
            field: "missing"
            for field in FIELDS
        },
        "error": None,
    }

    metrics = summarize(
        [row],
        [prediction],
    )

    assert metrics["omission_rate"] == 1.0
    assert metrics["correct_explicit_values"] == 0


def test_preference_as_hard_filter_is_hallucination():
    row = case(
        99,
        "I prefer Toyota, but any make is okay.",
        preference=("make",),
    )

    prediction = {
        "requirements": {
            **row["requirements"],
            "make": "Toyota",
        },
        "field_states": {
            **row["field_states"],
            "make": "explicit",
        },
        "error": None,
    }

    metrics = summarize(
        [row],
        [prediction],
    )

    assert metrics["hallucinated_constraints"] == 1
    assert metrics["hallucination_rate"] == round(
        1 / 7,
        4,
    )
