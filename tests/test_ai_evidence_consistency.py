import pytest

from backend.ai.extractor import build_extraction_response
from backend.ai.schemas import LLMExtraction, REQUIREMENT_FIELDS


def make_draft(field, value, evidence):
    data = {
        name: {
            "value": None,
            "status": "missing",
            "evidence": None,
            "note": None,
        }
        for name in REQUIREMENT_FIELDS
    }

    data[field] = {
        "value": value,
        "status": "explicit",
        "evidence": evidence,
        "note": None,
    }

    return LLMExtraction.model_validate(data)


@pytest.mark.parametrize(
    "text, field, value, evidence",
    [
        ("I need a Toyota SUV.", "make", "Honda", "Toyota"),
        ("I need a Toyota Corolla.", "model", "Civic", "Corolla"),
        ("I need an SUV.", "body_style", "Sedan", "SUV"),
        ("I need AWD.", "drivetrain", "FWD", "AWD"),
    ],
)
def test_contradictory_evidence_is_not_activated(
    text, field, value, evidence,
):
    result = build_extraction_response(
        make_draft(field, value, evidence),
        text,
    )

    assert getattr(result.requirements, field) is None
    assert result.field_states[field] == "ambiguous"
    assert result.review_notes


@pytest.mark.parametrize(
    "text, field, value, evidence",
    [
        ("I need a Toyota.", "make", "Toyota", "Toyota"),
        ("I need a Corolla.", "model", "Corolla", "Corolla"),
        ("I need an SUV.", "body_style", "SUV", "SUV"),
        (
            "I need all-wheel drive.",
            "drivetrain",
            "AWD",
            "all-wheel drive",
        ),
        (
            "My cash budget is under 25 grand.",
            "max_budget",
            25000,
            "25 grand",
        ),
    ],
)
def test_supported_evidence_remains_explicit(
    text, field, value, evidence,
):
    result = build_extraction_response(
        make_draft(field, value, evidence),
        text,
    )

    assert getattr(result.requirements, field) == value
    assert result.field_states[field] == "explicit"