"""HTML export endpoint."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from web.backend.export import render_html
from web.backend.plots import plotspec_to_plotly
from web.backend.storage.local import LocalStorage

router = APIRouter()
store = LocalStorage()


def _enrich_plots(report: dict) -> dict:  # type: ignore[type-arg]
    for plot in report.get("plots", []):
        if "plotly_json" not in plot:
            plot["plotly_json"] = plotspec_to_plotly(plot)
    return report


@router.get("/sessions/{session_id}/export/html", response_class=HTMLResponse)
async def export_html(session_id: str) -> HTMLResponse:
    if not store.exists(session_id, "report.json"):
        raise HTTPException(status_code=404, detail="Report not found. Run analysis first.")

    report = json.loads(store.read(session_id, "report.json"))
    _enrich_plots(report)

    meta = store.get_metadata(session_id)
    generated_at = meta.get("completed_at")

    html = render_html(report, session_id, generated_at)
    filename = f"hta-report-{session_id[:8]}.html"
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
