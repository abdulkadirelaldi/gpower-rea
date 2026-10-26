"""A third independent oracle: statsmodels.

SciPy (tests/test_reference_scipy.py) checks the engine against a reference we
wrote ourselves from SPEC.md -- it shares our *reading* of the specification.
statsmodels is different in kind: it is a power-analysis implementation written
by other people from the statistical literature, with no knowledge of this
project.  Agreement with it tests the reading, not just the arithmetic.

Three results are recorded here, and the second one corrects a plausible guess:

1. **statsmodels keeps the far-tail term** of the two-tailed power expression
   (SPEC F-02).  It would have been easy to assume a widely used library takes
   the textbook shortcut; measurement says it does not.  Candidate A of E-002
   is therefore the expression two independent implementations arrived at,
   which is much stronger evidence than one implementation plus an argument.

2. **statsmodels is an agreement oracle, not an accuracy oracle.**  Measured
   against an exact noncentral-t reference, its error reaches **7.2e-5** in the
   high-power regime -- it returns exactly `1.0` where the truth is
   `0.9999777...`.  The engine's worst error on the same grid is **1.2e-11**,
   six orders of magnitude better.  So broad agreement is asserted at 1e-4 and
   the accuracy oracle remains mpmath (tests/test_numerics.py).

3. Agreement holds for the balanced and unbalanced two-group designs and the
   one-sample design, in both tail counts -- the parts of the family
   statsmodels covers.

Skipped automatically when statsmodels is not installed; it is a test-only
dependency and the engine never imports it.
"""

from __future__ import annotations

import math

import pytest

sm_power = pytest.importorskip(
    "statsmodels.stats.power", reason="statsmodels not installed"
)
sp_stats = pytest.importorskip("scipy.stats", reason="scipy not installed")

from gpower_rea import numerics as nm  # noqa: E402
from gpower_rea import solve  # noqa: E402

#: statsmodels' own error against an exact noncentral t reaches 7.2e-5 as
#: power approaches 1 (measured; see the module docstring).  Agreement is
#: therefore checked at 1e-4, and never used to bound the engine's accuracy.
AGREEMENT_TOL = 1e-4

#: What the engine itself must achieve against an exact reference.
ENGINE_TOL = 1e-10

_indep = sm_power.TTestIndPower()
_one = sm_power.TTestPower()


def _exact_power(df: float, ncp: float, alpha: float, tails: int) -> float:
    """SPEC F-02 evaluated with SciPy -- the arbiter for this module."""
    if tails == 1:
        tc = sp_stats.t.ppf(1.0 - alpha, df)
        return float(1.0 - sp_stats.nct.cdf(tc, df, ncp))
    tc = sp_stats.t.ppf(1.0 - alpha / 2.0, df)
    return float(
        1.0 - sp_stats.nct.cdf(tc, df, ncp) + sp_stats.nct.cdf(-tc, df, ncp)
    )


# --------------------------------------------------------------------------
# 1. F-02: statsmodels keeps the far-tail term
# --------------------------------------------------------------------------
@pytest.mark.parametrize("alpha", [0.05, 0.10, 0.20])
@pytest.mark.parametrize("n", [11, 31, 101])
def test_statsmodels_also_keeps_the_far_tail(alpha, n):
    """At the null a two-sided test has size alpha -- not alpha/2.

    This is the E-002 discriminator applied to statsmodels rather than to the
    GUI.  A library that dropped the term would return alpha/2 here.
    """
    theirs = float(
        _one.power(effect_size=1e-12, nobs=n, alpha=alpha, alternative="two-sided")
    )
    assert theirs == pytest.approx(alpha, abs=1e-7)
    assert theirs != pytest.approx(alpha / 2.0, abs=1e-4)

    mine = solve(
        "ttest-generic", "power", alpha=alpha, effect_size=1e-12, tails=2,
        extra={"df": n - 1},
    ).power
    assert mine == pytest.approx(theirs, abs=1e-7)


def test_the_far_tail_is_large_enough_to_be_decisive_at_small_effects():
    """Where the term is big, agreement cannot be a coincidence.

    At d = 0.05 with n = 100 per group the far-tail term is ~1.0e-2 -- ten
    orders of magnitude above the two libraries' disagreement at that point.
    An implementation that dropped it would differ visibly.
    """
    mine = solve("ttest-indep-means", "power", alpha=0.05, effect_size=0.05,
                 tails=2, n1=100, n2=100)
    far = nm.nct_cdf(-mine.critical_t, mine.df, mine.noncentrality)
    assert far > 1e-2, "probe no longer discriminates; pick a smaller d"

    theirs = float(
        _indep.power(effect_size=0.05, nobs1=100, alpha=0.05, ratio=1.0,
                     alternative="two-sided")
    )
    assert mine.power == pytest.approx(theirs, abs=1e-9)
    # The truncated formula is nowhere near either of us.
    assert abs((mine.power - far) - theirs) > 1e-3


# --------------------------------------------------------------------------
# 2. Agreement across the designs statsmodels covers
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tails,alt", [(2, "two-sided"), (1, "larger")])
def test_two_group_power_agrees(tails, alt):
    worst = 0.0
    for d in (0.05, 0.2, 0.35, 0.5, 0.8, 1.2):
        for n in (6, 13, 26, 64, 105, 394):
            mine = solve("ttest-indep-means", "power", alpha=0.05,
                         effect_size=d, tails=tails, n1=n, n2=n).power
            theirs = float(
                _indep.power(effect_size=d, nobs1=n, alpha=0.05, ratio=1.0,
                             alternative=alt)
            )
            worst = max(worst, abs(mine - theirs))
    assert worst < AGREEMENT_TOL, f"worst deviation {worst:g}"


@pytest.mark.parametrize("tails,alt", [(2, "two-sided"), (1, "larger")])
def test_one_sample_power_agrees(tails, alt):
    worst = 0.0
    for d in (0.05, 0.2, 0.35, 0.5, 1.0):
        for n in (5, 15, 54, 120, 300):
            mine = solve("ttest-one-sample", "power", alpha=0.05,
                         effect_size=d, tails=tails, n=n).power
            theirs = float(
                _one.power(effect_size=d, nobs=n, alpha=0.05, alternative=alt)
            )
            worst = max(worst, abs(mine - theirs))
    assert worst < AGREEMENT_TOL, f"worst deviation {worst:g}"


def test_unbalanced_two_group_power_agrees():
    """statsmodels parameterises the allocation as nobs1 + ratio, like F-05."""
    worst = 0.0
    for d in (0.3, 0.5, 0.8):
        for n1 in (20, 45, 90):
            for ratio in (0.5, 1.5, 2.0, 3.0):
                n2 = int(round(ratio * n1))
                mine = solve("ttest-indep-means", "power", alpha=0.05,
                             effect_size=d, tails=2, n1=n1, n2=n2).power
                theirs = float(
                    _indep.power(effect_size=d, nobs1=n1, alpha=0.05,
                                 ratio=n2 / n1, alternative="two-sided")
                )
                worst = max(worst, abs(mine - theirs))
    assert worst < AGREEMENT_TOL, f"worst deviation {worst:g}"


# --------------------------------------------------------------------------
# 3. Who is right where they disagree
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tails", [1, 2])
def test_engine_is_far_more_accurate_than_statsmodels(tails):
    """Both are compared with an exact reference on the same grid.

    Measured worst deviations from exact, recorded in docs/VALIDATION.md:

        engine       9.2e-12  (two-group)   1.2e-11  (one sample)
        statsmodels  1.8e-05  (two-group)   7.2e-05  (one sample)

    statsmodels loses precision as power approaches 1, where it can return
    exactly 1.0; the engine's mixture-representation quadrature does not.
    """
    worst_mine = worst_theirs = 0.0
    for d in (0.05, 0.2, 0.35, 0.5, 0.8, 1.2):
        for n in (6, 13, 26, 64, 105, 394):
            ncp = d * math.sqrt(n / 2.0)
            df = 2.0 * n - 2.0
            ref = _exact_power(df, ncp, 0.05, tails)
            mine = solve("ttest-indep-means", "power", alpha=0.05,
                         effect_size=d, tails=tails, n1=n, n2=n).power
            theirs = float(
                _indep.power(effect_size=d, nobs1=n, alpha=0.05, ratio=1.0,
                             alternative="two-sided" if tails == 2 else "larger")
            )
            worst_mine = max(worst_mine, abs(mine - ref))
            worst_theirs = max(worst_theirs, abs(theirs - ref))
    assert worst_mine < ENGINE_TOL, f"engine error {worst_mine:g}"
    assert worst_mine < worst_theirs, (
        f"engine {worst_mine:g} vs statsmodels {worst_theirs:g}"
    )


def test_statsmodels_saturates_to_one_where_the_engine_does_not():
    """A concrete instance of the accuracy gap, pinned so it cannot silently
    change the meaning of the agreement tolerance above."""
    mine = solve("ttest-one-sample", "power", alpha=0.05, effect_size=0.35,
                 tails=2, n=300).power
    theirs = float(
        _one.power(effect_size=0.35, nobs=300, alpha=0.05,
                   alternative="two-sided")
    )
    ref = _exact_power(299.0, 0.35 * math.sqrt(300.0), 0.05, 2)
    assert theirs == 1.0, "statsmodels no longer saturates; re-tune this test"
    assert ref < 1.0
    assert abs(mine - ref) < 1e-10
    assert abs(theirs - ref) > 1e-5


# --------------------------------------------------------------------------
# Sample size: statsmodels solves a continuous nobs
# --------------------------------------------------------------------------
@pytest.mark.parametrize("d", [0.2, 0.35, 0.5, 0.8])
@pytest.mark.parametrize("target", [0.80, 0.90, 0.95])
def test_required_n_brackets_the_continuous_solution(d, target):
    """statsmodels returns a fractional per-group n; ours is the next integer
    up on the F-05 grid.  So ours must satisfy  sm_n <= ours < sm_n + 1."""
    sm_n = float(
        _indep.solve_power(effect_size=d, power=target, alpha=0.05, ratio=1.0,
                           alternative="two-sided")
    )
    ours = solve("ttest-indep-means", "n", alpha=0.05, power_target=target,
                 effect_size=d, tails=2).sample_size["n1"]
    assert sm_n - 1e-6 <= ours < sm_n + 1.0, (
        f"d={d} target={target}: statsmodels {sm_n:.6f}, ours {ours}"
    )
