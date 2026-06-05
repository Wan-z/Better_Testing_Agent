"""Tests for the playground demo pipeline (playground/pipeline.py).

Loaded by path so the test doesn't depend on `playground` being importable as a
package under the test's sys.path. Pure standard library.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_PIPELINE = Path(__file__).resolve().parents[1] / "playground" / "pipeline.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pg_pipeline", _PIPELINE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # @dataclass needs the module registered first
    spec.loader.exec_module(mod)
    return mod


P = _load()


def _cols(raw: dict[str, list[str]]) -> dict:
    return {h: P.profile_column(h, raw[h]) for h in raw}


def test_profile_infers_types() -> None:
    raw = {
        "id": [str(i) for i in range(20)],
        "cont": [f"{i * 0.7 + 0.1:.2f}" for i in range(20)],
        "bin": (["yes"] * 10) + (["no"] * 10),
        "grade": [str(i % 5 + 1) for i in range(20)],
    }
    cols = _cols(raw)
    assert cols["id"].var_type == "IDENTIFIER"
    assert cols["cont"].var_type == "CONTINUOUS"
    assert cols["bin"].var_type == "BINARY"
    assert cols["grade"].var_type == "ORDINAL"


def test_severity_grading() -> None:
    assert P.severity(0.2, 0.5) == "NONE"
    assert P.severity(1.4, 0.0) == "MILD"
    assert P.severity(2.5, 0.0) == "STRONG"
    assert P.severity(0.0, 8.0) == "STRONG"


def test_prefer_rank_based_clt_and_ordinal() -> None:
    assert P.prefer_rank_based("ORDINAL", 5, "NONE") is True          # scale of measurement
    assert P.prefer_rank_based("CONTINUOUS", 50, "STRONG") is False   # CLT overrides
    assert P.prefer_rank_based("CONTINUOUS", 10, "STRONG") is True
    assert P.prefer_rank_based("CONTINUOUS", 10, "MILD") is False


def test_select_welch_for_two_group_normal() -> None:
    # Continuous (float, many unique values) outcome, two near-normal groups → Welch by
    # default (no variance pretest). Per-group normality, not the pooled bimodal shape.
    a = [10.2, 11.4, 9.1, 12.3, 10.8, 11.0, 13.1, 9.6, 10.5, 12.0]
    b = [20.2, 21.4, 19.1, 22.3, 20.8, 21.0, 23.1, 19.6, 20.5, 22.0]
    raw = {
        "y": [f"{v:.2f}" for v in a + b],
        "arm": (["A"] * 10) + (["B"] * 10),
    }
    cols = _cols(raw)
    assert cols["y"].var_type == "CONTINUOUS"
    sel = P.select(cols, "y", "arm", None, "does y differ between arms?", raw)
    assert sel.test == "WELCH_T"


def test_select_maxbet_for_nonlinear_association() -> None:
    # A parabola y = x² over x ∈ [−1, 1]: strong dependence, ~zero correlation — the
    # depth-2 screen's canonical nonlinear-only case (mirrors the §6.2 BET path).
    n = 200
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    raw = {
        "x": [f"{x:.4f}" for x in xs],
        "y": [f"{x * x:.4f}" for x in xs],
    }
    cols = _cols(raw)
    sel = P.select(cols, "y", None, "x", "is y associated with x?", raw)
    assert sel.test == "MAXBET"
    assert "BET" in sel.computed
    assert sel.region                       # a dependence region was localized
