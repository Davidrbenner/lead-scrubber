# leadscrub

[![CI](https://github.com/Davidrbenner/lead-scrubber/actions/workflows/ci.yml/badge.svg)](https://github.com/Davidrbenner/lead-scrubber/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

A command-line tool that cleans a lead list before it goes to a dialer or an email campaign. It runs 8 passes in order: validation, dedupe, Do Not Call, opt-outs, existing customers, recent contacts, and state exclusions. Every removed row is logged with the pass that removed it and why.

Built for outbound sales teams that buy or collect leads from ad platforms, web forms, and events, then need a list that's clean, deduplicated, and safe to call.

## Example

On the included sample file (5,000 fake leads):

```
$ leadscrub run examples/leads.csv -c examples/config.toml --as-of 2026-10-01

 #  pass                 removed  remaining
--------------------------------------------
    input                             5,000
 1  missing_contact          154      4,846
 2  invalid_contact          160      4,686
 3  duplicate                452      4,234
 4  dnc                      352      3,882
 5  opt_out                  175      3,707
 6  existing_customer        169      3,538
 7  recently_contacted       181      3,357
 8  excluded_state           727      2,630
--------------------------------------------
kept 2,630 of 5,000 rows (52.6%)

clean rows:   scrub-output/clean.csv
removed rows: scrub-output/removed.csv
summary:      scrub-output/summary.md
```

## The passes

Passes run in this order. Each one only sees the rows that survived the ones before it, so every row is removed exactly once and the counts add up.

| # | Pass | Removes |
| --- | --- | --- |
| 1 | `missing_contact` | Rows with no phone (or no email in email mode) |
| 2 | `invalid_contact` | Numbers that can't be US phone numbers: wrong length, area code or exchange starting with 0/1, N11 codes like 911, repeated digits, 555-01XX. Malformed emails in email mode. |
| 3 | `duplicate` | Repeat phone (or email) within the file. Formatting doesn't matter: `(909) 555-2368` and `+1 909.555.2368` match. The first row is kept. |
| 4 | `dnc` | Numbers on your Do Not Call files |
| 5 | `opt_out` | Phones or emails on your internal opt-out / unsubscribe lists |
| 6 | `existing_customer` | Phones or emails already in your customer list |
| 7 | `recently_contacted` | Numbers in your contact log within the last N days (default 30) |
| 8 | `excluded_state` | Leads in states you don't serve or call. Accepts `TX` or `Texas`. |

Passes 4 to 8 are skipped if you don't give them a file or setting.

## Outputs

| File | Contents |
| --- | --- |
| `clean.csv` | Kept rows with your original columns unchanged, plus `phone_e164` (`+19095552368`) and `email_normalized` for loading into a dialer or CRM |
| `removed.csv` | Every removed row with `source_row`, `removed_by`, and `reason` (for example `duplicate of row 41` or `contacted 2026-09-14 (within 30 days)`) |
| `summary.json` | Counts per pass, for scripts and dashboards |
| `summary.md` | The same summary as a readable report |

## Install

Requires Python 3.11 or newer. No third-party dependencies.

```bash
git clone https://github.com/Davidrbenner/lead-scrubber.git
cd lead-scrubber
pip install .
```

## Usage

With a config file:

```bash
leadscrub run leads.csv -c config.toml -o out/
```

Or with flags only:

```bash
leadscrub run leads.csv \
  --dnc national_dnc.txt --dnc state_dnc.txt \
  --opt-out unsubscribes.csv \
  --customers customers.csv \
  --contact-log call_log.csv --recent-days 30 \
  --exclude-state TX --exclude-state FL \
  -o out/
```

Flags add to whatever the config file sets. Use `--dry-run` to see the counts without writing files, and `--mode email` to scrub an email list instead of a call list. Run `leadscrub run --help` for everything.

### Config file

See [`examples/config.toml`](examples/config.toml):

```toml
mode = "phone"

[columns]            # optional, auto-detected if left out
phone = "Phone"

[suppression]
dnc = ["dnc.txt"]
opt_out = ["opt_out.csv"]
customers = ["customers.csv"]

[recent_contact]
log = ["contact_log.csv"]
days = 30

[states]
exclude = ["TX", "FL"]
```

Paths are relative to the config file.

### Input formats

- **Lead files:** CSV with a header row. Comma, semicolon, tab, and pipe delimiters are detected. UTF-8 (with or without BOM) and Windows-1252 Excel exports both work.
- **Columns:** detected from common names (`Phone`, `Mobile Phone`, `Cell`, `Email Address`, `State`, ...). Override with `--phone-column` and friends.
- **DNC files:** one number per line, the FTC download layout (`909,5552368`), or any CSV with a phone column.
- **Opt-out and customer files:** any CSV with a phone and/or email column.
- **Contact logs:** CSV with a phone column and a date column (`2026-09-14`, `09/14/2026`, or timestamps).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=leadscrub     # 59 tests, about 97% coverage
ruff check . && ruff format --check .
```

`scripts/make_sample_data.py` regenerates the sample files. Every phone number in them is in the 555-0100 to 555-0199 range, which is reserved for fiction, so the sample can never match a real person. The sample config sets `allow_fictional = true` so those numbers pass validation.

### Layout

```
src/leadscrub/
  normalize.py   phone, email, state, and date parsing and validation
  io.py          CSV reading, column detection, suppression list loaders
  pipeline.py    the 8 passes and the Scrubber that runs them
  report.py      clean / removed / summary outputs
  config.py      TOML config
  cli.py         command line
```

### Performance

Suppression lists load into hash sets, so each check is constant time. 500,000 rows with all 8 passes run in about 10 seconds on a laptop. The whole file is held in memory, so plan on roughly 1 GB of RAM per million rows.

## Compliance note

This tool helps you apply your own suppression lists consistently and keeps an audit trail of every removal. It is not legal advice and does not by itself make a campaign TCPA compliant. You still need current National and state DNC data (the National Registry requires an SAN from the FTC), consent records, and calling-hour rules for the states you call.

## License

MIT. See [LICENSE](LICENSE).
