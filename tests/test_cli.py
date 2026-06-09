"""Tests for the CLI (`hta.cli`) via Typer's test runner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from hta.cli import app

runner = CliRunner()

_CSV = (
    "arm,score\n"
    "A,10.2\nA,11.4\nA,9.1\nA,12.3\nA,10.8\nA,11.0\nA,13.1\nA,9.6\nA,10.5\nA,12.0\n"
    "B,20.2\nB,21.4\nB,19.1\nB,22.3\nB,20.8\nB,21.0\nB,23.1\nB,19.6\nB,20.5\nB,22.0\n"
)


def _write_csv(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text(_CSV, encoding="utf-8")
    return p


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_run(tmp_path: Path) -> None:
    csv = _write_csv(tmp_path)
    result = runner.invoke(app, ["run", "--data", str(csv), "--hypothesis",
                                 "does score differ by arm?", "--outcome", "score",
                                 "--group", "arm"])
    assert result.exit_code == 0
    assert "WELCH_T" in result.stdout


def test_run_bad_outcome(tmp_path: Path) -> None:
    csv = _write_csv(tmp_path)
    result = runner.invoke(app, ["run", "--data", str(csv), "--hypothesis", "q",
                                 "--outcome", "nope"])
    assert result.exit_code == 1


def test_run_missing_file() -> None:
    result = runner.invoke(app, ["run", "--data", "no_such_file.csv", "--hypothesis", "q",
                                 "--outcome", "score"])
    assert result.exit_code != 0
