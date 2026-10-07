"""Write the scrub outputs: clean file, removed-rows audit, and summary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .io import write_table
from .pipeline import Scrubber, ScrubResult


def summary_dict(result: ScrubResult, source: str) -> dict:
    return {
        "source": source,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "input_rows": result.input_rows,
        "kept_rows": len(result.kept),
        "removed_rows": len(result.removed),
        "columns": result.columns,
        "passes": [
            {
                "name": p.name,
                "description": p.description,
                "enabled": p.enabled,
                "removed": p.removed,
                "remaining": p.remaining,
            }
            for p in result.passes
        ],
    }


def summary_table(result: ScrubResult) -> str:
    """Plain-text table for the terminal and the Markdown report."""
    width = max(len(p.name) for p in result.passes)
    lines = [f"{'#':>2}  {'pass':<{width}}  {'removed':>8}  {'remaining':>9}", "-" * (width + 26)]
    lines.append(f"{'':>2}  {'input':<{width}}  {'':>8}  {result.input_rows:>9,}")
    for i, p in enumerate(result.passes, 1):
        removed = f"{p.removed:,}" if p.enabled else "skipped"
        lines.append(f"{i:>2}  {p.name:<{width}}  {removed:>8}  {p.remaining:>9,}")
    pct = 100 * len(result.kept) / result.input_rows if result.input_rows else 0
    lines.append("-" * (width + 26))
    lines.append(f"kept {len(result.kept):,} of {result.input_rows:,} rows ({pct:.1f}%)")
    return "\n".join(lines)


def write_outputs(scrubber: Scrubber, result: ScrubResult, out_dir: str | Path, source: str) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "clean": out / "clean.csv",
        "removed": out / "removed.csv",
        "summary_json": out / "summary.json",
        "summary_md": out / "summary.md",
    }

    headers, rows = scrubber.output_rows(result)
    write_table(paths["clean"], headers, rows)

    audit_headers = ["source_row", "removed_by", "reason", *result.headers]
    write_table(
        paths["removed"],
        audit_headers,
        (
            {"source_row": str(r.lead.line), "removed_by": r.pass_name, "reason": r.detail, **r.lead.row}
            for r in result.removed
        ),
    )

    summary = summary_dict(result, source)
    paths["summary_json"].write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    md = [
        f"# Scrub summary: {Path(source).name}",
        "",
        f"Generated {summary['generated_at']}",
        "",
        "```",
        summary_table(result),
        "```",
        "",
        "| Pass | What it removes | Removed |",
        "| --- | --- | ---: |",
        *(
            f"| {p.name} | {p.description} | {p.removed:,} |"
            if p.enabled
            else f"| {p.name} | {p.description} | skipped |"
            for p in result.passes
        ),
        "",
    ]
    paths["summary_md"].write_text("\n".join(md), encoding="utf-8")
    return paths
