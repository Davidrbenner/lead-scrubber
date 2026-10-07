from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from leadscrub import Config


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return path


@pytest.fixture
def make_csv(tmp_path):
    def _make(name: str, rows: list[list[str]]) -> Path:
        return write_csv(tmp_path / name, rows)

    return _make


@pytest.fixture
def cfg() -> Config:
    return Config(today=date(2026, 10, 1))
