"""CSV reading/writing, column detection, and suppression-list loading."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .normalize import normalize_email, parse_date, phone_digits

PHONE_ALIASES = (
    "phone",
    "phone_number",
    "phonenumber",
    "phone number",
    "primary phone",
    "primary_phone",
    "mobile",
    "mobile phone",
    "mobile_phone",
    "cell",
    "cell phone",
    "telephone",
    "tel",
    "contact phone",
    "home phone",
    "work phone",
)
EMAIL_ALIASES = ("email", "email address", "email_address", "e-mail", "emailaddress", "contact email")
STATE_ALIASES = ("state", "st", "state/province", "province", "region", "state_code")
DATE_ALIASES = ("date", "contacted", "contacted_at", "contact date", "last contacted", "called_at", "timestamp")


def _key(header: str) -> str:
    return header.strip().lower().replace("-", " ").replace("_", " ")


def find_column(headers: Iterable[str], aliases: Iterable[str]) -> str | None:
    """Return the first header matching an alias (case, space, _ and - insensitive)."""
    wanted = [_key(a) for a in aliases]
    by_key = {_key(h): h for h in headers}
    for alias in wanted:
        if alias in by_key:
            return by_key[alias]
    return None


def _open_text(path: Path) -> io.StringIO:
    """Read as BOM-aware UTF-8, falling back to Windows-1252 for Excel exports."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    return io.StringIO(text, newline="")


def _dialect(sample: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


@dataclass
class Table:
    headers: list[str]
    rows: list[dict[str, str]]


def read_table(path: str | Path) -> Table:
    path = Path(path)
    with _open_text(path) as fh:
        sample = fh.read(1 << 16)
        fh.seek(0)
        reader = csv.DictReader(fh, dialect=_dialect(sample))
        headers = [h for h in (reader.fieldnames or []) if h is not None]
        if not headers:
            raise ValueError(f"{path}: no header row found")
        rows = [{h: (row.get(h) or "").strip() for h in headers} for row in reader]
    return Table(headers, rows)


def write_table(path: str | Path, headers: list[str], rows: Iterable[dict[str, str]]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def _iter_lines(path: Path) -> Iterator[list[str]]:
    with _open_text(path) as fh:
        sample = fh.read(1 << 16)
        fh.seek(0)
        yield from csv.reader(fh, dialect=_dialect(sample))


def load_phone_set(paths: Iterable[str | Path]) -> set[str]:
    """Load 10-digit phones from CSVs (any phone-like column) or plain lists.

    Plain files may have one number per line, or the FTC DNC layout of
    ``areacode,number``; in both cases the row's digits are joined.
    """
    phones: set[str] = set()
    for p in paths:
        rows = list(_iter_lines(Path(p)))
        if not rows:
            continue
        col = None
        header = rows[0]
        idx = find_column(header, PHONE_ALIASES)
        if idx is not None:
            col = header.index(idx)
            rows = rows[1:]
        for row in rows:
            raw = row[col] if col is not None and col < len(row) else "".join(row)
            digits = phone_digits(raw)
            if digits:
                phones.add(digits)
    return phones


def load_email_set(paths: Iterable[str | Path]) -> set[str]:
    """Load emails from CSVs with an email column, or one email per line."""
    emails: set[str] = set()
    for p in paths:
        rows = list(_iter_lines(Path(p)))
        if not rows:
            continue
        col = None
        idx = find_column(rows[0], EMAIL_ALIASES)
        if idx is not None:
            col = rows[0].index(idx)
            rows = rows[1:]
        for row in rows:
            cells = [row[col]] if col is not None and col < len(row) else row
            for cell in cells:
                if "@" in cell and (email := normalize_email(cell)):
                    emails.add(email)
    return emails


def load_contact_log(paths: Iterable[str | Path]) -> dict[str, date]:
    """Map phone -> most recent contact date from one or more contact-log CSVs."""
    latest: dict[str, date] = {}
    for p in paths:
        table = read_table(p)
        phone_col = find_column(table.headers, PHONE_ALIASES)
        date_col = find_column(table.headers, DATE_ALIASES)
        if not phone_col or not date_col:
            raise ValueError(f"{p}: contact log needs a phone column and a date column")
        for row in table.rows:
            digits = phone_digits(row[phone_col])
            when = parse_date(row[date_col])
            if digits and when and (digits not in latest or when > latest[digits]):
                latest[digits] = when
    return latest
