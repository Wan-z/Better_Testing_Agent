"""Study design dialogue endpoint — SSE streaming."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from web.backend.config import (
    DRY_RUN, LLM_PROVIDER,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, IS_AZURE_OPENAI,
)
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


def _system_prompt(
    subtype_suggestive: bool = False,
    dataset_columns: list[str] | None = None,
) -> str:
    """Build the dialogue system prompt, injecting a BET subgroup hint when warranted.

    Rule 8 (TECHNICAL_REPORT §6): if BET detected mixture-type nonlinear dependence,
    ask the researcher whether they suspect a latent subgroup/subtype before locking
    the design — that answer is captured as `subgroup_structure_suspected`.
    """
    base = (
        "You are a statistical study design expert. Ask up to 3 questions per turn to "
        "elicit: (1) experimental vs observational design, (2) independence of observations, "
        "(3) potential confounders, (4) relationship form (linear/monotone/nonlinear) if "
        "both variables are continuous, (5) whether a latent subgroup or subtype is "
        "suspected to drive the pattern. When you have enough information call the "
        "capture_study_design tool."
    )
    if dataset_columns:
        col_list = ", ".join(dataset_columns)
        base += (
            f"\n\nThe dataset contains these columns: {col_list}. "
            "When recording confounders in capture_study_design, use the exact column name "
            "for any confounder that is measurable from this dataset (e.g. 'temp_avg_f' not "
            "'temperature'). Use a descriptive name only for confounders not present in the data."
        )
    if subtype_suggestive:
        base += (
            "\n\nIMPORTANT: The BET nonlinear-dependence screen flagged mixture-type patterns "
            "in this dataset — shapes (bimodal, checkerboard, parabolic) that often arise from "
            "an unmodelled subgroup or biological subtype. Before recording the design, ask the "
            "researcher whether they suspect such a latent subgroup is present and whether a "
            "stratified analysis within subgroups is warranted."
        )
    return base


TOOL_SCHEMA: dict = {
    "name": "capture_study_design",
    "description": "Record the fully-elicited study design.",
    "properties": {
        "design_type": {"type": "string", "enum": ["EXPERIMENTAL", "OBSERVATIONAL", "QUASI_EXPERIMENTAL"]},
        "measurement_type": {"type": "string", "enum": ["BETWEEN_SUBJECTS", "WITHIN_SUBJECTS", "MIXED"]},
        "is_randomized": {"type": "boolean"},
        "relationship_form": {"type": "string", "enum": ["linear", "monotone", "nonlinear", "unknown"]},
        "confounder_names": {"type": "array", "items": {"type": "string"}},
        "subgroup_structure_suspected": {
            "type": "boolean",
            "description": (
                "True if the researcher suspects a latent subgroup or subtype drives "
                "the observed dependence pattern (relevant when BET finds mixture-type "
                "nonlinear shapes)."
            ),
        },
    },
    "required": ["design_type", "measurement_type", "is_randomized"],
}


def _build_design(args: dict) -> dict:  # type: ignore[type-arg]
    confounders = [
        {"name": n, "role": "CONFOUNDER", "is_measured": True,
         "adjustment_recommended": True, "rationale": ""}
        for n in args.get("confounder_names", [])
    ]
    form = args.get("relationship_form", "unknown")
    notes: list[str] = [form] if form not in ("linear", "unknown") else []
    if args.get("subgroup_structure_suspected"):
        notes.append("subgroup_structure_suspected")
    return {
        "design_type": args["design_type"],
        "measurement_type": args["measurement_type"],
        "is_randomized": args["is_randomized"],
        "confounders": confounders,
        "notes": notes,
    }


async def _stream_live(session_id: str, history: list[dict[str, str]],  # type: ignore[return]
                       system: str) -> object:
    """Yield SSE chunks — routes to Anthropic or OpenAI based on LLM_PROVIDER."""
    if LLM_PROVIDER == "anthropic":
        async for chunk in _stream_anthropic(session_id, history, system):
            yield chunk
    else:
        async for chunk in _stream_openai(session_id, history, system):
            yield chunk


async def _stream_anthropic(session_id: str, history: list[dict[str, str]],  # type: ignore[return]
                             system: str) -> object:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    tools: list[anthropic.types.ToolParam] = [{
        "name": TOOL_SCHEMA["name"],
        "description": TOOL_SCHEMA["description"],
        "input_schema": {
            "type": "object",
            "properties": TOOL_SCHEMA["properties"],
            "required": TOOL_SCHEMA["required"],
        },
    }]

    accumulated = ""
    tool_input_json = ""
    is_tool_call = False

    async with client.messages.stream(
        model=ANTHROPIC_MODEL,
        system=system,
        messages=history,  # type: ignore[arg-type]
        tools=tools,
        max_tokens=512,
    ) as stream:
        async for event in stream:
            if event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    accumulated += event.delta.text
                    yield _sse({"type": "token", "content": event.delta.text})
                elif event.delta.type == "input_json_delta":
                    is_tool_call = True
                    tool_input_json += event.delta.partial_json

    if is_tool_call and tool_input_json:
        design = _build_design(json.loads(tool_input_json))
        store.write_json(session_id, "design.json", design)
        store.set_status(session_id, "DESIGNED")
        yield _sse({"type": "done", "is_complete": True, "study_design": design})
    else:
        if accumulated:
            history.append({"role": "assistant", "content": accumulated})
            store.write_json(session_id, "dialogue_history.json", history)
        yield _sse({"type": "done", "is_complete": False})


async def _stream_openai(session_id: str, history: list[dict[str, str]],  # type: ignore[return]
                         system: str) -> object:
    if IS_AZURE_OPENAI:
        from openai import AsyncAzureOpenAI
        client = AsyncAzureOpenAI(
            api_key=OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
    else:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

    tools = [{
        "type": "function",
        "function": {
            "name": TOOL_SCHEMA["name"],
            "description": TOOL_SCHEMA["description"],
            "parameters": {
                "type": "object",
                "properties": TOOL_SCHEMA["properties"],
                "required": TOOL_SCHEMA["required"],
            },
        },
    }]

    accumulated = ""
    tool_call_args = ""
    is_tool_call = False

    stream = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system}] + history,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
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
        design = _build_design(json.loads(tool_call_args))
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

    # Inject dataset columns so the LLM uses exact column names for measurable confounders.
    dataset_columns: list[str] = []
    if store.exists(session_id, "preview.json"):
        preview_meta = json.loads(store.read(session_id, "preview.json"))
        dataset_columns = preview_meta.get("columns", [])

    # Rule 8: inject BET subgroup hint into the system prompt when the profile shows
    # mixture-type nonlinear dependence (subtype_suggestive flag set by the profiler).
    subtype_suggestive = False
    if store.exists(session_id, "profile.json"):
        p = json.loads(store.read(session_id, "profile.json"))
        subtype_suggestive = bool((p.get("eda_summary") or {}).get("subtype_suggestive", False))

    system = _system_prompt(subtype_suggestive, dataset_columns)

    # Build message history from stored dialogue
    history_path = "dialogue_history.json"
    history: list[dict[str, str]] = []
    if store.exists(session_id, history_path):
        history = json.loads(store.read(session_id, history_path))  # type: ignore[assignment]

    if payload.user_message != "__init__":
        history.append({"role": "user", "content": payload.user_message})

    store.write_json(session_id, history_path, history)

    return StreamingResponse(
        _stream_live(session_id, history, system),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
