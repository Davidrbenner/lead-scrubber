"""Normalization and validation for phone numbers, emails, states, and dates."""

from __future__ import annotations

import re
from datetime import date, datetime

_NON_DIGIT = re.compile(r"\D")
# Extensions like "x123", "ext. 45", "#7" are dropped before parsing the number.
_EXTENSION = re.compile(r"(?:\s*(?:x|ext\.?|extension|#)\s*\d{1,6})\s*$", re.IGNORECASE)
_EMAIL = re.compile(r"^[a-z0-9._%+'-]+@(?:[a-z0-9-]+\.)+[a-z]{2,}$")

# fmt: off
_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR", "guam": "GU", "us virgin islands": "VI", "american samoa": "AS",
    "northern mariana islands": "MP",
}
# fmt: on
US_STATES = frozenset(_STATE_NAMES.values())

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%m-%d-%Y")


def phone_digits(raw: str | None) -> str | None:
    """Return the 10-digit US number in ``raw``, or None if it can't be one.

    Accepts any punctuation, a leading +1/1 country code, and a trailing extension.
    Does not check whether the number is dialable; see :func:`is_valid_nanp`.
    """
    if not raw:
        return None
    digits = _NON_DIGIT.sub("", _EXTENSION.sub("", raw.strip()))
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def is_fictional(digits: str) -> bool:
    """555-0100 through 555-0199 are reserved for fiction in every area code."""
    return digits[3:6] == "555" and digits[6:8] == "01"


def is_valid_nanp(digits: str, allow_fictional: bool = False) -> bool:
    """Structural NANP check on a 10-digit string.

    Area code and exchange must start with 2-9 and must not be N11 service codes
    (411, 911, ...). Repeated-digit junk like 2222222222 is rejected.
    """
    if len(digits) != 10 or not digits.isdigit():
        return False
    area, exchange = digits[:3], digits[3:6]
    if area[0] in "01" or exchange[0] in "01":
        return False
    if area[1:] == "11" or exchange[1:] == "11":
        return False
    if len(set(digits)) == 1:
        return False
    return allow_fictional or not is_fictional(digits)


def format_e164(digits: str) -> str:
    return f"+1{digits}"


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    email = raw.strip().strip("<>").lower()
    return email or None


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL.match(email)) and ".." not in email


def normalize_state(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    upper = value.upper()
    if upper in US_STATES:
        return upper
    return _STATE_NAMES.get(value.lower())


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    value = raw.strip()
    # Tolerate timestamps like "2026-03-04T10:15:00" or "2026-03-04 10:15".
    candidates = (value, value.split("T")[0], value.split(" ")[0])
    for candidate in candidates:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None
