from dataclasses import replace
from datetime import date

import pytest

from leadscrub import Scrubber, read_table

HEADER = ["id", "Phone", "Email", "State"]


def run(cfg, make_csv, rows):
    return Scrubber(cfg).run(read_table(make_csv("leads.csv", [HEADER, *rows])))


def removed_by(result):
    return {r.lead.row["id"]: r.pass_name for r in result.removed}


def test_validation_and_dedupe(cfg, make_csv):
    result = run(
        cfg,
        make_csv,
        [
            ["1", "(909) 555-2368", "a@example.com", "CA"],
            ["2", "", "b@example.com", "CA"],
            ["3", "911", "", "CA"],
            ["4", "411-555-2368", "", "CA"],
            ["5", "+1 909 555 2368", "", "CA"],
        ],
    )
    assert [ld.row["id"] for ld in result.kept] == ["1"]
    assert removed_by(result) == {
        "2": "missing_contact",
        "3": "invalid_contact",
        "4": "invalid_contact",
        "5": "duplicate",
    }
    dup = next(r for r in result.removed if r.pass_name == "duplicate")
    assert dup.detail == "duplicate of row 1"


def test_each_pass_is_counted_in_order(cfg, make_csv):
    result = run(cfg, make_csv, [["1", "9095552368", "", "CA"], ["2", "", "", "CA"]])
    assert [p.name for p in result.passes] == [
        "missing_contact",
        "invalid_contact",
        "duplicate",
        "dnc",
        "opt_out",
        "existing_customer",
        "recently_contacted",
        "excluded_state",
    ]
    assert result.passes[0].removed == 1
    assert not result.passes[3].enabled  # no DNC file given


def test_suppression_passes(cfg, make_csv, tmp_path):
    dnc = tmp_path / "dnc.txt"
    dnc.write_text("909,5552001\n")
    opt = make_csv("opt.csv", [["email"], ["OPT@example.com"]])
    cust = make_csv("cust.csv", [["Name", "Phone"], ["X", "909-555-2003"]])
    log = make_csv("log.csv", [["phone", "date"], ["9095552004", "2026-09-25"], ["9095552005", "2026-06-01"]])
    cfg = replace(
        cfg, dnc=[dnc], opt_out=[opt], customers=[cust], contact_log=[log], recent_days=30, exclude_states={"TX"}
    )
    result = run(
        cfg,
        make_csv,
        [
            ["dnc", "9095552001", "", "CA"],
            ["opt", "9095552002", "opt@example.com", "CA"],
            ["cust", "9095552003", "", "CA"],
            ["recent", "9095552004", "", "CA"],
            ["old", "9095552005", "", "CA"],  # contacted long ago: kept
            ["tx", "9095552006", "", "Texas"],
        ],
    )
    assert [ld.row["id"] for ld in result.kept] == ["old"]
    assert removed_by(result) == {
        "dnc": "dnc",
        "opt": "opt_out",
        "cust": "existing_customer",
        "recent": "recently_contacted",
        "tx": "excluded_state",
    }


def test_email_mode(cfg, make_csv):
    cfg = replace(cfg, mode="email")
    result = run(
        cfg,
        make_csv,
        [
            ["1", "", "A@Example.com", "CA"],
            ["2", "", "a@example.com", "CA"],
            ["3", "", "not-an-email", "CA"],
            ["4", "", "", "CA"],
        ],
    )
    assert [ld.row["id"] for ld in result.kept] == ["1"]
    assert removed_by(result) == {"2": "duplicate", "3": "invalid_contact", "4": "missing_contact"}


def test_output_rows_add_normalized_columns(cfg, make_csv):
    scrubber = Scrubber(cfg)
    result = scrubber.run(read_table(make_csv("l.csv", [HEADER, ["1", "909.555.2368", " A@B.co ", "ca"]])))
    headers, rows = scrubber.output_rows(result)
    assert headers == [*HEADER, "phone_e164", "email_normalized"]
    assert rows[0]["phone_e164"] == "+19095552368"
    assert rows[0]["email_normalized"] == "a@b.co"
    assert rows[0]["Phone"] == "909.555.2368"  # original preserved


def test_explicit_column_names(cfg, make_csv):
    cfg = replace(cfg, phone_column="Work #")
    result = Scrubber(cfg).run(read_table(make_csv("l.csv", [["Work #"], ["9095552368"]])))
    assert len(result.kept) == 1


def test_missing_phone_column_is_an_error(cfg, make_csv):
    with pytest.raises(ValueError, match="no phone column"):
        Scrubber(cfg).run(read_table(make_csv("l.csv", [["name"], ["x"]])))


def test_unknown_column_name_is_an_error(cfg, make_csv):
    with pytest.raises(ValueError, match="not in file"):
        Scrubber(replace(cfg, phone_column="Nope")).run(read_table(make_csv("l.csv", [["Phone"], ["9095552368"]])))


def test_missing_suppression_file_is_an_error(cfg, tmp_path):
    with pytest.raises(FileNotFoundError):
        Scrubber(replace(cfg, dnc=[tmp_path / "missing.txt"]))


def test_recent_days_boundary(cfg, make_csv):
    log = make_csv("log.csv", [["phone", "date"], ["9095552001", "2026-09-01"], ["9095552002", "2026-08-31"]])
    cfg = replace(cfg, contact_log=[log], recent_days=30, today=date(2026, 10, 1))
    result = run(cfg, make_csv, [["edge", "9095552001", "", ""], ["out", "9095552002", "", ""]])
    assert [ld.row["id"] for ld in result.kept] == ["out"]
