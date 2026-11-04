
import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.ai import extractor
from backend.ai.schemas import (
    LLMExtraction,
    REQUIREMENT_FIELDS,
)


def make_draft(**overrides):
    data = {
        field: {
            "value": None,
            "status": "missing",
            "evidence": None,
            "note": None,
        }
        for field in REQUIREMENT_FIELDS
    }

    data.update(overrides)

    return LLMExtraction.model_validate(data)


def test_explicit_requirements_are_extracted():
    text = (
        "I need a Toyota SUV under 25 grand, "
        "2020 or newer."
    )

    draft = make_draft(
        max_budget={
            "value": 25000,
            "status": "explicit",
            "evidence": "under 25 grand",
            "note": None,
        },
        make={
            "value": "Toyota",
            "status": "explicit",
            "evidence": "Toyota",
            "note": None,
        },
        min_year={
            "value": 2020,
            "status": "explicit",
            "evidence": "2020 or newer",
            "note": None,
        },
        body_style={
            "value": "SUV",
            "status": "explicit",
            "evidence": "SUV",
            "note": None,
        },
    )

    result = extractor.build_extraction_response(
        draft,
        text,
    )

    assert result.requirements.max_budget == 25000
    assert result.requirements.make == "Toyota"
    assert result.requirements.min_year == 2020
    assert result.requirements.body_style == "SUV"

    assert result.requirements.model is None
    assert result.requirements.drivetrain is None

    assert result.field_states["make"] == "explicit"
    assert result.field_states["model"] == "missing"


def test_preference_is_not_mandatory():
    text = (
        "I prefer Toyota but I'm open "
        "to other brands."
    )

    draft = make_draft(
        make={
            "value": "Toyota",
            "status": "preference",
            "evidence": "prefer Toyota",
            "note": "Toyota is preferred, not required.",
        },
    )

    result = extractor.build_extraction_response(
        draft,
        text,
    )

    assert result.requirements.make is None
    assert result.field_states["make"] == "preference"
    assert result.review_notes


def test_winter_does_not_imply_awd():
    text = "I want something good for winter."

    draft = make_draft(
        drivetrain={
            "value": "AWD",
            "status": "explicit",
            "evidence": "good for winter",
            "note": None,
        },
    )

    result = extractor.build_extraction_response(
        draft,
        text,
    )

    assert result.requirements.drivetrain is None
    assert result.field_states["drivetrain"] == "ambiguous"


def test_actual_awd_requirement_is_accepted():
    text = "I need an SUV with AWD."

    draft = make_draft(
        drivetrain={
            "value": "AWD",
            "status": "explicit",
            "evidence": "AWD",
            "note": None,
        },
    )

    result = extractor.build_extraction_response(
        draft,
        text,
    )

    assert result.requirements.drivetrain == "AWD"


def test_unsupported_evidence_is_not_accepted():
    draft = make_draft(
        make={
            "value": "Toyota",
            "status": "explicit",
            "evidence": "Toyota",
            "note": None,
        },
    )

    result = extractor.build_extraction_response(
        draft,
        "I need a reliable sedan.",
    )

    assert result.requirements.make is None
    assert result.field_states["make"] == "ambiguous"


def test_invalid_year_is_not_activated():
    draft = make_draft(
        min_year={
            "value": 1800,
            "status": "explicit",
            "evidence": "1800",
            "note": None,
        },
    )

    result = extractor.build_extraction_response(
        draft,
        "I need a car from 1800.",
    )

    assert result.requirements.min_year is None
    assert result.field_states["min_year"] == "ambiguous"


def test_all_missing_requires_manual_input():
    result = extractor.build_extraction_response(
        make_draft(),
        "I need a reliable car.",
    )

    values = result.requirements.model_dump()

    assert all(value is None for value in values.values())
    assert any(
        "at least one requirement" in note
        for note in result.review_notes
    )


def test_invalid_structured_value_is_rejected():
    data = {
        field: {
            "value": None,
            "status": "missing",
            "evidence": None,
            "note": None,
        }
        for field in REQUIREMENT_FIELDS
    }

    data["max_budget"] = {
        "value": "twenty five thousand",
        "status": "explicit",
        "evidence": "twenty five thousand",
        "note": None,
    }

    with pytest.raises(ValidationError):
        LLMExtraction.model_validate(data)


@pytest.mark.parametrize(
    "text",
    [
        "Call me at 416-555-0123 about an SUV.",
        "Email customer@example.com for details.",
        "My name is Jane and I need an SUV.",
        "Deliver to 123 Main Street.",
    ],
)
def test_personal_information_is_blocked(text):
    with pytest.raises(
        extractor.PersonalInformationDetected
    ):
        extractor.check_personal_information(text)


def test_missing_key_is_handled(monkeypatch):
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    with pytest.raises(
        extractor.ExtractionUnavailable
    ):
        asyncio.run(
            extractor.extract_requirements(
                "I need a Toyota SUV."
            )
        )


def test_mocked_openai_structured_response(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "fake-test-key",
    )

    draft = make_draft(
        make={
            "value": "Toyota",
            "status": "explicit",
            "evidence": "Toyota",
            "note": None,
        },
    )

    async def fake_parse(**kwargs):
        assert kwargs["text_format"] is LLMExtraction
        assert kwargs["store"] is False

        return SimpleNamespace(
            status="completed",
            output_parsed=draft,
        )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(
                parse=fake_parse
            )

        async def close(self):
            pass

    monkeypatch.setattr(
        extractor,
        "AsyncOpenAI",
        FakeOpenAI,
    )

    result = asyncio.run(
        extractor.extract_requirements(
            "I need a Toyota SUV."
        )
    )

    assert result.requirements.make == "Toyota"


def test_incomplete_model_response(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "fake-test-key",
    )

    async def fake_parse(**kwargs):
        return SimpleNamespace(
            status="incomplete",
            output_parsed=None,
        )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(
                parse=fake_parse
            )

        async def close(self):
            pass

    monkeypatch.setattr(
        extractor,
        "AsyncOpenAI",
        FakeOpenAI,
    )

    with pytest.raises(
        extractor.ExtractionInvalidResponse
    ):
        asyncio.run(
            extractor.extract_requirements(
                "I need a Toyota SUV."
            )
        )
