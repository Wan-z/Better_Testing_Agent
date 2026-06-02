"""Analysis run endpoint — SSE streaming pipeline execution."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from web.backend.plots import plotspec_to_plotly
from web.backend.storage.local import LocalStorage
from web.backend.stubs import STUB_REPORT

router = APIRouter()
store = LocalStorage()


def _sse(data: object) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _enrich_plots(report: dict) -> dict:  # type: ignore[type-arg]
    """Convert PlotSpec data dicts to plotly_json fields in-place."""
    for plot in report.get("plots", []):
        plot["plotly_json"] = plotspec_to_plotly(plot)
    return report


async def _run_dry_run(session_id: str) -> object:
    """Yield SSE progress events then the stub report."""
    stages = [
        ("selecting_test", "Selecting statistical test…"),
        ("executing_test",  "Running Welch's t-test…"),
        ("generating_report", "Generating report…"),
    ]
    for stage, msg in stages:
        await asyncio.sleep(0.6)
        yield _sse({"type": "progress", "stage": stage, "message": msg})

    report = _enrich_plots(dict(STUB_REPORT))

    # Merge real profile if available
    if store.exists(session_id, "profile.json"):
        report["data_profile"] = json.loads(store.read(session_id, "profile.json"))

    # Merge real design if available
    if store.exists(session_id, "design.json"):
        report["study_design"] = json.loads(store.read(session_id, "design.json"))

    store.write_json(session_id, "report.json", report)
    store.set_status(session_id, "COMPLETE")

    yield _sse({"type": "result", "report": report})


@router.post("/sessions/{session_id}/run")
async def run_analysis(session_id: str) -> StreamingResponse:
    if not store.exists(session_id, "metadata.json"):
        raise HTTPException(status_code=404, detail="Session not found.")

    store.set_status(session_id, "RUNNING")

    return StreamingResponse(
        _run_dry_run(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
