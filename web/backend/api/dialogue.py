"""Study design dialogue endpoint — SSE streaming."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from web.backend.config import DRY_RUN, AZURE_OPENAI_API_KEY, AZURE_OPENAI_BASE_URL, AZURE_OPENAI_DEPLOYMENT
from web.backend.schemas import DialoguePayload
from web.backend.storage.local import LocalStorage
from web.backend.stubs import STUB_DIALOGUE_TURNS, STUB_STUDY_DESIGN

router = APIRouter()
store = LocalStorage()


def _sse(data: object) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_dry_run(session_id: str, turn: int) -> object:
    """Yield SSE chunks for dry-run mode."""
    is_last = turn >= len(STUB_DIALOGUE_TURNS) - 1
    text = STUB_DIALOGUE_TURNS[min(turn, len(STUB_DIALOGUE_TURNS) - 1)]

    for word in text.split(" "):
        yield _sse({"type": "token", "content": word + " "})
        await asyncio.sleep(0.03)

    if is_last:
        store.write_json(session_id, "design.json", STUB_STUDY_DESIGN)
        store.set_status(session_id, "DESIGNED")
        yield _sse({"type": "done", "is_complete": True, "study_design": STUB_STUDY_DESIGN})
    else:
        yield _sse({"type": "done", "is_complete": False})


async def _stream_live(session_id: str, history: list[dict[str, str]]) -> object:  # type: ignore[return]
    """Yield SSE chunks from the real GPT-5.4 API (Phase W3)."""
    from openai import AsyncAzureOpenAI

    client = AsyncAzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_BASE_URL,
        api_version="2024-02-01",
    )

    SYSTEM = (
        "You are a statistical study design expert. Ask up to 3 questions per turn to "
        "elicit: (1) experimental vs observational design, (2) independence of observations, "
        "(3) potential confounders, (4) relationship form (linear/monotone/nonlinear) if "
        "both variables are continuous. When you have enough information call the "
        "capture_study_design function."
    )

    TOOLS = [{
        "type": "function",
        "function": {
            "name": "capture_study_design",
            "description": "Record the fully-elicited study design.",
            "parameters": {
                "type": "object",
                "properties": {
                    "design_type": {"type": "string", "enum": ["EXPERIMENTAL", "OBSERVATIONAL", "QUASI_EXPERIMENTAL"]},
                    "measurement_type": {"type": "string", "enum": ["BETWEEN_SUBJECTS", "WITHIN_SUBJECTS", "MIXED"]},
                    "is_randomized": {"type": "boolean"},
                    "relationship_form": {"type": "string", "enum": ["linear", "monotone", "nonlinear", "unknown"]},
                    "confounder_names": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["design_type", "measurement_type", "is_randomized"],
            },
        },
    }]

    accumulated = ""
    tool_call_args = ""
    is_tool_call = False

    stream = await client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "system", "content": SYSTEM}] + history,  # type: ignore[arg-type]
        tools=TOOLS,  # type: ignore[arg-type]
        stream=True,
        max_completion_tokens=512,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue
        if delta.tool_calls:
            is_tool_call = True
            for tc in delta.tool_calls:
                if tc.function and tc.function.arguments:
                    tool_call_args += tc.function.arguments
        elif delta.content:
            accumulated += delta.content
            yield _sse({"type": "token", "content": delta.content})

    if is_tool_call and tool_call_args:
        args = json.loads(tool_call_args)
        confounders = [
            {"name": n, "role": "CONFOUNDER", "is_measured": True,
             "adjustment_recommended": True, "rationale": ""}
            for n in args.get("confounder_names", [])
        ]
        form = args.get("relationship_form", "unknown")
        design = {
            "design_type": args["design_type"],
            "measurement_type": args["measurement_type"],
            "is_randomized": args["is_randomized"],
            "confounders": confounders,
            "notes": [form] if form not in ("linear", "unknown") else [],
        }
        store.write_json(session_id, "design.json", design)
        store.set_status(session_id, "DESIGNED")
        yield _sse({"type": "done", "is_complete": True, "study_design": design})
    else:
        if accumulated:
            history.append({"role": "assistant", "content": accumulated})
            store.write_json(session_id, "dialogue_history.json", history)
        yield _sse({"type": "done", "is_complete": False})


@router.post("/sessions/{session_id}/dialogue")
async def dialogue(session_id: str, payload: DialoguePayload) -> StreamingResponse:
    if not store.exists(session_id, "metadata.json"):
        raise HTTPException(status_code=404, detail="Session not found.")

    meta = store.get_metadata(session_id)
    turn: int = meta.get("dialogue_turn", 0)

    # Advance turn counter
    meta["dialogue_turn"] = turn + 1
    store.write_json(session_id, "metadata.json", meta)

    if DRY_RUN:
        return StreamingResponse(
            _stream_dry_run(session_id, turn),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Build message history from stored dialogue
    history_path = "dialogue_history.json"
    history: list[dict[str, str]] = []
    if store.exists(session_id, history_path):
        history = json.loads(store.read(session_id, history_path))  # type: ignore[assignment]

    if payload.user_message != "__init__":
        history.append({"role": "user", "content": payload.user_message})

    store.write_json(session_id, history_path, history)

    return StreamingResponse(
        _stream_live(session_id, history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
