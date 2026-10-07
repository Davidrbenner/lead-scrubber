"""The scrub pipeline: ordered passes that each remove leads with a reason."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from .config import Config
from .io import (
    EMAIL_ALIASES,
    PHONE_ALIASES,
    STATE_ALIASES,
    Table,
    find_column,
    load_contact_log,
    load_email_set,
    load_phone_set,
)
from .normalize import format_e164, is_valid_email, is_valid_nanp, normalize_email, normalize_state, phone_digits


@dataclass(slots=True)
class Lead:
    row: dict[str, str]
    line: int  # 1-based data row number in the source file (header excluded)
    raw_phone: str
    phone: str | None  # 10 digits if parseable
    email: str | None
    state: str | None


@dataclass(slots=True)
class Removal:
    lead: Lead
    pass_name: str
    detail: str


@dataclass
class PassResult:
    name: str
    description: str
    removed: int
    remaining: int
    enabled: bool


@dataclass
class ScrubResult:
    headers: list[str]
    columns: dict[str, str | None]
    kept: list[Lead]
    removed: list[Removal]
    passes: list[PassResult] = field(default_factory=list)
    input_rows: int = 0


# A check returns None to keep the lead, or a short reason to remove it.
Check = Callable[[Lead], "str | None"]


@dataclass
class Pass:
    name: str
    description: str
    enabled: bool
    make_check: Callable[[], Check]


class Scrubber:
    def __init__(self, config: Config):
        config.validate()
        self.config = config

    def _columns(self, table: Table) -> dict[str, str | None]:
        cfg = self.config
        cols = {
            "phone": cfg.phone_column or find_column(table.headers, PHONE_ALIASES),
            "email": cfg.email_column or find_column(table.headers, EMAIL_ALIASES),
            "state": cfg.state_column or find_column(table.headers, STATE_ALIASES),
        }
        for kind, name in cols.items():
            if name is not None and name not in table.headers:
                raise ValueError(f"{kind} column {name!r} not in file. Columns: {', '.join(table.headers)}")
        if cfg.mode == "phone" and not cols["phone"]:
            raise ValueError("no phone column found; set it with --phone-column or [columns].phone")
        if cfg.mode == "email" and not cols["email"]:
            raise ValueError("no email column found; set it with --email-column or [columns].email")
        return cols

    def _passes(self) -> list[Pass]:
        cfg = self.config
        by_phone = cfg.mode == "phone"

        def missing() -> Check:
            if by_phone:
                return lambda ld: None if ld.raw_phone else "no phone number"
            return lambda ld: None if ld.email else "no email address"

        def invalid() -> Check:
            if by_phone:

                def check_phone(ld: Lead) -> str | None:
                    if ld.phone is None:
                        return f"unparseable phone {ld.raw_phone!r}"
                    if not is_valid_nanp(ld.phone, cfg.allow_fictional):
                        return f"invalid US number {ld.phone}"
                    return None

                return check_phone
            return lambda ld: None if ld.email and is_valid_email(ld.email) else f"invalid email {ld.email!r}"

        def duplicate() -> Check:
            seen: dict[str, int] = {}

            def check(ld: Lead) -> str | None:
                key = ld.phone if by_phone else ld.email
                assert key is not None  # guaranteed by earlier passes
                if key in seen:
                    return f"duplicate of row {seen[key]}"
                seen[key] = ld.line
                return None

            return check

        def phone_list(paths, label: str) -> Callable[[], Check]:
            def make() -> Check:
                phones = load_phone_set(paths)
                return lambda ld: f"phone on {label}" if ld.phone and ld.phone in phones else None

            return make

        def phone_or_email_list(paths, label: str) -> Callable[[], Check]:
            def make() -> Check:
                phones, emails = load_phone_set(paths), load_email_set(paths)

                def check(ld: Lead) -> str | None:
                    if ld.phone and ld.phone in phones:
                        return f"phone on {label}"
                    if ld.email and ld.email in emails:
                        return f"email on {label}"
                    return None

                return check

            return make

        def recent() -> Check:
            log = load_contact_log(cfg.contact_log)
            cutoff = cfg.today - timedelta(days=cfg.recent_days)

            def check(ld: Lead) -> str | None:
                last = log.get(ld.phone) if ld.phone else None
                if last and last >= cutoff:
                    return f"contacted {last.isoformat()} (within {cfg.recent_days} days)"
                return None

            return check

        def states() -> Check:
            return lambda ld: f"excluded state {ld.state}" if ld.state in cfg.exclude_states else None

        contact = "phone" if by_phone else "email"
        return [
            Pass("missing_contact", f"Rows with no {contact}", True, missing),
            Pass(
                "invalid_contact",
                f"Malformed or undialable {contact}" if by_phone else "Malformed email",
                True,
                invalid,
            ),
            Pass("duplicate", f"Repeat {contact} within the file (first kept)", True, duplicate),
            Pass("dnc", "Do Not Call list matches", bool(cfg.dnc), phone_list(cfg.dnc, "DNC list")),
            Pass(
                "opt_out",
                "Internal opt-out / unsubscribe matches",
                bool(cfg.opt_out),
                phone_or_email_list(cfg.opt_out, "opt-out list"),
            ),
            Pass(
                "existing_customer",
                "Already a customer",
                bool(cfg.customers),
                phone_or_email_list(cfg.customers, "customer list"),
            ),
            Pass("recently_contacted", f"Contacted in the last {cfg.recent_days} days", bool(cfg.contact_log), recent),
            Pass("excluded_state", "In an excluded state", bool(cfg.exclude_states), states),
        ]

    def run(self, table: Table) -> ScrubResult:
        cols = self._columns(table)
        leads = []
        for i, row in enumerate(table.rows, start=1):
            raw_phone = row.get(cols["phone"], "") if cols["phone"] else ""
            leads.append(
                Lead(
                    row=row,
                    line=i,
                    raw_phone=raw_phone,
                    phone=phone_digits(raw_phone),
                    email=normalize_email(row.get(cols["email"], "")) if cols["email"] else None,
                    state=normalize_state(row.get(cols["state"], "")) if cols["state"] else None,
                )
            )

        result = ScrubResult(headers=list(table.headers), columns=cols, kept=[], removed=[], input_rows=len(leads))
        for p in self._passes():
            if not p.enabled:
                result.passes.append(PassResult(p.name, p.description, 0, len(leads), False))
                continue
            check = p.make_check()
            survivors = []
            for lead in leads:
                reason = check(lead)
                if reason is None:
                    survivors.append(lead)
                else:
                    result.removed.append(Removal(lead, p.name, reason))
            result.passes.append(PassResult(p.name, p.description, len(leads) - len(survivors), len(survivors), True))
            leads = survivors

        result.kept = leads
        return result

    def output_rows(self, result: ScrubResult) -> tuple[list[str], list[dict[str, str]]]:
        """Clean rows in original column order, plus normalized columns if enabled."""
        headers = list(result.headers)
        if not self.config.add_normalized:
            return headers, [ld.row for ld in result.kept]
        extra = []
        if result.columns["phone"]:
            extra.append("phone_e164")
        if result.columns["email"]:
            extra.append("email_normalized")
        rows = []
        for ld in result.kept:
            row = dict(ld.row)
            if "phone_e164" in extra:
                valid = ld.phone and is_valid_nanp(ld.phone, self.config.allow_fictional)
                row["phone_e164"] = format_e164(ld.phone) if valid else ""
            if "email_normalized" in extra:
                row["email_normalized"] = ld.email or ""
            rows.append(row)
        return headers + [c for c in extra if c not in headers], rows
