"""Behavioural invariants of the engine.

These tests need no external oracle: they encode properties that any correct
implementation of SPEC.md must satisfy, so they stay meaningful even when
SciPy is unavailable (e.g. in a minimal CI container).
"""

from __future__ import annotations

import math

import pytest

from gpower_rea import (
    NoSolutionError,
    ValidationError,
    power,
    power_curve,
    solve,
)
from gpower_rea.engine import _round_half_up

SINGLE_GROUP = ["ttest-one-sample", "ttest-paired-means", "ttest-point-biserial"]
ALL_SOLVABLE = SINGLE_GROUP + ["ttest-indep-means", "ttest-regression-coef"]


def _extra(test):
    return {"predictors": 3} if test == "ttest-regression-coef" else None


def _es(test):
    return {"ttest-point-biserial": 0.3, "ttest-regression-coef": 0.15}.get(test, 0.5)


# --------------------------------------------------------------------------
# F-02: the two-tailed formula keeps the far-tail term
# --------------------------------------------------------------------------
@pytest.mark.parametrize("alpha", [0.001, 0.01, 0.05, 0.10, 0.20])
@pytest.mark.parametrize("df", [1, 5, 30, 208])
def test_two_tailed_power_at_null_equals_alpha(alpha, df):
    """At delta = 0 the size of a two-sided test is exactly alpha.

    A formula that drops the lower rejection region returns alpha/2 here.
    This is the cheapest discriminator between the two candidate formulas
    (SPEC F-02, evidence E-002).
    """
    got = solve(
        "ttest-generic",
        "power",
        alpha=alpha,
        effect_size=1e-12,
        tails=2,
        extra={"df": df},
    ).power
    assert got == pytest.approx(alpha, abs=1e-9)
    assert got != pytest.approx(alpha / 2, abs=1e-6)


@pytest.mark.parametrize("alpha", [0.01, 0.05])
@pytest.mark.parametrize("df", [3, 40])
def test_one_tailed_power_at_null_equals_alpha(alpha, df):
    got = solve(
        "ttest-generic",
        "power",
        alpha=alpha,
        effect_size=1e-12,
        tails=1,
        extra={"df": df},
    ).power
    assert got == pytest.approx(alpha, abs=1e-9)


# --------------------------------------------------------------------------
# Monotonicity
# --------------------------------------------------------------------------
@pytest.mark.parametrize("test", ALL_SOLVABLE)
def test_power_increases_with_sample_size(test):
    prev = -1.0
    for n in range(12, 160, 7):
        p = solve(
            test,
            "power",
            alpha=0.05,
            effect_size=_es(test),
            tails=2,
            n=n,
            extra=_extra(test),
        ).power
        assert p >= prev - 1e-12, f"{test}: power dropped at n={n}"
        prev = p


@pytest.mark.parametrize("test", ALL_SOLVABLE)
def test_power_increases_with_alpha(test):
    prev = -1.0
    for alpha in (0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.3):
        p = solve(
            test,
            "power",
            alpha=alpha,
            effect_size=_es(test),
            tails=2,
            n=60,
            extra=_extra(test),
        ).power
        assert p >= prev - 1e-12
        prev = p


@pytest.mark.parametrize("test", ALL_SOLVABLE)
def test_power_increases_with_effect_size(test):
    prev = -1.0
    base = _es(test)
    for mult in (0.1, 0.25, 0.5, 1.0, 1.5, 2.0):
        p = solve(
            test,
            "power",
            alpha=0.05,
            effect_size=base * mult,
            tails=2,
            n=60,
            extra=_extra(test),
        ).power
        assert p >= prev - 1e-12
        prev = p


@pytest.mark.parametrize("test", ALL_SOLVABLE)
def test_required_n_decreases_with_effect_size(test):
    prev = 10**9
    base = _es(test)
    for mult in (0.5, 0.75, 1.0, 1.5, 2.0):
        n = solve(
            test,
            "n",
            alpha=0.05,
            power_target=0.8,
            effect_size=base * mult,
            tails=2,
            extra=_extra(test),
        ).sample_size["total"]
        assert n <= prev
        prev = n


# --------------------------------------------------------------------------
# F-06: the a-priori answer really is the smallest sufficient design
# --------------------------------------------------------------------------
@pytest.mark.parametrize("test", ALL_SOLVABLE)
@pytest.mark.parametrize("target", [0.80, 0.90, 0.95])
@pytest.mark.parametrize("tails", [1, 2])
def test_apriori_is_minimal_and_sufficient(test, target, tails):
    """SPEC F-06 and F-12: the answer satisfies `power >= target` with no
    epsilon slack, and one step down on the search grid does not."""
    res = solve(
        test,
        "n",
        alpha=0.05,
        power_target=target,
        effect_size=_es(test),
        tails=tails,
        extra=_extra(test),
    )
    assert res.power >= target, "returned design misses the target"

    if test == "ttest-indep-means":
        n1 = res.sample_size["n1"]
        assert res.sample_size["n2"] == n1, "balanced design must be equal-n"
        smaller = solve(
            test,
            "power",
            alpha=0.05,
            effect_size=_es(test),
            tails=tails,
            n1=n1 - 1,
            n2=n1 - 1,
        ).power
    else:
        total = res.sample_size["total"]
        smaller = solve(
            test,
            "power",
            alpha=0.05,
            effect_size=_es(test),
            tails=tails,
            n=total - 1,
            extra=_extra(test),
        ).power
    assert smaller < target, "a smaller design would already have sufficed"


# --------------------------------------------------------------------------
# Round trips between the five analysis types
# --------------------------------------------------------------------------
@pytest.mark.parametrize("test", ALL_SOLVABLE)
def test_post_hoc_reproduces_a_priori_power(test):
    res = solve(
        test,
        "n",
        alpha=0.05,
        power_target=0.9,
        effect_size=_es(test),
        tails=2,
        extra=_extra(test),
    )
    if test == "ttest-indep-means":
        back = solve(
            test,
            "power",
            alpha=0.05,
            effect_size=_es(test),
            tails=2,
            n1=res.sample_size["n1"],
            n2=res.sample_size["n2"],
        )
    else:
        back = solve(
            test,
            "power",
            alpha=0.05,
            effect_size=_es(test),
            tails=2,
            n=res.sample_size["total"],
            extra=_extra(test),
        )
    assert back.power == pytest.approx(res.power, abs=1e-12)
    assert back.df == res.df
    assert back.noncentrality == pytest.approx(res.noncentrality, abs=1e-12)


@pytest.mark.parametrize("test", SINGLE_GROUP)
def test_criterion_round_trip(test):
    res = solve(
        test, "alpha", power_target=0.85, effect_size=_es(test), tails=2, n=50
    )
    back = solve(
        test, "power", alpha=res.alpha, effect_size=_es(test), tails=2, n=50
    )
    assert back.power == pytest.approx(0.85, abs=1e-9)


@pytest.mark.parametrize("test", SINGLE_GROUP)
def test_sensitivity_round_trip(test):
    res = solve(test, "effect-size", alpha=0.05, power_target=0.85, tails=2, n=50)
    back = solve(
        test,
        "power",
        alpha=0.05,
        effect_size=res.effect_size["value"],
        tails=2,
        n=50,
    )
    assert back.power == pytest.approx(0.85, abs=1e-9)


def test_compromise_honours_the_requested_ratio():
    """SPEC F-10: the solve target is the critical value, so beta/alpha == q
    must hold exactly and power must be the exact complement of beta."""
    for q in (0.5, 1.0, 2.0, 4.0):
        res = solve(
            "ttest-indep-means",
            "compromise",
            effect_size=0.5,
            tails=2,
            n1=40,
            n2=40,
            beta_alpha_ratio=q,
        )
        beta = res.target["beta"]
        assert beta / res.alpha == pytest.approx(q, rel=1e-7)
        assert res.power == pytest.approx(1.0 - beta, abs=1e-12)


# --------------------------------------------------------------------------
# Procedure consistency: the family must agree where it overlaps
# --------------------------------------------------------------------------
def test_one_sample_and_paired_agree():
    for d in (0.2, 0.5, 0.9):
        for tails in (1, 2):
            a = solve(
                "ttest-one-sample", "n", alpha=0.05, power_target=0.9,
                effect_size=d, tails=tails,
            ).sample_size["total"]
            b = solve(
                "ttest-paired-means", "n", alpha=0.05, power_target=0.9,
                effect_size=d, tails=tails,
            ).sample_size["total"]
            assert a == b


def test_regression_with_one_predictor_equals_point_biserial():
    """f2 = r^2/(1-r^2) with predictors=1 must reproduce the correlation test."""
    for r in (0.15, 0.3, 0.45):
        f2 = r * r / (1.0 - r * r)
        a = solve(
            "ttest-point-biserial", "n", alpha=0.05, power_target=0.9,
            effect_size=r, tails=2,
        )
        b = solve(
            "ttest-regression-coef", "n", alpha=0.05, power_target=0.9,
            effect_size=f2, tails=2, extra={"predictors": 1},
        )
        assert a.sample_size["total"] == b.sample_size["total"]
        assert a.df == b.df
        assert a.noncentrality == pytest.approx(b.noncentrality, rel=1e-12)


def test_point_biserial_matches_balanced_two_group():
    """With a 50/50 dichotomy, d = 2r/sqrt(1-r^2) and the two tests coincide."""
    for r in (0.2, 0.3, 0.4):
        d = 2.0 * r / math.sqrt(1.0 - r * r)
        n_total = 80
        a = solve(
            "ttest-point-biserial", "power", alpha=0.05, effect_size=r,
            tails=2, n=n_total,
        )
        b = solve(
            "ttest-indep-means", "power", alpha=0.05, effect_size=d,
            tails=2, n1=n_total // 2, n2=n_total // 2,
        )
        assert a.noncentrality == pytest.approx(b.noncentrality, rel=1e-12)
        assert a.power == pytest.approx(b.power, abs=1e-12)


# --------------------------------------------------------------------------
# F-05 / F-09: allocation grid and rounding
# --------------------------------------------------------------------------
def test_balanced_a_priori_never_returns_an_odd_total():
    for d in (0.2, 0.33, 0.5, 0.77, 1.1):
        for pw in (0.8, 0.9, 0.95):
            total = solve(
                "ttest-indep-means", "n", alpha=0.05, power_target=pw,
                effect_size=d, tails=2, allocation_ratio=1.0,
            ).sample_size["total"]
            assert total % 2 == 0, f"d={d} power={pw} gave odd N={total}"


@pytest.mark.parametrize("ratio", [0.5, 1.5, 2.0, 3.0, 4.0])
def test_n1_grid_rule_reproduces_the_ratio_exactly(ratio):
    """SPEC F-09: under `n1-grid`, n2 is round_half_up(ratio * n1) -- so the
    realised ratio is exact whenever ratio*n1 is an integer.  This exactness is
    the cheapest single signature that distinguishes the two candidate grids."""
    res = solve(
        "ttest-indep-means", "n", alpha=0.05, power_target=0.9,
        effect_size=0.5, tails=2, allocation_ratio=ratio,
        allocation_rule="n1-grid",
    )
    n1, n2 = res.sample_size["n1"], res.sample_size["n2"]
    assert n2 == _round_half_up(ratio * n1)


@pytest.mark.parametrize("ratio", [0.5, 1.5, 2.0, 3.0])
def test_total_grid_never_needs_more_than_n1_grid(ratio):
    kw = dict(
        alpha=0.05, power_target=0.9, effect_size=0.5, tails=2,
        allocation_ratio=ratio,
    )
    a = solve("ttest-indep-means", "n", allocation_rule="n1-grid", **kw)
    b = solve("ttest-indep-means", "n", allocation_rule="total-grid", **kw)
    assert b.sample_size["total"] <= a.sample_size["total"]
    assert a.power >= 0.9 and b.power >= 0.9


def test_allocation_ratio_is_recorded():
    res = solve(
        "ttest-indep-means", "n", alpha=0.05, power_target=0.8,
        effect_size=0.5, tails=2, allocation_ratio=2.0,
    )
    assert res.sample_size["allocation_ratio"] == 2.0
    assert res.engine["allocation_rule"] == "even-total"


# --------------------------------------------------------------------------
# Validation and error handling
# --------------------------------------------------------------------------
def test_unknown_test_raises():
    with pytest.raises(ValidationError):
        solve("anova-oneway", "n", alpha=0.05, power_target=0.8, effect_size=0.5)


def test_alias_resolution():
    a = solve("indep", "n", alpha=0.05, power_target=0.8, effect_size=0.5)
    b = solve(
        "ttest-indep-means", "n", alpha=0.05, power_target=0.8, effect_size=0.5
    )
    assert a.sample_size == b.sample_size


def test_bad_alpha_and_tails():
    with pytest.raises(ValidationError):
        solve("ttest-one-sample", "power", alpha=0.0, effect_size=0.5, n=20)
    with pytest.raises(ValidationError):
        solve("ttest-one-sample", "power", alpha=0.05, effect_size=0.5, n=20, tails=3)


def test_point_biserial_rejects_r_at_one():
    with pytest.raises(ValidationError):
        solve("ttest-point-biserial", "n", alpha=0.05, power_target=0.8, effect_size=1.0)


def test_generic_requires_df_and_refuses_apriori():
    with pytest.raises(ValidationError):
        solve("ttest-generic", "power", alpha=0.05, effect_size=2.0)
    with pytest.raises(ValidationError):
        solve(
            "ttest-generic", "n", alpha=0.05, power_target=0.8,
            effect_size=2.0, extra={"df": 10},
        )


def test_unknown_extra_parameter_is_rejected():
    with pytest.raises(ValidationError):
        solve(
            "ttest-one-sample", "power", alpha=0.05, effect_size=0.5,
            n=20, extra={"predictors": 3},
        )


def test_an_a_priori_effect_below_the_gui_minimum_is_refused():
    """SPEC F-15: |ES| < 1e-5 is refused in an a-priori analysis."""
    with pytest.raises(ValidationError, match="at least"):
        solve(
            "ttest-regression-coef", "n", alpha=0.001, power_target=0.99,
            effect_size=1e-9, tails=2, extra={"predictors": 1},
        )


def test_df_must_stay_positive():
    with pytest.raises(ValidationError):
        solve(
            "ttest-regression-coef", "power", alpha=0.05, effect_size=0.15,
            n=4, extra={"predictors": 10},
        )


def test_negative_effect_size_is_flagged_but_solved():
    res = solve(
        "ttest-one-sample", "n", alpha=0.05, power_target=0.8,
        effect_size=-0.5, tails=1,
    )
    assert res.sample_size["total"] > 0
    assert any("negative effect size" in w for w in res.warnings)


# --------------------------------------------------------------------------
# power_curve
# --------------------------------------------------------------------------
def test_power_curve_matches_point_queries():
    rows = power_curve(
        "ttest-one-sample", alpha=0.05, effect_size=0.5, tails=2,
        n_from=20, n_to=40, n_step=5,
    )
    assert [r["total"] for r in rows] == [20, 25, 30, 35, 40]
    for r in rows:
        direct = solve(
            "ttest-one-sample", "power", alpha=0.05, effect_size=0.5,
            tails=2, n=r["total"],
        ).power
        assert r["power"] == pytest.approx(direct, abs=1e-14)


def test_power_curve_row_cap():
    with pytest.raises(ValidationError):
        power_curve(
            "ttest-one-sample", alpha=0.05, effect_size=0.5,
            n_from=1, n_to=10_000, n_step=1,
        )


def test_power_function_matches_solve_power():
    pt = power("ttest-indep-means", alpha=0.05, effect_size=0.5, n1=30, n2=45)
    res = solve(
        "ttest-indep-means", "power", alpha=0.05, effect_size=0.5, n1=30, n2=45
    )
    assert pt.power == pytest.approx(res.power, abs=1e-15)
    assert pt.df == res.df == 73


def test_an_explicit_design_reports_its_own_ratio_not_the_default():
    """Found by the live agent run (agent/transcripts/): a post-hoc result on
    79 + 158 used to print 'Allocation ratio N2/N1 = 1'."""
    for mode, kw in (("power", {"alpha": 0.05, "effect_size": 0.5}),
                     ("alpha", {"power_target": 0.8, "effect_size": 0.5}),
                     ("effect-size", {"alpha": 0.05, "power_target": 0.8}),
                     ("compromise", {"effect_size": 0.5, "beta_alpha_ratio": 1.0})):
        res = solve("ttest-indep-means", mode, n1=79, n2=158, **kw)
        assert res.sample_size["allocation_ratio"] == pytest.approx(2.0), mode
