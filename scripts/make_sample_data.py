"""Generate fake, messy sample data for demos and tests.

Every phone number uses the 555-0100..0199 block, which is reserved for fiction,
so nothing here can match a real person. Run with --allow-fictional.

    python scripts/make_sample_data.py --rows 5000 --as-of 2026-10-01
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

FIRST = [
    "James",
    "Mary",
    "John",
    "Patricia",
    "Robert",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "Maria",
    "Jose",
    "Wei",
    "Aisha",
    "Omar",
    "Priya",
    "Luis",
    "Ana",
    "Kevin",
    "Grace",
]
LAST = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Nguyen",
    "Kim",
    "Patel",
    "Lopez",
    "Chen",
    "Wilson",
    "Anderson",
    "Thomas",
    "Lee",
    "Clark",
]
# Any structurally valid area code works since the 555-01XX block is fictional everywhere.
AREA_CODES = [f"{a}{b}{c}" for a in "23456789" for b in "0123456789" for c in "0123456789" if f"{b}{c}" != "11"]
STATES = ["CA"] * 10 + ["NV", "AZ", "AZ", "OR", "WA", "TX", "TX", "TX", "FL", "FL", "GA", "IL", "NY", "CO"]
STATE_NAMES = {"CA": "California", "NV": "Nevada", "AZ": "Arizona", "TX": "Texas", "FL": "Florida"}
SOURCES = ["Facebook Lead Ad", "Google Ads", "Website form", "Home show", "Referral"]
BAD_PHONES = ["911", "555-1234", "(000) 123-4567", "411-555-0123", "1234567890", "n/a", "call me", "2222222222"]


def fake_digits(rng: random.Random) -> str:
    return f"{rng.choice(AREA_CODES)}5550{rng.randint(100, 199)}"


def messy(d: str, rng: random.Random) -> str:
    style = rng.randint(0, 7)
    a, e, n = d[:3], d[3:6], d[6:]
    return [
        f"({a}) {e}-{n}",
        f"{a}-{e}-{n}",
        f"{a}.{e}.{n}",
        d,
        f"+1 {a} {e} {n}",
        f"1{d}",
        f"{a}-{e}-{n} x{rng.randint(1, 999)}",
        f" {a} {e} {n} ",
    ][style]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "examples")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    leads, pool = [], []
    for i in range(args.rows):
        r = rng.random()
        if pool and r < 0.07:  # duplicate an earlier lead with different formatting
            prev = rng.choice(pool)
            leads.append({**prev, "Phone": messy(prev["_d"], rng), "Lead ID": f"L{i + 1:05d}"})
            continue
        d = fake_digits(rng)
        first, last = rng.choice(FIRST), rng.choice(LAST)
        state = rng.choice(STATES)
        lead = {
            "Lead ID": f"L{i + 1:05d}",
            "First Name": first,
            "Last Name": last,
            "Phone": messy(d, rng),
            "Email": f"{first}.{last}{rng.randint(1, 99)}@example.com" if rng.random() < 0.8 else "",
            "State": STATE_NAMES.get(state, state) if rng.random() < 0.15 else state,
            "Source": rng.choice(SOURCES),
            "_d": d,
        }
        if r < 0.10:
            lead["Phone"] = rng.choice(BAD_PHONES)
        elif r < 0.13:
            lead["Phone"] = ""
        else:
            pool.append(lead)
        leads.append(lead)

    good = list({ld["_d"]: ld for ld in pool}.values())
    rng.shuffle(good)
    n = len(good)
    dnc = good[: n // 12]
    opt_out = [ld for ld in good[n // 12 : n // 12 + n // 20] if ld["Email"]]
    customers = good[n // 12 + n // 20 : n // 12 + n // 20 + n // 25]
    contacted = good[n // 6 : n // 6 + n // 8]

    headers = ["Lead ID", "First Name", "Last Name", "Phone", "Email", "State", "Source"]
    with (out / "leads.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, headers, extrasaction="ignore")
        w.writeheader()
        w.writerows(leads)
    # DNC in the FTC download layout: area code, then 7-digit number.
    (out / "dnc.txt").write_text("".join(f"{ld['_d'][:3]},{ld['_d'][3:]}\n" for ld in dnc), encoding="utf-8")
    with (out / "opt_out.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["email", "phone", "opted_out_on"])
        for ld in opt_out:
            w.writerow([ld["Email"].upper(), "", (args.as_of - timedelta(days=rng.randint(1, 400))).isoformat()])
    with (out / "customers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Customer Name", "Mobile Phone"])
        for ld in customers:
            w.writerow([f"{ld['First Name']} {ld['Last Name']}", messy(ld["_d"], rng)])
    with (out / "contact_log.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["phone", "contacted_at", "outcome"])
        for ld in contacted:
            when = args.as_of - timedelta(days=rng.randint(0, 90))
            w.writerow(
                [
                    ld["_d"],
                    when.strftime("%m/%d/%Y"),
                    rng.choice(["no answer", "voicemail", "callback", "not interested"]),
                ]
            )
    print(f"wrote {len(leads)} leads and suppression files to {out}")


if __name__ == "__main__":
    main()
