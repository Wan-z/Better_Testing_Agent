"""HTML report export — renders report.html.j2 to a self-contained HTML string."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_html(report: dict, session_id: str, generated_at: str | None = None) -> str:  # type: ignore[type-arg]
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    template = _env.get_template("report.html.j2")
    return template.render(report=report, session_id=session_id, generated_at=generated_at)
