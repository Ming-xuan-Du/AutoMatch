
import re


NUMBER_PATTERN = re.compile(
    r"\$?\s*"
    r"(?P<number>\d{1,3}(?:[ ,]\d{3})+|\d+)"
    r"\s*(?:km|kms|kilometres?|kilometers?|cad)?",
    flags=re.IGNORECASE,
)


def normalize_number(text):
    """Parse a complete, non-negative integer value.

    Supports comma/space thousands separators, optional
    dollar signs, and common mileage/currency suffixes.

    Unrecognized or ambiguous formats return None.
    """
    if text is None:
        return None

    cleaned = (
        str(text)
        .strip()
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
    )

    if not cleaned:
        return None

    match = NUMBER_PATTERN.fullmatch(cleaned)

    if match is None:
        return None

    digits = match.group("number")

    return int(
        digits.replace(",", "").replace(" ", "")
    )
