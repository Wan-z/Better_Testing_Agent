"""Command-line interface for the Hypothesis Testing Agent.

    hta run --data data.csv --hypothesis "A < B" --outcome score --group arm
    hta run --data data.csv --hypothesis "x ~ y" --outcome y --predictor x
    hta version

Output is rendered with Rich: a panel for the primary result (p-value coloured by
significance), tables for assumption checks and caveats, and the plain-language summary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hta import __version__
from hta.agent import HypothesisTestingAgent
from hta.models.report import Report

# Effect-size names and labels contain Greek/accented characters (ρ, α, η, é) that a default
# Windows cp1252 console cannot encode. Switch stdout/stderr to UTF-8 *before* building the
# Rich console (which captures the stream), degrading gracefully if reconfigure is unavailable.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

app = typer.Typer(add_completion=False, help="Hypothesis Testing Agent (HTA) CLI.")
console = Console()

_STATUS_COLOR = {"MET": "green", "VIOLATED": "red", "MARGINAL": "yellow", "UNTESTABLE": "dim"}
_SEVERITY_COLOR = {"INFO": "blue", "WARNING": "yellow", "CRITICAL": "red"}


def _render(report: Report) -> None:
    r = report.test_result
    es = r.effect_size
    sig_color = "green" if r.is_significant else "white"
    sig_word = "significant" if r.is_significant else "not significant"
    body = (
        f"[bold]{r.test_used.value}[/bold]\n"
        f"statistic = {r.statistic:.4g}"
        + (f"    df = {r.degrees_of_freedom:.4g}" if r.degrees_of_freedom is not None else "")
        + f"\np = [{sig_color}]{r.p_value:.4g}[/{sig_color}]  ({sig_word} at α = 0.05)\n"
        f"{es.measure_name} = {es.value:.4g} "
        f"({es.interpretation}; 95% CI [{es.ci_lower:.4g}, {es.ci_upper:.4g}])"
    )
    console.print(Panel(body, title="Primary result", border_style=sig_color, expand=False))

    if r.assumption_checks:
        t = Table(title="Assumption checks", show_lines=False, expand=False)
        t.add_column("Assumption")
        t.add_column("Status")
        t.add_column("Note", overflow="fold")
        for c in r.assumption_checks:
            color = _STATUS_COLOR.get(c.status.value, "white")
            t.add_row(c.assumption_name, f"[{color}]{c.status.value}[/{color}]", c.note)
        console.print(t)

    if report.caveats:
        t = Table(title="Caveats", show_lines=False, expand=False)
        t.add_column("Severity")
        t.add_column("Message", overflow="fold")
        for cav in report.caveats:
            color = _SEVERITY_COLOR.get(cav.severity.value, "white")
            t.add_row(f"[{color}]{cav.severity.value}[/{color}]", cav.message)
        console.print(t)

    console.print(Panel(report.plain_language_summary, title="Plain-language summary",
                        border_style="cyan", expand=False))


@app.command()
def run(
    data: Path = typer.Option(..., "--data", exists=True, dir_okay=False,
                              help="Path to the input CSV file."),
    hypothesis: str = typer.Option(..., "--hypothesis", help="The research hypothesis."),
    outcome: str = typer.Option(..., "--outcome", help="Outcome (dependent) variable column."),
    group: Optional[str] = typer.Option(None, "--group", help="Grouping variable (comparison)."),
    predictor: Optional[str] = typer.Option(None, "--predictor",
                                            help="Predictor variable (association)."),
    design_json: Optional[Path] = typer.Option(
        None, "--design-json", exists=True, dir_okay=False,
        help=(
            "Path to a study design JSON file (e.g. exported from a previous web-app session). "
            "When omitted a default observational design is assumed. "
            "The interactive dialogue is available only via the web app."
        ),
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without any LLM API calls."),
) -> None:
    """Profile the data, select and run the appropriate test, and print a report."""
    import json
    import pandas as pd

    from hta.models.design import StudyDesign

    design = None
    if design_json is not None:
        try:
            design = StudyDesign.model_validate(json.loads(design_json.read_text()))
        except Exception as exc:
            console.print(f"[red]Error loading design JSON:[/red] {exc}")
            raise typer.Exit(code=1)

    agent = HypothesisTestingAgent(dry_run=dry_run)
    try:
        df = pd.read_csv(data)
        report = agent.run(df, hypothesis, outcome, group, predictor, design=design)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    _render(report)


@app.command()
def version() -> None:
    """Print the HTA version."""
    console.print(f"Hypothesis Testing Agent v{__version__}")


if __name__ == "__main__":
    app()
