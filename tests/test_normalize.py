from datetime import date

import pytest

from leadscrub.normalize import (
    format_e164,
    is_valid_email,
    is_valid_nanp,
    normalize_email,
    normalize_state,
    parse_date,
    phone_digits,
)


@pytest.mark.parametrize(
    "raw",
    [
        "(909) 555-2368",
        "909-555-2368",
        "909.555.2368",
        "9095552368",
        "+1 909 555 2368",
        "19095552368",
        "909-555-2368 x12",
        "909 555 2368 ext. 4",
        " 909 555 2368 ",
    ],
)
def test_phone_digits_accepts_common_formats(raw):
    assert phone_digits(raw) == "9095552368"


@pytest.mark.parametrize("raw", ["", None, "555-1234", "n/a", "29095552368", "123"])
def test_phone_digits_rejects_wrong_lengths(raw):
    assert phone_digits(raw) is None


@pytest.mark.parametrize(
    "digits,ok",
    [
        ("9095552368", True),
        ("0095552368", False),  # area code can't start with 0
        ("1095552368", False),  # or 1
        ("9091552368", False),  # exchange can't start with 1
        ("4115552368", False),  # N11 area code
        ("9094112368", False),  # N11 exchange
        ("2222222222", False),  # repeated digits
        ("9095550142", False),  # fictional 555-01XX
    ],
)
def test_is_valid_nanp(digits, ok):
    assert is_valid_nanp(digits) is ok


def test_fictional_numbers_allowed_on_request():
    assert is_valid_nanp("9095550142", allow_fictional=True)


def test_format_e164():
    assert format_e164("9095552368") == "+19095552368"


def test_email_normalize_and_validate():
    assert normalize_email("  <Jane.Doe@Example.COM> ") == "jane.doe@example.com"
    assert normalize_email("   ") is None
    assert is_valid_email("o'brien+leads@mail.example.co")
    for bad in ["jane", "jane@", "@example.com", "jane@example", "jane..doe@example.com", "jane doe@example.com"]:
        assert not is_valid_email(bad), bad


@pytest.mark.parametrize(
    "raw,expected", [("ca", "CA"), ("California", "CA"), (" new york ", "NY"), ("Narnia", None), ("", None)]
)
def test_normalize_state(raw, expected):
    assert normalize_state(raw) == expected


@pytest.mark.parametrize("raw", ["2026-03-04", "03/04/2026", "3/4/26", "2026-03-04T10:15:00", "2026-03-04 10:15"])
def test_parse_date_formats(raw):
    assert parse_date(raw) == date(2026, 3, 4)


def test_parse_date_garbage():
    assert parse_date("last tuesday") is None
