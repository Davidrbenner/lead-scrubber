"""Scrub configuration, loaded from TOML and/or CLI flags."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

Mode = Literal["phone", "email"]


@dataclass
class Config:
    mode: Mode = "phone"
    # Column names in the lead file. None means auto-detect.
    phone_column: str | None = None
    email_column: str | None = None
    state_column: str | None = None

    dnc: list[Path] = field(default_factory=list)
    opt_out: list[Path] = field(default_factory=list)
    customers: list[Path] = field(default_factory=list)
    contact_log: list[Path] = field(default_factory=list)
    recent_days: int = 30
    exclude_states: set[str] = field(default_factory=set)

    allow_fictional: bool = False
    add_normalized: bool = True
    today: date = field(default_factory=date.today)

    def validate(self) -> None:
        if self.mode not in ("phone", "email"):
            raise ValueError(f"mode must be 'phone' or 'email', got {self.mode!r}")
        if self.recent_days < 0:
            raise ValueError("recent_days must be 0 or more")
        for path in [*self.dnc, *self.opt_out, *self.customers, *self.contact_log]:
            if not path.is_file():
                raise FileNotFoundError(f"suppression file not found: {path}")


def _paths(value: object, base: Path) -> list[Path]:
    if value is None:
        return []
    items = [value] if isinstance(value, str) else list(value)  # type: ignore[arg-type]
    return [(base / str(v)).resolve() for v in items]


def load_config(path: str | Path) -> Config:
    """Load a TOML config. Relative file paths resolve against the config's folder."""
    path = Path(path)
    base = path.parent
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    columns = data.get("columns", {})
    supp = data.get("suppression", {})
    recent = data.get("recent_contact", {})
    states = data.get("states", {})
    options = data.get("options", {})

    return Config(
        mode=data.get("mode", "phone"),
        phone_column=columns.get("phone"),
        email_column=columns.get("email"),
        state_column=columns.get("state"),
        dnc=_paths(supp.get("dnc"), base),
        opt_out=_paths(supp.get("opt_out"), base),
        customers=_paths(supp.get("customers"), base),
        contact_log=_paths(recent.get("log"), base),
        recent_days=int(recent.get("days", 30)),
        exclude_states={s.strip().upper() for s in states.get("exclude", [])},
        allow_fictional=bool(options.get("allow_fictional", False)),
        add_normalized=bool(options.get("add_normalized", True)),
    )
