
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


ExtractionStatus = Literal[
    "explicit",
    "missing",
    "ambiguous",
    "preference",
]

REQUIREMENT_FIELDS = (
    "max_budget",
    "make",
    "model",
    "min_year",
    "max_mileage_km",
    "body_style",
    "drivetrain",
)


class ExtractRequest(BaseModel):
    customer_text: str = Field(
        min_length=5,
        max_length=1200,
    )

    @field_validator("customer_text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 5:
            raise ValueError(
                "Enter a meaningful customer description."
            )

        return value


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


class NumericFieldExtraction(StrictModel):
    value: int | None
    status: ExtractionStatus
    evidence: str | None
    note: str | None


class TextFieldExtraction(StrictModel):
    value: str | None
    status: ExtractionStatus
    evidence: str | None
    note: str | None


class LLMExtraction(StrictModel):
    """
    Internal structured response from the LLM.

    Every field is required in the JSON schema.
    Each value may be null when not explicit.
    """

    max_budget: NumericFieldExtraction
    make: TextFieldExtraction
    model: TextFieldExtraction
    min_year: NumericFieldExtraction
    max_mileage_km: NumericFieldExtraction
    body_style: TextFieldExtraction
    drivetrain: TextFieldExtraction


class ExtractedRequirements(BaseModel):
    """
    Fields compatible with the existing MatchRequest.

    Only explicit, validated requirements are included.
    """

    max_budget: int | None = None
    make: str | None = None
    model: str | None = None
    min_year: int | None = None
    max_mileage_km: int | None = None
    body_style: str | None = None
    drivetrain: str | None = None


class ExtractResponse(BaseModel):
    requirements: ExtractedRequirements

    field_states: dict[str, ExtractionStatus]

    evidence: dict[str, str | None]

    review_notes: list[str]
