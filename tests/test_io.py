from datetime import date

import pytest

from leadscrub.io import find_column, load_contact_log, load_email_set, load_phone_set, read_table


def test_find_column_is_forgiving():
    assert find_column(["Lead ID", "Mobile-Phone", "E_Mail"], ["mobile phone"]) == "Mobile-Phone"
    assert find_column(["a", "b"], ["phone"]) is None


def test_read_table_handles_semicolons_and_bom(tmp_path):
    p = tmp_path / "leads.csv"
    p.write_bytes("﻿Name;Phone\nAna;909-555-2368\n".encode())
    t = read_table(p)
    assert t.headers == ["Name", "Phone"]
    assert t.rows == [{"Name": "Ana", "Phone": "909-555-2368"}]


def test_read_table_falls_back_to_cp1252(tmp_path):
    p = tmp_path / "excel.csv"
    p.write_bytes("Name,Phone\nJos\xe9,9095552368\n".encode("cp1252"))
    assert read_table(p).rows[0]["Name"] == "José"


def test_read_table_requires_header(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(ValueError, match="no header"):
        read_table(p)


def test_load_phone_set_formats(tmp_path, make_csv):
    ftc = tmp_path / "dnc.txt"
    ftc.write_text("909,5552368\n310,5559876\n")
    plain = tmp_path / "plain.txt"
    plain.write_text("(415) 555-1111\n\nnot a number\n")
    with_header = make_csv("c.csv", [["Name", "Cell Phone"], ["A", "+1 626 555 2222"]])
    assert load_phone_set([ftc, plain, with_header]) == {"9095552368", "3105559876", "4155551111", "6265552222"}


def test_load_email_set(tmp_path, make_csv):
    a = make_csv("a.csv", [["Email"], ["A@Example.com"], [""]])
    b = tmp_path / "b.txt"
    b.write_text("b@example.com\nnot-an-email\n")
    assert load_email_set([a, b]) == {"a@example.com", "b@example.com"}


def test_contact_log_keeps_latest_date(make_csv):
    log = make_csv(
        "log.csv",
        [["phone", "called_at"], ["9095552368", "01/02/2026"], ["909-555-2368", "2026-03-01"], ["bad", "2026-01-01"]],
    )
    assert load_contact_log([log]) == {"9095552368": date(2026, 3, 1)}


def test_contact_log_requires_columns(make_csv):
    log = make_csv("log.csv", [["who", "when"], ["x", "y"]])
    with pytest.raises(ValueError, match="phone column and a date column"):
        load_contact_log([log])
