"""SPEC F-13: the twelve points v1.0 left undetermined, each locked.

Every assertion here corresponds to one row of the F-13 table.  They exist
because five of these points were places where two independent implementations
of SPEC.md v1.0 produced different numbers (docs/EVIDENCE/E-013).  Specifying
a convention is worth nothing unless the convention is enforced, so each one is
a test rather than a sentence.
"""

from __future__ import annotations

import math

import pytest

from gpower_rea import NoSolutionError, ValidationError, solve
from gpower_rea.engine import ALPHA_SEARCH_MAX, ALPHA_SEARCH_MIN
from gpower_rea.procedures import PROCEDURES


# --------------------------------------------------------------------------
# item 1 -- compromise is a solving analysis, so it uses |delta|
# --------------------------------------------------------------------------
def test_compromise_uses_the_absolute_effect_size():
    """Two independent readers of v1.0 got alpha = 0.133 and alpha = 0.867
    here.  v1.1 says compromise joins the other three solving analyses."""
    neg = solve(
        "ttest-indep-means", "compromise",
        effect_size=-0.5, tails=1, n1=40, n2=40, beta_alpha_ratio=1.0,
    )
    pos = solve(
        "ttest-indep-means", "compromise",
        effect_size=0.5, tails=1, n1=40, n2=40, beta_alpha_ratio=1.0,
    )
    assert neg.alpha == pytest.approx(pos.alpha, abs=1e-12)
    assert neg.power == pytest.approx(pos.power, abs=1e-12)
    assert neg.alpha < 0.5, "the |delta| reading must give a usable alpha"
    assert any("negative effect size" in w for w in neg.warnings)
    assert pos.warnings == []


def test_compromise_is_sign_invariant_for_two_tails_either_way():
    """The control: for k = 2 the choice is unobservable, so a difference here
    would mean the test itself is wrong."""
    a = solve(
        "ttest-indep-means", "compromise",
        effect_size=-0.5, tails=2, n1=40, n2=40, beta_alpha_ratio=2.0,
    )
    b = solve(
        "ttest-indep-means", "compromise",
        effect_size=0.5, tails=2, n1=40, n2=40, beta_alpha_ratio=2.0,
    )
    assert a.alpha == pytest.approx(b.alpha, abs=1e-14)


# --------------------------------------------------------------------------
# item 2 -- f2 is squared, so the sign rule does not extend to it
# --------------------------------------------------------------------------
@pytest.mark.parametrize("mode,kwargs", [
    ("power", dict(alpha=0.05, n=60)),
    ("n", dict(alpha=0.05, power_target=0.8)),
])
def test_negative_f_squared_is_rejected(mode, kwargs):
    with pytest.raises(ValidationError, match="admissible domain"):
        solve(
            "ttest-regression-coef", mode,
            effect_size=-0.15, tails=2, extra={"predictors": 3}, **kwargs,
        )


def test_zero_f_squared_is_admissible_for_post_hoc():
    """f2 = 0 means no effect, which is a perfectly good post-hoc question:
    the answer is exactly alpha (F-02)."""
    res = solve(
        "ttest-regression-coef", "power",
        alpha=0.05, effect_size=0.0, tails=2, n=60, extra={"predictors": 3},
    )
    assert res.power == pytest.approx(0.05, abs=1e-9)


def test_the_sign_rule_still_applies_to_d_dz_r_and_generic_delta():
    for test, es in (
        ("ttest-one-sample", -0.5),
        ("ttest-paired-means", -0.5),
        ("ttest-point-biserial", -0.3),
        ("ttest-generic", -2.0),
    ):
        extra = {"df": 30} if test == "ttest-generic" else None
        kw = {"extra": extra} if extra else {}
        res = solve(
            test, "power", alpha=0.05, effect_size=es, tails=1,
            **({"n": 40} if test != "ttest-generic" else {}), **kw,
        )
        assert res.noncentrality < 0, f"{test}: sign was discarded"
        assert res.power < 0.05, f"{test}: power should be below alpha"


# --------------------------------------------------------------------------
# item 3 -- the result echoes the effect size AS SUPPLIED
# --------------------------------------------------------------------------
def test_the_reported_effect_size_is_the_input_not_the_value_used():
    res = solve(
        "ttest-one-sample", "n",
        alpha=0.05, power_target=0.8, effect_size=-0.5, tails=1,
    )
    assert res.effect_size["value"] == -0.5, "the input must be echoed"
    # and the value actually used is recoverable from the noncentrality
    assert res.noncentrality == pytest.approx(
        0.5 * math.sqrt(res.sample_size["total"]), rel=1e-12
    )
    assert any("negative effect size" in w for w in res.warnings)


def test_sensitivity_reports_the_answer_because_there_is_no_input():
    res = solve("ttest-one-sample", "effect-size", alpha=0.05, power_target=0.8, n=40)
    back = solve(
        "ttest-one-sample", "power",
        alpha=0.05, effect_size=res.effect_size["value"], tails=2, n=40,
    )
    assert back.power == pytest.approx(0.8, abs=1e-9)


# --------------------------------------------------------------------------
# item 4 -- closed sensitivity brackets
# --------------------------------------------------------------------------
EXPECTED_BOUNDS = {
    "ttest-indep-means": (1e-12, 100.0),
    "ttest-paired-means": (1e-12, 100.0),
    "ttest-one-sample": (1e-12, 100.0),
    "ttest-point-biserial": (1e-12, 1.0 - 1e-12),
    "ttest-regression-coef": (1e-12, 1e6),
    "ttest-generic": (1e-12, 1e6),
}


@pytest.mark.parametrize("key", sorted(EXPECTED_BOUNDS))
def test_effect_size_brackets_match_the_specification(key):
    assert PROCEDURES[key].es_bounds == EXPECTED_BOUNDS[key]


def test_sensitivity_returns_the_lower_bound_when_the_target_is_already_met():
    """A target power *below* alpha is met by any effect size at all, so the
    answer is the documented lower end of the bracket."""
    res = solve(
        "ttest-one-sample", "effect-size", alpha=0.20, power_target=0.15,
        tails=2, n=50,
    )
    assert res.effect_size["value"] == pytest.approx(1e-12, rel=1e-6)
    assert res.power == pytest.approx(0.20, abs=1e-9), (
        "at the lower bound the power is the size of the test"
    )


def test_sensitivity_at_the_knife_edge_target_equals_alpha():
    """Target power exactly equal to alpha is the boundary of the domain.

    Power at the lower bracket end *is* alpha to within 1e-17, so whether the
    search returns the bracket end or the first representable crossing above
    it is decided by one bit.  The documented behaviour is only that the
    answer is admissible and reproduces the target -- not which side of the
    bit it lands on.
    """
    res = solve(
        "ttest-one-sample", "effect-size", alpha=0.20, power_target=0.20,
        tails=2, n=50,
    )
    es = res.effect_size["value"]
    assert 1e-12 <= es < 1e-6, f"expected a negligible effect size, got {es:g}"
    assert res.power == pytest.approx(0.20, abs=1e-9)


def test_sensitivity_fails_rather_than_returning_the_upper_bound():
    with pytest.raises(NoSolutionError):
        solve(
            "ttest-point-biserial", "effect-size",
            alpha=1e-300, power_target=0.999999, tails=2, n=3,
        )


# --------------------------------------------------------------------------
# item 5 -- the criterion analysis bisects log(alpha)
# --------------------------------------------------------------------------
def test_criterion_finds_an_astronomically_small_alpha():
    """This was a real defect: the old linear bracket returned its own floor
    of 1e-12 when the honest answer is 4.2e-60 (E-013)."""
    res = solve(
        "ttest-one-sample", "alpha",
        power_target=0.05, effect_size=1.5, tails=2, n=200,
    )
    assert res.alpha < 1e-50, f"got {res.alpha:g}; the floor-return bug is back"
    assert res.alpha == pytest.approx(4.2133e-60, rel=1e-3)
    # and it round-trips
    back = solve(
        "ttest-one-sample", "power",
        alpha=res.alpha, effect_size=1.5, tails=2, n=200,
    )
    assert back.power == pytest.approx(0.05, rel=1e-6)


@pytest.mark.parametrize("target", [0.05, 0.2, 0.5, 0.8, 0.95, 0.999])
def test_criterion_round_trips_across_the_whole_range(target):
    res = solve(
        "ttest-indep-means", "alpha",
        power_target=target, effect_size=0.5, tails=2, n1=50, n2=50,
    )
    assert ALPHA_SEARCH_MIN <= res.alpha <= ALPHA_SEARCH_MAX
    back = solve(
        "ttest-indep-means", "power",
        alpha=res.alpha, effect_size=0.5, tails=2, n1=50, n2=50,
    )
    assert back.power == pytest.approx(target, rel=1e-7, abs=1e-9)


def test_criterion_bracket_endpoints_are_the_documented_ones():
    assert ALPHA_SEARCH_MIN == 1e-300
    assert ALPHA_SEARCH_MAX == 1.0 - 1e-15


# --------------------------------------------------------------------------
# item 6 -- the reported critical t is the F-02 quantile, signed
# --------------------------------------------------------------------------
def test_critical_t_is_signed_and_can_be_negative():
    res = solve("ttest-one-sample", "power", alpha=0.75, effect_size=0.3, tails=1, n=30)
    assert res.critical_t < 0, "a one-tailed alpha > 0.5 has a negative quantile"


def test_critical_t_for_two_tails_is_the_upper_quantile():
    from gpower_rea import numerics as nm

    res = solve("ttest-one-sample", "power", alpha=0.05, effect_size=0.5, tails=2, n=30)
    assert res.critical_t == pytest.approx(nm.t_ppf(0.975, 29), rel=1e-12)
    assert res.critical_t > 0


# --------------------------------------------------------------------------
# item 7 -- inadmissible grid points are skipped, not fatal
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ratio", [0.05, 0.1, 10.0, 20.0, 50.0])
@pytest.mark.parametrize("rule", ["n1-grid", "total-grid"])
def test_extreme_allocation_ratios_still_solve(ratio, rule):
    res = solve(
        "ttest-indep-means", "n",
        alpha=0.05, power_target=0.8, effect_size=0.8, tails=2,
        allocation_ratio=ratio, allocation_rule=rule,
    )
    assert res.sample_size["n1"] >= 2
    assert res.sample_size["n2"] >= 2
    assert res.power >= 0.8


# --------------------------------------------------------------------------
# item 8 -- a zero effect size is a validation error in the solving analyses
# --------------------------------------------------------------------------
@pytest.mark.parametrize("mode,kwargs", [
    ("n", dict(alpha=0.05, power_target=0.8)),
    ("alpha", dict(power_target=0.8, n=50)),
    ("compromise", dict(beta_alpha_ratio=1.0, n=50)),
])
def test_zero_effect_size_is_refused_by_the_solving_analyses(mode, kwargs):
    with pytest.raises(ValidationError, match="zero effect size"):
        solve("ttest-one-sample", mode, effect_size=0.0, tails=2, **kwargs)


def test_zero_effect_size_is_fine_for_post_hoc_and_returns_alpha():
    res = solve("ttest-one-sample", "power", alpha=0.05, effect_size=0.0, tails=2, n=50)
    assert res.power == pytest.approx(0.05, abs=1e-10)


def test_zero_effect_size_refusal_is_immediate_not_a_ten_million_step_search():
    """Behavioural, not just cosmetic: the old path exhausted N_SEARCH_CAP."""
    import time

    start = time.perf_counter()
    with pytest.raises(ValidationError):
        solve("ttest-one-sample", "n", alpha=0.05, power_target=0.8, effect_size=0.0)
    assert time.perf_counter() - start < 0.5


# --------------------------------------------------------------------------
# item 9 -- display rounding never enters a search
# --------------------------------------------------------------------------
def test_the_returned_values_are_full_precision():
    res = solve("ttest-indep-means", "n", alpha=0.05, power_target=0.95, effect_size=0.5)
    assert res.power != round(res.power, 7), (
        "the result must carry full precision; rounding is for rendering only"
    )
    from gpower_rea.report import text_block

    assert "0.9501287" in text_block(res)


# --------------------------------------------------------------------------
# item 10 -- both allocation rules are reachable and reported
# --------------------------------------------------------------------------
def test_both_allocation_rules_are_reachable_and_named_in_the_result():
    from gpower_rea.engine import ALLOCATION_RULES, DEFAULT_ALLOCATION_RULE

    assert set(ALLOCATION_RULES) == {"n1-grid", "total-grid"}
    assert DEFAULT_ALLOCATION_RULE == "n1-grid"
    for rule in ALLOCATION_RULES:
        res = solve(
            "ttest-indep-means", "n", alpha=0.05, power_target=0.9,
            effect_size=0.5, tails=2, allocation_ratio=2.0, allocation_rule=rule,
        )
        assert res.engine["allocation_rule"] == rule


def test_an_unknown_allocation_rule_is_rejected():
    with pytest.raises(ValidationError, match="allocation rule"):
        solve(
            "ttest-indep-means", "n", alpha=0.05, power_target=0.9,
            effect_size=0.5, tails=2, allocation_ratio=2.0,
            allocation_rule="golden-ratio",
        )


# --------------------------------------------------------------------------
# item 11 -- an inapplicable design parameter is rejected, not ignored
# --------------------------------------------------------------------------
@pytest.mark.parametrize("test,bad", [
    ("ttest-one-sample", {"predictors": 3}),
    ("ttest-one-sample", {"df": 10}),
    ("ttest-indep-means", {"df": 10}),
    ("ttest-point-biserial", {"predictors": 2}),
    ("ttest-regression-coef", {"df": 10}),
    ("ttest-generic", {"predictors": 2}),
])
def test_inapplicable_parameters_are_rejected(test, bad):
    extra = dict(bad)
    if test == "ttest-generic":
        extra.setdefault("df", 20)
    with pytest.raises(ValidationError, match="unknown parameter"):
        solve(test, "power", alpha=0.05, effect_size=0.5, tails=2, n=40, extra=extra)


# --------------------------------------------------------------------------
# item 12 -- the generic test accepts any positive df, including below 1
# --------------------------------------------------------------------------
@pytest.mark.parametrize("df", [0.05, 0.5, 0.999, 1.0, 1.5, 2.0, 1e6])
def test_generic_accepts_fractional_degrees_of_freedom(df):
    res = solve("ttest-generic", "power", alpha=0.05, effect_size=2.0, tails=2,
                extra={"df": df})
    assert 0.0 < res.power < 1.0
    assert res.df == df


@pytest.mark.parametrize("df", [0.0, -1.0])
def test_generic_rejects_a_non_positive_df(df):
    with pytest.raises(ValidationError):
        solve("ttest-generic", "power", alpha=0.05, effect_size=2.0, tails=2,
              extra={"df": df})


def test_generic_df_below_one_is_still_a_valid_size_at_the_null():
    """The quadrature must hold up for df < 1, or item 12 is a licence to be
    wrong rather than a documented domain."""
    for df in (0.05, 0.3, 0.75):
        res = solve("ttest-generic", "power", alpha=0.10, effect_size=1e-12,
                    tails=2, extra={"df": df})
        assert res.power == pytest.approx(0.10, abs=1e-8)
