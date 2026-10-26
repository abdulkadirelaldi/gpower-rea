"""How often the two allocation grids of F-09 actually disagree.

SPEC F-09 and docs/EVIDENCE/E-009 quote measured disagreement rates.  Quoted
figures rot, so they are asserted here: if the rates move, these tests fail and
whoever changed the engine has to update the specification deliberately rather
than leave a stale number in a document that is meant to be evidence.

Needs no third-party package -- both candidate rules are implemented in the
engine and selectable, which is the whole point of F-09 being `REA-OPEN`.
"""

from __future__ import annotations

from collections import Counter

import pytest

from gpower_rea import solve
from gpower_rea.engine import _round_half_up

RATIOS = (0.5, 1.5, 2.0, 2.5, 3.0, 4.0)
TARGETS = (0.80, 0.90, 0.95)
EFFECT_SIZES = tuple(i / 100 for i in range(20, 121, 5))

#: Rates quoted in SPEC F-09, as (ratio -> percentage), tolerance +/- 4 points.
EXPECTED_RATES = {
    0.5: 12.7,
    1.5: 76.2,
    2.0: 88.9,
    2.5: 90.5,
    3.0: 90.5,
    4.0: 95.2,
}
EXPECTED_OVERALL = 75.7


@pytest.fixture(scope="module")
def sweep():
    differ: Counter = Counter()
    total: Counter = Counter()
    gaps: Counter = Counter()
    for ratio in RATIOS:
        for d in EFFECT_SIZES:
            for target in TARGETS:
                kw = dict(
                    alpha=0.05, power_target=target, effect_size=d, tails=2,
                    allocation_ratio=ratio,
                )
                a = solve("ttest-indep-means", "n", allocation_rule="n1-grid", **kw)
                b = solve("ttest-indep-means", "n", allocation_rule="total-grid", **kw)
                total[ratio] += 1
                gap = a.sample_size["total"] - b.sample_size["total"]
                gaps[gap] += 1
                if gap:
                    differ[ratio] += 1
                # Both rules must still deliver the requested power.
                assert a.power >= target
                assert b.power >= target
                # total-grid can never need more participants.
                assert b.sample_size["total"] <= a.sample_size["total"]
    return differ, total, gaps


def test_sweep_size_matches_the_documented_one(sweep):
    _, total, _ = sweep
    assert sum(total.values()) == 378, (
        "the sweep changed size; the rates quoted in SPEC F-09 are for 378 "
        "settings"
    )


@pytest.mark.parametrize("ratio", RATIOS)
def test_per_ratio_disagreement_rate(ratio, sweep):
    differ, total, _ = sweep
    rate = 100.0 * differ[ratio] / total[ratio]
    assert abs(rate - EXPECTED_RATES[ratio]) <= 4.0, (
        f"R={ratio}: measured {rate:.1f}%, SPEC F-09 says "
        f"{EXPECTED_RATES[ratio]}% -- update SPEC.md and E-009 if this moved"
    )


def test_overall_disagreement_rate(sweep):
    differ, total, _ = sweep
    rate = 100.0 * sum(differ.values()) / sum(total.values())
    assert abs(rate - EXPECTED_OVERALL) <= 3.0, (
        f"measured {rate:.1f}%, SPEC F-09 says {EXPECTED_OVERALL}%"
    )


def test_disagreement_is_small_but_never_zero_everywhere(sweep):
    """The gap is 1-3 participants: large enough to matter, small enough to be
    mistaken for a rounding bug.  That combination is what makes F-09 worth a
    finding of its own."""
    _, _, gaps = sweep
    assert set(gaps) <= {0, 1, 2, 3}, f"unexpected gap sizes: {sorted(gaps)}"
    assert gaps[0] > 0, "the two rules should coincide somewhere"
    assert sum(v for k, v in gaps.items() if k) > 0


def test_integer_ratios_give_an_exact_realised_ratio_under_n1_grid():
    """E-009's cheapest single observation, across the whole sweep.

    Where `R` is an integer, `n1-grid` reproduces it to every digit and
    `total-grid` never does.  Half-integer ratios are excluded: `R*n1` lands
    on a half-integer for odd `n1`, so neither rule can be exact there.
    """
    for ratio in (2.0, 3.0, 4.0):
        for d in (0.20, 0.35, 0.50, 0.80):
            for target in TARGETS:
                kw = dict(
                    alpha=0.05, power_target=target, effect_size=d, tails=2,
                    allocation_ratio=ratio,
                )
                a = solve("ttest-indep-means", "n", allocation_rule="n1-grid", **kw)
                n1, n2 = a.sample_size["n1"], a.sample_size["n2"]
                assert n2 == _round_half_up(ratio * n1)
                assert n2 / n1 == pytest.approx(ratio, abs=1e-12)


def test_round_half_up_is_not_bankers_rounding():
    """F-09's second, independent choice: halves go away from zero."""
    assert _round_half_up(2.5) == 3
    assert _round_half_up(3.5) == 4
    assert _round_half_up(0.5) == 1
    assert _round_half_up(-2.5) == -3
    # Python's built-in disagrees on every one of those.
    assert round(2.5) == 2
    assert round(0.5) == 0


def test_the_rule_in_force_is_always_reported():
    """An REA-OPEN choice must never be silent (SPEC section 2, F-09)."""
    for rule in ("n1-grid", "total-grid"):
        res = solve(
            "ttest-indep-means", "n", alpha=0.05, power_target=0.9,
            effect_size=0.5, tails=2, allocation_ratio=2.0,
            allocation_rule=rule,
        )
        assert res.engine["allocation_rule"] == rule
        assert res.sample_size["allocation_ratio"] == 2.0
        assert res.sample_size["actual_ratio"] == pytest.approx(
            res.sample_size["n2"] / res.sample_size["n1"]
        )
