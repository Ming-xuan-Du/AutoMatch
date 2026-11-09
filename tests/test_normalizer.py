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
        ("$25 900", 25900),
        ("85 000 km", 85000),
        ("$25\u00a0900", 25900),
        ("85\u202f000 km", 85000),
        ("25,900 CAD", 25900),
        ("Contact for price", None),
        ("-$1,000", None),
        ("$-1,000", None),
        ("$25,900.50", None),
        ("25 90", None),
        ("25,900 or 27,000", None),
    ],
)
def test_normalize_number(raw_value, expected):
    assert normalize_number(raw_value) == expected
