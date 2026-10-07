"""Command-line interface: ``leadscrub run leads.csv [options]``."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from . import __version__
from .config import Config, load_config
from .io import read_table
from .pipeline import Scrubber
from .report import summary_table, write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leadscrub",
        description="Clean a lead list: validate, dedupe, and remove DNC, opt-out, customer, and recently contacted rows.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="scrub a lead file")
    run.add_argument("leads", type=Path, help="lead CSV to scrub")
    run.add_argument("-c", "--config", type=Path, help="TOML config file")
    run.add_argument(
        "-o", "--out", type=Path, default=Path("scrub-output"), help="output folder (default: scrub-output)"
    )
    run.add_argument("--mode", choices=["phone", "email"], help="what the list will be used for (default: phone)")
    run.add_argument("--phone-column")
    run.add_argument("--email-column")
    run.add_argument("--state-column")
    run.add_argument("--dnc", type=Path, action="append", default=[], help="DNC file (repeatable)")
    run.add_argument("--opt-out", type=Path, action="append", default=[], help="opt-out file (repeatable)")
    run.add_argument("--customers", type=Path, action="append", default=[], help="customer file (repeatable)")
    run.add_argument("--contact-log", type=Path, action="append", default=[], help="contact log CSV (repeatable)")
    run.add_argument("--recent-days", type=int, help="days a contact stays suppressed (default: 30)")
    run.add_argument("--exclude-state", action="append", default=[], help="state code to exclude (repeatable)")
    run.add_argument("--allow-fictional", action="store_true", help="accept 555-01XX numbers (for demo data)")
    run.add_argument("--no-normalized", action="store_true", help="don't add phone_e164/email_normalized columns")
    run.add_argument(
        "--as-of",
        dest="today",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="date to measure --recent-days from (default: today)",
    )
    run.add_argument("--dry-run", action="store_true", help="print the summary without writing files")
    return parser


def config_from_args(args: argparse.Namespace) -> Config:
    cfg = load_config(args.config) if args.config else Config()
    updates: dict = {
        "dnc": cfg.dnc + [p.resolve() for p in args.dnc],
        "opt_out": cfg.opt_out + [p.resolve() for p in args.opt_out],
        "customers": cfg.customers + [p.resolve() for p in args.customers],
        "contact_log": cfg.contact_log + [p.resolve() for p in args.contact_log],
        "exclude_states": cfg.exclude_states | {s.strip().upper() for s in args.exclude_state},
    }
    for flag, key in (
        ("mode", "mode"),
        ("phone_column", "phone_column"),
        ("email_column", "email_column"),
        ("state_column", "state_column"),
        ("recent_days", "recent_days"),
        ("today", "today"),
    ):
        if getattr(args, flag) is not None:
            updates[key] = getattr(args, flag)
    if args.allow_fictional:
        updates["allow_fictional"] = True
    if args.no_normalized:
        updates["add_normalized"] = False
    return replace(cfg, **updates)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(args)
        scrubber = Scrubber(cfg)
        result = scrubber.run(read_table(args.leads))
    except (ValueError, FileNotFoundError) as exc:
        print(f"leadscrub: error: {exc}", file=sys.stderr)
        return 2

    print(summary_table(result))
    if args.dry_run:
        return 0
    paths = write_outputs(scrubber, result, args.out, str(args.leads))
    print(f"\nclean rows:   {paths['clean']}")
    print(f"removed rows: {paths['removed']}")
    print(f"summary:      {paths['summary_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
