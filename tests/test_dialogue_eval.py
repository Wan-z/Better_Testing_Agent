"""
Study Design dialogue evaluation — two levels.

Level 1 — fast, no API, runs in normal ``pytest``:
  Tests ``_build_design()`` directly to verify the tool-arg → StudyDesign
  mapping is correct.

Level 2 — ``@pytest.mark.slow``, requires a live LLM:
  Scripted dialogue eval. A "user agent" provides a one-shot statement with
  all design facts; the LLM should call ``capture_study_design`` within
  MAX_TURNS turns. Auto-skips when no API key is configured.

  Run with:
      pytest tests/test_dialogue_eval.py -v -m slow
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

# Make the engine and web packages importable.
_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from web.backend.api.dialogue import _build_design, _system_prompt, TOOL_SCHEMA  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────────────────

MAX_TURNS = 6  # max conversation turns before the test fails


def _has_anthropic_key() -> bool:
    from web.backend.config import ANTHROPIC_API_KEY, LLM_PROVIDER
    return LLM_PROVIDER == "anthropic" and bool(ANTHROPIC_API_KEY)


def _has_openai_key() -> bool:
    from web.backend.config import OPENAI_API_KEY, LLM_PROVIDER
    return LLM_PROVIDER in ("openai", "azure_openai") and bool(OPENAI_API_KEY)


def _has_any_key() -> bool:
    return _has_anthropic_key() or _has_openai_key()


# ── Level 1: _build_design unit tests ─────────────────────────────────────────

class TestBuildDesign:
    """_build_design() converts raw tool-call args into a StudyDesign dict."""

    def test_minimal_args(self) -> None:
        d = _build_design({
            "design_type": "OBSERVATIONAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": False,
        })
        assert d["design_type"] == "OBSERVATIONAL"
        assert d["measurement_type"] == "BETWEEN_SUBJECTS"
        assert d["is_randomized"] is False
        assert d["confounders"] == []
        assert d["notes"] == []

    def test_rct_args(self) -> None:
        d = _build_design({
            "design_type": "EXPERIMENTAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": True,
            "relationship_form": "linear",
        })
        assert d["design_type"] == "EXPERIMENTAL"
        assert d["is_randomized"] is True
        # "linear" should NOT appear in notes (it is the default/expected form)
        assert "linear" not in d["notes"]

    def test_nonlinear_form_appended_to_notes(self) -> None:
        d = _build_design({
            "design_type": "OBSERVATIONAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": False,
            "relationship_form": "nonlinear",
        })
        assert "nonlinear" in d["notes"]

    def test_monotone_form_appended_to_notes(self) -> None:
        d = _build_design({
            "design_type": "OBSERVATIONAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": False,
            "relationship_form": "monotone",
        })
        assert "monotone" in d["notes"]

    def test_confounders_mapped(self) -> None:
        d = _build_design({
            "design_type": "OBSERVATIONAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": False,
            "confounder_names": ["age", "sex"],
        })
        names = [c["name"] for c in d["confounders"]]
        assert "age" in names
        assert "sex" in names
        assert all(c["role"] == "CONFOUNDER" for c in d["confounders"])
        assert all(c["is_measured"] is True for c in d["confounders"])

    def test_subgroup_flag_in_notes(self) -> None:
        d = _build_design({
            "design_type": "OBSERVATIONAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": False,
            "subgroup_structure_suspected": True,
        })
        assert "subgroup_structure_suspected" in d["notes"]

    def test_unknown_form_not_in_notes(self) -> None:
        d = _build_design({
            "design_type": "OBSERVATIONAL",
            "measurement_type": "BETWEEN_SUBJECTS",
            "is_randomized": False,
            "relationship_form": "unknown",
        })
        assert d["notes"] == []

    def test_quasi_experimental(self) -> None:
        d = _build_design({
            "design_type": "QUASI_EXPERIMENTAL",
            "measurement_type": "MIXED",
            "is_randomized": False,
        })
        assert d["design_type"] == "QUASI_EXPERIMENTAL"
        assert d["measurement_type"] == "MIXED"


# ── Level 2: scripted LLM eval ────────────────────────────────────────────────

@dataclass
class Scenario:
    """A research scenario for the dialogue eval harness."""
    name: str
    description: str
    # Context the user provides in the init message (appended after variable info)
    dataset_context: str
    # Compact statement covering all design facts — the user agent sends this
    # each turn until the LLM calls the tool.
    user_statement: str
    # Expected StudyDesign field values. None means "don't assert".
    expected_design_type: Optional[str] = None
    # Single value or a set of acceptable values (e.g. panel data accepts
    # both WITHIN_SUBJECTS and MIXED — both are technically defensible).
    expected_measurement_type: Optional[str] = None
    expected_measurement_type_any: list[str] = field(default_factory=list)
    expected_is_randomized: Optional[bool] = None
    expected_confounder_names: list[str] = field(default_factory=list)
    # If True, the scenario is ambiguous; we only check convergence (tool called).
    convergence_only: bool = False
    subtype_suggestive: bool = False


SCENARIOS: list[Scenario] = [
    Scenario(
        name="rct_clinical",
        description="Classic randomised controlled trial",
        dataset_context=(
            "My primary outcome variable is: pain_score.\n"
            "My predictor variable is: treatment_group.\n"
            "My research hypothesis is: Drug A reduces pain score compared to placebo.\n"
            "Do not ask me which variables I am studying — I have already specified them above."
        ),
        user_statement=(
            "This was a double-blind randomised controlled trial. "
            "I randomly assigned 60 patients to either Drug A or placebo. "
            "Each patient was measured once after 4 weeks — observations are independent. "
            "There are no known confounders because randomisation balanced the groups. "
            "I expect a linear reduction in pain score."
        ),
        expected_design_type="EXPERIMENTAL",
        expected_measurement_type="BETWEEN_SUBJECTS",
        expected_is_randomized=True,
    ),
    Scenario(
        name="observational_crosssectional",
        description="Observational cross-sectional survey",
        dataset_context=(
            "My primary outcome variable is: self_rated_health.\n"
            "My predictor variable is: income_level.\n"
            "My research hypothesis is: Higher income is associated with better self-rated health.\n"
            "Do not ask me which variables I am studying — I have already specified them above."
        ),
        user_statement=(
            "This is an observational cross-sectional study. "
            "I collected survey data from 500 adults in 2023 — each person appears once. "
            "There was no intervention or randomisation. "
            "Age and education level are likely confounders. "
            "I expect a monotone (not necessarily linear) association."
        ),
        expected_design_type="OBSERVATIONAL",
        expected_measurement_type="BETWEEN_SUBJECTS",
        expected_is_randomized=False,
        expected_confounder_names=["age"],
    ),
    Scenario(
        name="longitudinal_panel",
        description="Longitudinal panel / repeated-measures study",
        dataset_context=(
            "My primary outcome variable is: unemployment_rate.\n"
            "My predictor variable is: policy_index.\n"
            "My research hypothesis is: Higher policy index is associated with lower "
            "unemployment rate over time.\n"
            "Do not ask me which variables I am studying — I have already specified them above."
        ),
        user_statement=(
            "This is an observational longitudinal study — no intervention, no randomisation. "
            "I have quarterly data for 50 states measured over 10 years. "
            "The SAME states are observed repeatedly — each state contributes many rows, "
            "so observations are NOT independent (repeated/panel structure). "
            "GDP and population density are potential confounders. "
            "I expect a monotone relationship between policy_index and unemployment_rate."
        ),
        expected_design_type="OBSERVATIONAL",
        # Both WITHIN_SUBJECTS and MIXED are defensible for state-year panel data.
        expected_measurement_type_any=["WITHIN_SUBJECTS", "MIXED"],
        expected_is_randomized=False,
    ),
    Scenario(
        name="quasi_experimental",
        description="Natural experiment / difference-in-differences",
        dataset_context=(
            "My primary outcome variable is: opioid_overdose_rate.\n"
            "My predictor variable is: naloxone_law.\n"
            "My research hypothesis is: Naloxone access laws reduce opioid overdose rates.\n"
            "Do not ask me which variables I am studying — I have already specified them above."
        ),
        user_statement=(
            "This is a quasi-experimental study using a natural experiment. "
            "Some states adopted naloxone access laws and some did not — "
            "there was no randomisation, but the policy change acts like an exogenous shock. "
            "I have state-year panel data (same states observed before and after). "
            "Income and urbanisation are potential confounders. "
            "I expect a monotone relationship."
        ),
        expected_design_type="QUASI_EXPERIMENTAL",
        expected_is_randomized=False,
    ),
    Scenario(
        name="ambiguous_vague",
        description="Vague researcher — only checks the LLM converges",
        dataset_context=(
            "My primary outcome variable is: score.\n"
            "My research hypothesis is: Score varies by group.\n"
            "Do not ask me which variables I am studying — I have already specified them above."
        ),
        user_statement=(
            "I'm not very sure — I just collected some data and want to compare groups. "
            "I think each person appears once. "
            "I didn't assign groups myself. "
            "I don't know about confounders."
        ),
        convergence_only=True,
    ),
]


def _run_scenario_anthropic(
    scenario: Scenario,
) -> tuple[Optional[dict], list[str]]:  # type: ignore[type-arg]
    """Run one scenario against the Anthropic API.
    Returns (captured_design_or_None, conversation_log)."""
    import anthropic
    from web.backend.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)
    system = _system_prompt(
        subtype_suggestive=scenario.subtype_suggestive,
        dataset_columns=None,
    )
    tools: list[anthropic.types.ToolParam] = [{
        "name": TOOL_SCHEMA["name"],
        "description": TOOL_SCHEMA["description"],
        "input_schema": {
            "type": "object",
            "properties": TOOL_SCHEMA["properties"],
            "required": TOOL_SCHEMA["required"],
        },
    }]

    init = (
        "I have uploaded my dataset and selected my variables.\n"
        + scenario.dataset_context
        + "\nPlease interview me about the study design."
    )
    history: list[dict] = [{"role": "user", "content": init}]
    log: list[str] = [f"[USER init]\n{init}"]

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            system=system,
            messages=history,  # type: ignore[arg-type]
            tools=tools,
            max_tokens=512,
        )
        # Check for tool call
        for block in response.content:
            if block.type == "tool_use" and block.name == TOOL_SCHEMA["name"]:
                log.append(f"[TOOL CALL turn {turn + 1}] {block.input}")
                return _build_design(block.input), log  # type: ignore[arg-type]
        # Extract text and continue
        text = " ".join(
            b.text for b in response.content if b.type == "text" and b.text
        )
        if not text:
            log.append(f"[ASSISTANT turn {turn + 1}] (empty response)")
            break
        log.append(f"[ASSISTANT turn {turn + 1}]\n{text}")
        history.append({"role": "assistant", "content": text})
        history.append({"role": "user", "content": scenario.user_statement})
        log.append(f"[USER turn {turn + 1}]\n{scenario.user_statement}")

    return None, log


def _run_scenario_openai(
    scenario: Scenario,
) -> tuple[Optional[dict], list[str]]:  # type: ignore[type-arg]
    """Run one scenario against OpenAI / Azure OpenAI.
    Returns (captured_design_or_None, conversation_log)."""
    import json as _json
    from web.backend.config import (
        OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
        AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, IS_AZURE_OPENAI,
    )
    if IS_AZURE_OPENAI:
        from openai import AzureOpenAI
        client = AzureOpenAI(  # type: ignore[assignment]
            api_key=OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            timeout=60.0,
        )
    else:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=60.0)  # type: ignore[assignment]

    system = _system_prompt(subtype_suggestive=scenario.subtype_suggestive)
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

    init = (
        "I have uploaded my dataset and selected my variables.\n"
        + scenario.dataset_context
        + "\nPlease interview me about the study design."
    )
    history: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": init},
    ]
    log: list[str] = [f"[USER init]\n{init}"]

    for turn in range(MAX_TURNS):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=history,  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            max_completion_tokens=512,
        )
        msg = response.choices[0].message
        if msg.tool_calls:
            args = _json.loads(msg.tool_calls[0].function.arguments)
            log.append(f"[TOOL CALL turn {turn + 1}] {args}")
            return _build_design(args), log
        text = msg.content or ""
        if not text:
            log.append(f"[ASSISTANT turn {turn + 1}] (empty response)")
            break
        log.append(f"[ASSISTANT turn {turn + 1}]\n{text}")
        history.append({"role": "assistant", "content": text})
        history.append({"role": "user", "content": scenario.user_statement})
        log.append(f"[USER turn {turn + 1}]\n{scenario.user_statement}")

    return None, log


def _run_scenario(scenario: Scenario) -> tuple[Optional[dict], list[str]]:  # type: ignore[type-arg]
    if _has_anthropic_key():
        return _run_scenario_anthropic(scenario)
    return _run_scenario_openai(scenario)


def _assert_design(design: dict, scenario: Scenario) -> None:  # type: ignore[type-arg]
    if scenario.convergence_only:
        return
    if scenario.expected_design_type is not None:
        assert design["design_type"] == scenario.expected_design_type, (
            f"{scenario.name}: expected design_type={scenario.expected_design_type}, "
            f"got {design['design_type']}"
        )
    if scenario.expected_measurement_type is not None:
        assert design["measurement_type"] == scenario.expected_measurement_type, (
            f"{scenario.name}: expected measurement_type={scenario.expected_measurement_type}, "
            f"got {design['measurement_type']}"
        )
    if scenario.expected_measurement_type_any:
        assert design["measurement_type"] in scenario.expected_measurement_type_any, (
            f"{scenario.name}: expected measurement_type in "
            f"{scenario.expected_measurement_type_any}, got {design['measurement_type']}"
        )
    if scenario.expected_is_randomized is not None:
        assert design["is_randomized"] == scenario.expected_is_randomized, (
            f"{scenario.name}: expected is_randomized={scenario.expected_is_randomized}, "
            f"got {design['is_randomized']}"
        )
    if scenario.expected_confounder_names:
        captured_names = {c["name"] for c in design.get("confounders", [])}
        for name in scenario.expected_confounder_names:
            assert name in captured_names, (
                f"{scenario.name}: expected confounder '{name}' not found "
                f"in captured set {captured_names}"
            )


@pytest.mark.slow
@pytest.mark.skipif(not _has_any_key(), reason="No LLM API key configured")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_dialogue_captures_design(scenario: Scenario) -> None:
    """The LLM must call capture_study_design with correct field values
    within MAX_TURNS turns given a researcher's one-shot design statement."""
    design, log = _run_scenario(scenario)
    conversation = "\n".join(log)

    assert design is not None, (
        f"Scenario '{scenario.name}': LLM did not call capture_study_design "
        f"within {MAX_TURNS} turns.\n\nConversation transcript:\n{conversation}"
    )
    _assert_design(design, scenario)
