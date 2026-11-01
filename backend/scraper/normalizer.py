import re


def normalize_number(text):
    """Convert formatted numbers into integers."""
    if text is None:
        return None

    text = str(text).strip()

    if not text:
        return None

    match = re.search(r"\d[\d,]*", text)

    if not match:
        return None

    return int(match.group().replace(",", ""))
