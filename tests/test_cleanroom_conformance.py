"""The clean-room implementation is held to the same contract as the engine.

Session B (docs/CLEANROOM-PROTOCOL.md) produced `cleanroom/src/gpower_cleanroom`
from SPEC.md alone.  This file runs it through the same 401 conformance vectors
and the same SPEC properties as the shipped engine, so the two-session claim is
a test rather than a sentence.

Skipped automatically when the clean-room package is absent, which keeps the
main suite runnable for anyone who has not performed the second session.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEANROOM_SRC = ROOT / "cleanroom" / "src"

if CLEANROOM_SRC.is_dir() and str(CLEANROOM_SRC) not in sys.path:
    sys.path.insert(0, str(CLEANROOM_SRC))

cr = pytest.importorskip(
    "gpower_cleanroom",
    reason="no clean-room implementation present (see docs/CLEANROOM-PROTOCOL.md)",
)

sys.path.insert(0, str(ROOT / "tools"))
from judge_cleanroom import (  # noqa: E402
    check_divergence_against_shipped,
    check_gpower_observations,
    check_identities,
    check_round_trips,
    check_vectors,
    similarity,
)


@pytest.fixture(scope="module")
def vectors():
    return check_vectors(cr)


def test_public_surface_is_complete():
    for name in (
        "required_sample_size",
        "achieved_power",
        "required_alpha",
        "detectable_effect_size",
        "compromise",
        "TESTS",
    ):
        assert hasattr(cr, name), f"missing public name {name}"
    assert len(cr.TESTS) == 6


def test_no_third_party_imports():
    """SPEC-independent, but a hard requirement of the handover prompt."""
    banned = ("numpy", "scipy", "pandas", "mpmath", "statsmodels")
    for path in sorted((CLEANROOM_SRC / "gpower_cleanroom").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in banned:
            assert f"import {name}" not in text, f"{path.name} imports {name}"
            assert f"from {name}" not in text, f"{path.name} imports from {name}"


def test_conformance_vectors_exact(vectors):
    assert vectors["exact_n"] == vectors["rows"], (
        f"{vectors['exact_n']}/{vectors['rows']} exact; first divergences: "
        + "; ".join(vectors["errors"][:5])
    )


def test_conformance_powers_within_tolerance(vectors):
    assert vectors["power_within_tol"] == vectors["rows"]


@pytest.mark.parametrize(
    "index", range(9), ids=[
        "F-03 one-sample==paired",
        "F-04 pbs==two-group",
        "F-07 regression(p=1)==pbs",
        "F-02 two-sided size==alpha",
        "F-05 balanced total even",
        "F-09 even-total grid and observed split",
        "F-08 sign is a direction",
        "F-15 observed input domain",
        "F-06/F-12 minimality",
    ],
)
def test_spec_properties(index):
    label, ok, detail = check_identities(cr)[index]
    assert ok, f"{label}: {detail}"


@pytest.mark.parametrize("index", range(4), ids=[
    "a-priori->post-hoc",
    "criterion->post-hoc",
    "sensitivity->post-hoc",
    "compromise ratio",
])
def test_round_trips(index):
    label, ok, detail = check_round_trips(cr)[index]
    assert ok, f"{label}: {detail}"


def test_reproduces_the_real_gpower():
    """[GÖZLEM] The second implementation against every recorded a-priori
    G*Power 3.1.9.6 result (N <= 1e7) -- not against the first one."""
    obs = check_gpower_observations(cr)
    assert obs["rows"] >= 200
    assert obs["same"] == obs["rows"], (
        f"{obs['same']}/{obs['rows']} exact; first divergences: "
        + "; ".join(obs["diffs"][:5])
    )


def test_agrees_with_the_shipped_engine_on_a_wide_grid():
    div = check_divergence_against_shipped(cr)
    assert div["same"] == div["cases"], (
        f"{div['same']}/{div['cases']} agree; first divergences: "
        + "; ".join(div["diffs"][:5])
    )


def test_implementations_are_lexically_independent():
    """A clean-room pass should share domain vocabulary, not internals.

    Shared *private* helper names or verbatim comment lines would indicate the
    boundary leaked.  Domain nouns (alpha, power, noncentrality) are expected
    to overlap and are not evidence of anything.
    """
    sim = similarity()
    assert sim, "similarity report unavailable"
    assert sim["identical_comment_lines"] == [], (
        "verbatim comment lines shared with the shipped engine: "
        f"{sim['identical_comment_lines'][:3]}"
    )
    assert sim["jaccard"] < 0.60, (
        f"lexical overlap {sim['jaccard']:.3f} is implausibly high for an "
        "independent implementation"
    )
