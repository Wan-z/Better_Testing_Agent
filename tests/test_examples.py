"""Regression tests for the two Zhang (2019) worked examples under examples/.

These pin the qualitative findings the demos are meant to reproduce, so the
synthetic generators and the BET engine stay in agreement with the paper's story.
Pure standard library; the example modules are loaded by path (examples/ is not a
package) and only their pure functions are exercised — no file IO.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from hta.bet_screen import LINEAR_NULL_THRESHOLD, maxbet, maxbet_twostage

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _EXAMPLES / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stars_independence_detected_but_not_by_correlation() -> None:
    stars = _load("stars_independence")
    rows = stars.generate()
    assert len(rows) == stars.N_STARS
    lon = [r[0] for r in rows]
    sin_lat = [r[1] for r in rows]
    res = maxbet_twostage(lon, sin_lat, seed=7)
    # Linear tests are weak (the paper's r = -0.07), BET rejects, and it localizes
    # the dependence to a region (the band).
    assert abs(res.pearson_r) < LINEAR_NULL_THRESHOLD
    assert res.significant
    assert res.positive_region
    assert res.region_description


def test_gene_pair_nonlinear_and_joint_beats_marginals() -> None:
    genes = _load("gene_pair_subtype")
    rows = genes.generate()
    dzip1 = [r[0] for r in rows]
    nav3 = [r[1] for r in rows]
    subtype = [r[2] for r in rows]

    res = maxbet(dzip1, nav3, seed=11)
    assert res.significant                                   # BET flags the pair
    assert res.form in ("PARABOLIC", "SINUSOIDAL", "CHECKERBOARD", "COMPLEX")

    # §8.3: the BET-discovered pair classifies the subtype better *together* than
    # either gene alone.
    acc_dzip1 = genes.knn_loo_accuracy([[d] for d in dzip1], subtype)
    acc_nav3 = genes.knn_loo_accuracy([[v] for v in nav3], subtype)
    acc_joint = genes.knn_loo_accuracy([[d, v] for d, v in zip(dzip1, nav3)], subtype)
    assert acc_joint > acc_dzip1
    assert acc_joint > acc_nav3
    assert acc_joint > 0.85
