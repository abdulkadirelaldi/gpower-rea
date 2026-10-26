"""SPEC F-16: the gaps the second clean-room pass found in v1.2, as settled.

Every assertion with a probe id is what G*Power 3.1.9.6 printed for that
input (probes/observations/); the rest are the conventions F-16 states.
"""

from __future__ import annotations

import pytest

from gpower_rea import ValidationError, solve


def test_g2_04_even_total_does_not_skip_a_group_of_one():
    """X-G2-04 / D-28: R = 3, d = 8 -> 1 / 3, N = 4."""
    res = solve("ttest-indep-means", "n", alpha=0.05, power_target=0.8,
                effect_size=8, tails=2, allocation_ratio=3)
    assert (res.sample_size["n1"], res.sample_size["n2"]) == (1, 3)
    assert f"{res.power:.7f}" == "0.9084887"


def test_g2_14_the_split_is_computed_in_binary_double():
    """X-G2-14: 66/8.8 is 7.4999... in double, and G*Power prints 7 / 59."""
    res = solve("ttest-indep-means", "n", alpha=0.05, power_target=0.8,
                effect_size=1.11, tails=2, allocation_ratio=7.8)
    assert (res.sample_size["n1"], res.sample_size["n2"]) == (7, 59)
    assert f"{res.power:.7f}" == "0.7807817"


def test_g2_05_delta_is_printed_at_the_reported_split():
    """S-019: 87 / 131, delta = 3.6152392 (not 3.6166283 of the unrounded split)."""
    res = solve("ttest-indep-means", "n", alpha=0.05, power_target=0.9495,
                effect_size=0.5, tails=2, allocation_ratio=1.5)
    assert f"{res.noncentrality:.7f}" == "3.6152392"


def test_g2_06_point_biserial_r_zero_is_admissible_post_hoc():
    """X-G2-06: power = alpha."""
    res = solve("ttest-point-biserial", "power", alpha=0.05, effect_size=0, n=10)
    assert f"{res.power:.7f}" == "0.0500000"


def test_g2_08_the_a_priori_floor_covers_f2_but_not_r():
    with pytest.raises(ValidationError):            # X-G2-08b
        solve("ttest-regression-coef", "n", alpha=0.05, power_target=0.8,
              effect_size=5e-6, extra={"predictors": 1})
    res = solve("ttest-point-biserial", "n", alpha=0.05, power_target=0.8,
                effect_size=5e-6)                   # X-G2-08a: N = 3.1e11
    assert res.sample_size["total"] > 3e11


@pytest.mark.parametrize("ratio,ok", [(0.001, False), (0.01, True), (100, True), (1000, False)])
def test_g2_11_allocation_ratio_domain(ratio, ok):
    """X-G2-11a-d: [0.01, 100]."""
    call = lambda: solve("ttest-indep-means", "n", alpha=0.05, power_target=0.8,  # noqa: E731
                         effect_size=0.5, allocation_ratio=ratio)
    if ok:
        assert call().sample_size["total"] == 3206
    else:
        with pytest.raises(ValidationError, match="allocation ratio"):
            call()


def test_g2_02_each_group_needs_one():
    with pytest.raises(ValidationError, match="at least 1"):   # X-G2-02
        solve("ttest-indep-means", "power", alpha=0.05, effect_size=0.5, n1=0, n2=3)
    solve("ttest-indep-means", "power", alpha=0.05, effect_size=0.5, n1=1, n2=2)  # D-24


def test_g2_17_at_least_one_predictor():
    with pytest.raises(ValidationError):                       # X-G2-17
        solve("ttest-regression-coef", "power", alpha=0.05, effect_size=0.15,
              n=20, extra={"predictors": 0})


def test_g2_09_a_zero_effect_prints_a_positive_critical_value():
    """D-06."""
    res = solve("ttest-indep-means", "power", alpha=0.05, effect_size=0, n1=20, n2=20)
    assert res.critical_t > 0


@pytest.mark.parametrize("ratio,split", [(100, (0, 6)), (0.01, (6, 0))])
def test_g3_01_even_total_reports_an_empty_group_like_gpower(ratio, split):
    """X-G3-01a,b: G*Power prints an empty group, delta = 0, power = alpha."""
    res = solve("ttest-indep-means", "n", alpha=0.05, power_target=0.8,
                effect_size=20, tails=2, allocation_ratio=ratio)
    assert (res.sample_size["n1"], res.sample_size["n2"]) == split
    assert f"{res.power:.7f}" == "0.0500000"
    assert res.df == 4


def test_g3_03_the_a_priori_floor_for_r_is_1e6():
    with pytest.raises(ValidationError, match="1e-06"):
        solve("ttest-point-biserial", "n", alpha=0.05, power_target=0.8, effect_size=5e-7)
