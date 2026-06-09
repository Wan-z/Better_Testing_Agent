"""Backward-compatible facade over the canonical engine (``hta.modules``).

The profiler and selector that used to live here have moved into the engine so there is
a single source of truth shared by the playground, the web backend, and the CLI:

  * variable-type inference + normality severity → ``hta.modules.profiler``
  * the deterministic §6.2 test selector (+ the real BET dependence test) → ``hta.modules.selector``

Both engine modules are pure standard library at import time (their pandas/scipy paths are
deferred to call time), so ``python playground/app.py`` still runs with no numpy/scipy/
pydantic/fastapi. This module simply re-exports the public names the playground and the
web backend already import (``profile_column``, ``select``, ``Selection``, ``Column``, …).
"""

from __future__ import annotations

from hta.modules.profiler import (
    Column,
    _moments,
    _to_float,
    profile_column,
    severity,
)
from hta.modules.selector import (
    LARGE_N,
    Selection,
    prefer_rank_based,
    select,
)

__all__ = [
    "Column",
    "Selection",
    "LARGE_N",
    "profile_column",
    "severity",
    "prefer_rank_based",
    "select",
    "_to_float",
    "_moments",
]
