import json
from pathlib import Path

from leadscrub.cli import main
from leadscrub.config import load_config

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_example_config_resolves_paths():
    cfg = load_config(EXAMPLES / "config.toml")
    assert cfg.dnc == [(EXAMPLES / "dnc.txt").resolve()]
    assert cfg.exclude_states == {"TX", "FL"}
    assert cfg.allow_fictional


def test_end_to_end_on_sample_data(tmp_path, capsys):
    code = main(
        [
            "run",
            str(EXAMPLES / "leads.csv"),
            "-c",
            str(EXAMPLES / "config.toml"),
            "--as-of",
            "2026-10-01",
            "-o",
            str(tmp_path),
        ]
    )
    assert code == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["input_rows"] == 5000
    assert summary["kept_rows"] + summary["removed_rows"] == 5000
    assert all(p["enabled"] for p in summary["passes"])
    assert all(p["removed"] > 0 for p in summary["passes"])
    clean = (tmp_path / "clean.csv").read_text().splitlines()
    assert len(clean) == summary["kept_rows"] + 1
    assert "phone_e164" in clean[0]
    removed = (tmp_path / "removed.csv").read_text().splitlines()
    assert removed[0].startswith("source_row,removed_by,reason")
    assert "kept" in capsys.readouterr().out


def test_flags_without_config(make_csv, tmp_path, capsys):
    leads = make_csv("l.csv", [["Phone", "State"], ["9095552368", "CA"], ["3105552368", "TX"]])
    code = main(["run", str(leads), "--exclude-state", "tx", "--dry-run"])
    assert code == 0
    assert "kept 1 of 2" in capsys.readouterr().out
    assert not (tmp_path / "scrub-output").exists()


def test_errors_return_exit_code_2(make_csv, capsys):
    leads = make_csv("l.csv", [["name"], ["x"]])
    assert main(["run", str(leads)]) == 2
    assert "no phone column" in capsys.readouterr().err
