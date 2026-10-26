"""F-05 counter-examples, re-derived without using this engine's search.

A fair objection to the counter-example table in
docs/EVIDENCE/E-005-balanced-search-grid.md is that those numbers come from the
engine, so a bug in *our* integer search could manufacture a counter-example
that does not exist.

This file answers that objection using only third-party code:
``statsmodels`` supplies the continuous per-group `n` and evaluates the power
of an unbalanced split directly.  Under the two candidate grids the integer
answer is ``2*ceil(n_frac)`` (per-group search) versus the smallest sufficient
total (total-N search), and statsmodels' own power function decides which one
clears the target.

Skipped automatically when statsmodels is not installed.
"""

from __future__ import annotations

import math

import pytest

sm_power = pytest.importorskip(
    "statsmodels.stats.power", reason="statsmodels not installed"
)

from gpower_rea import solve  # noqa: E402

_indep = sm_power.TTestIndPower()

ALPHA = 0.05


def _n_frac(d: float, target: float) -> float:
    return float(
        _indep.solve_power(effect_size=d, power=target, alpha=ALPHA, ratio=1.0,
                           alternative="two-sided")
    )


def _sm_power(d: float, n1: int, n2: int) -> float:
    return float(
        _indep.power(effect_size=d, nobs1=n1, alpha=ALPHA, ratio=n2 / n1,
                     alternative="two-sided")
    )


#: (d, target, per-group-grid total, odd total, odd split suffices?)
#: Every figure here is reproduced below from statsmodels alone.
COUNTER_EXAMPLES = [
    (0.20, 0.80, 788, 787, True),
    (0.25, 0.80, 506, 505, True),
    (0.30, 0.80, 352, 351, True),
    (0.42, 0.90, 242, 241, True),
    (0.45, 0.95, 260, 259, True),
    # controls: the two grids agree here
    (0.35, 0.90, 346, 345, False),
    (0.50, 0.95, 210, 209, False),
    (0.62, 0.85, 96, 95, False),
]


@pytest.mark.parametrize(
    "d,target,even_total,odd_total,odd_suffices",
    COUNTER_EXAMPLES,
    ids=[f"d{d}-p{t}" for d, t, *_ in COUNTER_EXAMPLES],
)
def test_counter_example_holds_without_our_search(
    d, target, even_total, odd_total, odd_suffices
):
    per_group = math.ceil(_n_frac(d, target) - 1e-12)
    assert 2 * per_group == even_total, (
        f"statsmodels' continuous solution gives {per_group} per group, so the "
        f"per-group grid total is {2 * per_group}, not {even_total}"
    )
    assert odd_total == 2 * per_group - 1

    p_odd = _sm_power(d, per_group - 1, per_group)
    assert (p_odd >= target) is odd_suffices, (
        f"statsmodels says the odd split ({per_group - 1},{per_group}) has "
        f"power {p_odd:.7f} against a target of {target}"
    )

    # And our engine, searching per group, reports the even total either way.
    ours = solve(
        "ttest-indep-means", "n", alpha=ALPHA, power_target=target,
        effect_size=d, tails=2, allocation_ratio=1.0,
    ).sample_size["total"]
    assert ours == even_total


def test_the_grids_disagree_on_about_half_of_all_settings():
    """SPEC F-05 quotes 50.2% over this exact sweep; hold it to +/- 3 points.

    The sweep uses statsmodels throughout, so the figure is independent of the
    engine's search code.
    """
    differ = same = 0
    for i in range(100, 1201, 7):
        d = i / 1000
        for target in (0.80, 0.90, 0.95):
            per_group = math.ceil(_n_frac(d, target) - 1e-12)
            if per_group < 3:
                continue
            if _sm_power(d, per_group - 1, per_group) >= target:
                differ += 1
            else:
                same += 1
    rate = differ / (differ + same)
    assert differ + same >= 450, "sweep shrank; the quoted figure is stale"
    assert 0.47 <= rate <= 0.53, (
        f"the grids disagree on {rate:.1%} of settings; SPEC F-05 says 50.2% "
        f"-- update SPEC.md if this has genuinely moved"
    )


def test_published_d02_result_is_reproduced():
    """d = 0.20 at 80% power is the most quoted figure for this design."""
    ours = solve(
        "ttest-indep-means", "n", alpha=0.05, power_target=0.80,
        effect_size=0.20, tails=2,
    )
    assert ours.sample_size == {
        "n1": 394, "n2": 394, "total": 788,
        "allocation_ratio": 1.0, "actual_ratio": 1.0,
    }
    assert math.ceil(_n_frac(0.20, 0.80) - 1e-12) == 394
