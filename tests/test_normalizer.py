import pytest

from backend.scraper.normalizer import normalize_number


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("$ 218,880", 218880),
        ("51,818 KM", 51818),
        ("$32,995", 32995),
        ("4", 4),
        ("0", 0),
        ("", None),
        (None, None),
        ("N/A", None),
        ("Unknown", None),
    ],
)
def test_normalize_number(raw_value, expected):
    assert normalize_number(raw_value) == expected
