"""Accuracy and self-consistency of the hand-rolled special functions."""

from __future__ import annotations

import math

import pytest

from gpower_rea import numerics as nm
from gpower_rea.numerics import (
    _gauss_legendre,
    _scale_panels,
    _scale_params,
    _scale_pdf,
)

try:
    from scipy import stats as _sp
except ImportError:  # pragma: no cover
    _sp = None

needs_scipy = pytest.mark.skipif(_sp is None, reason="scipy not installed")


# --------------------------------------------------------------------------
# Self-consistency -- holds with no external oracle at all
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "df",
    [0.01, 0.05, 0.3, 0.75, 1, 2, 3, 5, 10, 29, 30, 31, 37, 208, 1000,
     10_000, 100_000, 1_000_000],
)
def test_log_scale_density_integrates_to_one(df):
    """The quadrature panels used by nct_cdf must carry all the probability.

    This is the strongest check available with no oracle at all, and it spans
    eight orders of magnitude of df including values below 1, where the old
    s-space formulation failed.  df = 29/30/31 straddle the Stirling threshold
    inside ``_log_scale_params``, so the two branches are pinned to each other
    as well.
    """
    from gpower_rea.numerics import _log_h, _log_scale_panels, _log_scale_params

    nodes, weights = _gauss_legendre(24)
    a, l0 = _log_scale_params(float(df))
    mass = 0.0
    for lo, hi in _log_scale_panels(float(df)):
        half, mid = 0.5 * (hi - lo), 0.5 * (hi + lo)
        for x, w in zip(nodes, weights):
            lh = _log_h(mid + half * x, a, l0)
            if lh > -745.0:
                mass += half * w * math.exp(lh)
    assert mass == pytest.approx(1.0, abs=1e-13)


@pytest.mark.parametrize("df", [1, 2, 3, 5, 10, 208, 10_000])
def test_scale_density_integrates_to_one(df):
    """The superseded s-space formulation is kept and still checked for
    df >= 1, because `_scale_pdf` documents the two Stirling branches that
    `_log_scale_params` inherited."""
    nodes, weights = _gauss_legendre(24)
    params = _scale_params(float(df))
    mass = 0.0
    for lo, hi in _scale_panels(float(df)):
        half, mid = 0.5 * (hi - lo), 0.5 * (hi + lo)
        mass += half * sum(
            w * _scale_pdf(mid + half * x, params) for x, w in zip(nodes, weights)
        )
    assert mass == pytest.approx(1.0, abs=1e-13)


def test_scale_density_branches_agree_at_the_threshold():
    """The exact-lgamma and Stirling branches must be interchangeable."""
    from gpower_rea.numerics import _STIRLING_MIN

    df = 2.0 * _STIRLING_MIN  # a == _STIRLING_MIN exactly
    stirling = _scale_params(df)
    assert stirling[2] is True
    a = 0.5 * df
    exact = (a, math.log(2.0) + a * math.log(a) - math.lgamma(a), False)
    for s in (0.6, 0.9, 1.0, 1.05, 1.4):
        assert _scale_pdf(s, stirling) == pytest.approx(
            _scale_pdf(s, exact), rel=1e-13
        )


def test_log_beta_matches_lgamma_for_moderate_arguments():
    for a, b in [(0.5, 0.5), (1.0, 7.0), (12.5, 0.5), (29.5, 0.5), (31.0, 0.5)]:
        naive = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        assert nm.log_beta(a, b) == pytest.approx(naive, rel=1e-13)


def test_betainc_xy_handles_x_next_to_one():
    """Passing the complement explicitly is what keeps t_cdf accurate at
    large df; recovering it by subtraction loses ~11 digits."""
    df, t = 20000.0, 2.0
    denom = df + t * t
    good = nm.betainc_xy(0.5 * df, 0.5, df / denom, t * t / denom)
    naive = nm.betainc(0.5 * df, 0.5, df / denom)
    assert good == pytest.approx(naive, rel=1e-8)
    assert 0.0 < good < 1.0


@pytest.mark.parametrize("df", [1, 2, 7, 31, 208])
def test_nct_reduces_to_central_t_at_zero_ncp(df):
    for t in (-3.0, -0.5, 0.0, 1.0, 1.96, 4.0):
        assert nm.nct_cdf(t, df, 1e-300) == pytest.approx(
            nm.t_cdf(t, df), abs=1e-12
        )


@pytest.mark.parametrize("df", [1, 3, 12, 97])
def test_t_cdf_symmetry(df):
    for t in (0.1, 0.9, 2.3, 7.0):
        assert nm.t_cdf(-t, df) == pytest.approx(1.0 - nm.t_cdf(t, df), abs=1e-14)


@pytest.mark.parametrize("df", [1, 2, 6, 40, 500])
def test_t_ppf_inverts_t_cdf(df):
    for p in (1e-4, 0.01, 0.1, 0.5, 0.9, 0.975, 0.999):
        t = nm.t_ppf(p, df)
        assert nm.t_cdf(t, df) == pytest.approx(p, abs=1e-13)


def test_t_ppf_exact_median():
    for df in (1, 2, 10, 1000):
        assert nm.t_ppf(0.5, df) == 0.0


@pytest.mark.parametrize("df", [1, 5, 30, 300])
def test_nct_cdf_is_monotone_in_t(df):
    prev = -1.0
    for t in [-6.0, -3.0, -1.0, 0.0, 0.5, 1.0, 2.0, 5.0, 10.0]:
        cur = nm.nct_cdf(t, df, 2.5)
        assert cur >= prev - 1e-15
        prev = cur


@pytest.mark.parametrize("df", [2, 9, 60])
def test_nct_cdf_decreases_in_ncp(df):
    prev = 2.0
    for ncp in [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]:
        cur = nm.nct_cdf(1.96, df, ncp)
        assert cur <= prev + 1e-15
        prev = cur


def test_norm_cdf_known_values():
    assert nm.norm_cdf(0.0) == pytest.approx(0.5, abs=1e-16)
    assert nm.norm_cdf(1.959963984540054) == pytest.approx(0.975, abs=1e-12)
    assert nm.norm_cdf(-8.0) == pytest.approx(6.22096057e-16, rel=1e-6)


def test_norm_ppf_inverts_norm_cdf():
    for p in (1e-12, 1e-6, 0.01, 0.2, 0.5, 0.8, 0.99, 1 - 1e-6, 1 - 1e-12):
        assert nm.norm_cdf(nm.norm_ppf(p)) == pytest.approx(p, rel=1e-11, abs=1e-18)


def test_chi2_ppf_inverts_chi2_cdf():
    # chi2 only sets the quadrature panel edges, so 1e-10 relative is ample;
    # the accuracy of nct_cdf is pinned separately below.
    for df in (1, 2, 7, 40, 300):
        for p in (1e-8, 0.01, 0.5, 0.99, 1 - 1e-8):
            x = nm.chi2_ppf(p, df)
            assert nm.chi2_cdf(x, df) == pytest.approx(p, rel=1e-10, abs=1e-15)


def test_betainc_edges_and_symmetry():
    assert nm.betainc(2.0, 3.0, 0.0) == 0.0
    assert nm.betainc(2.0, 3.0, 1.0) == 1.0
    for a, b, x in [(0.5, 0.5, 0.3), (2.0, 7.0, 0.42), (104.0, 0.5, 0.8)]:
        assert nm.betainc(a, b, x) == pytest.approx(
            1.0 - nm.betainc(b, a, 1.0 - x), abs=1e-14
        )


# --------------------------------------------------------------------------
# The tail-probability quantile, and the regimes that broke the old one
# --------------------------------------------------------------------------
@pytest.mark.parametrize("df", [0.05, 0.5, 1, 2, 7, 40, 500, 5000])
def test_t_isf_round_trips_through_t_sf(df):
    for q in (1e-300, 1e-120, 1e-60, 1e-12, 1e-4, 0.025, 0.1, 0.4, 0.5, 0.9):
        try:
            t = nm.t_isf(q, df)
        except ValueError:
            continue  # quantile outside the double range; documented
        assert nm.t_sf(t, df) == pytest.approx(q, rel=1e-9)


@pytest.mark.parametrize("df", [1, 2, 7, 40, 500])
def test_t_isf_agrees_with_t_ppf_where_both_are_well_conditioned(df):
    for q in (0.001, 0.025, 0.05, 0.1, 0.25, 0.4):
        assert nm.t_isf(q, df) == pytest.approx(nm.t_ppf(1.0 - q, df), rel=1e-12)


def test_t_isf_is_exact_for_the_cauchy_tail():
    """df = 1 has a closed form: P(T > t) -> 1/(pi*t).

    At q = 1e-300 that is 3.1830988618e299.  The old implementation squared t,
    overflowed, and returned 1.2e69; SciPy 1.14 returns 1e100.  Both are
    wrong, and neither says so.
    """
    for q in (1e-300, 1e-200, 1e-100, 1e-40):
        t = nm.t_isf(q, df=1)
        assert t == pytest.approx(1.0 / (math.pi * q), rel=1e-9)


def test_t_sf_survives_arguments_that_overflow_when_squared():
    """t*t overflows above about 1.34e154; the asymptotic branch must take over
    smoothly rather than produce nan or a spurious zero."""
    for df in (0.5, 1.0, 3.0):
        for t in (1e120, 1e155, 1e200, 1e300):
            val = nm.t_sf(t, df)
            assert math.isfinite(val)
            assert 0.0 <= val < 1e-50
    # Monotone decreasing while the tail is still representable.  At df = 3,
    # t = 1e120 the true tail is ~1e-360 and genuinely underflows to 0, so
    # use a df whose tail survives.
    assert 0.0 < nm.t_sf(1e200, 0.5) < nm.t_sf(1e120, 0.5)
    assert nm.t_sf(1e120, 0.5) == pytest.approx(
        math.exp(
            0.5 * 0.5 * (math.log(0.5) - 2.0 * math.log(1e120))
            - math.log(0.5)
            - nm.log_beta(0.25, 0.5)
        ),
        rel=1e-12,
    )


def test_t_sf_asymptotic_branch_joins_the_exact_one():
    """Continuity across the threshold: the two formulations must agree where
    both are valid."""
    from gpower_rea.numerics import _log_t_sf_asymptotic, _T_SQUARE_SAFE

    for df in (0.3, 1.0, 2.0, 7.0):
        t = _T_SQUARE_SAFE * 0.5  # just below the switch, so exact path runs
        exact = nm.t_sf(t, df)
        asym = math.exp(_log_t_sf_asymptotic(t, df))
        if exact > 0.0:
            assert asym == pytest.approx(exact, rel=1e-9)


def test_t_sf_symmetry():
    for df in (0.5, 1, 5, 60):
        for t in (0.3, 1.7, 9.0):
            assert nm.t_sf(-t, df) == pytest.approx(1.0 - nm.t_sf(t, df), abs=1e-14)


def test_t_isf_refuses_an_unrepresentable_quantile():
    """df = 0.05 with a tiny tail puts the quantile past the double range.

    Returning an unbracketed bisection there is what the old code did.
    """
    with pytest.raises(ValueError, match="range of a double"):
        nm.t_isf(1e-30, 0.05)


@pytest.mark.parametrize("df", [0.05, 0.1, 0.3, 0.5, 0.75, 0.9, 0.99])
def test_noncentral_t_is_accurate_below_one_degree_of_freedom(df):
    """The s-space quadrature silently degraded here (measured: a two-sided
    size of 0.252 where alpha was 0.100). The log-scale form fixes it."""
    for alpha in (0.01, 0.05, 0.10, 0.20):
        t_crit = nm.t_isf(0.5 * alpha, df)
        size = (1.0 - nm.nct_cdf(t_crit, df, 1e-30)) + nm.nct_cdf(-t_crit, df, 1e-30)
        assert size == pytest.approx(alpha, abs=1e-8)


@pytest.mark.parametrize("df", [1, 2, 5, 30, 208, 5000])
def test_two_sided_size_is_exact_in_relative_terms(df):
    """The size of the test must be alpha to **relative** precision, down to
    alpha = 1e-12.

    This is what the survival function buys.  Computing the upper term as
    ``1 - nct_cdf(t_crit)`` gives the same absolute error but a relative error
    of 6e-04 at alpha = 1e-12, because the subtraction throws away every
    significant digit of a tiny answer.
    """
    for alpha in (1e-12, 1e-6, 0.001, 0.01, 0.05, 0.10, 0.20, 0.50, 0.90):
        t_crit = nm.t_isf(0.5 * alpha, df)
        size = nm.nct_sf(t_crit, df, 1e-30) + nm.nct_cdf(-t_crit, df, 1e-30)
        assert size == pytest.approx(alpha, rel=1e-11)


@pytest.mark.parametrize("df", [1, 2, 7, 60, 500])
def test_nct_sf_and_nct_cdf_are_complementary(df):
    """Self-consistency with no oracle: the two must sum to 1 even though
    neither is computed from the other."""
    for ncp in (0.5, 2.0, 5.0, 12.0):
        for t in (-3.0, 0.0, 2.0, 7.0, 25.0):
            total = nm.nct_sf(t, df, ncp) + nm.nct_cdf(t, df, ncp)
            assert total == pytest.approx(1.0, abs=1e-14)


def test_nct_sf_keeps_relative_precision_for_a_tiny_answer():
    """A one-tailed test pointed the wrong way: power is 7.7e-06, and the
    subtraction-from-one formulation cannot represent it to better than 1e-16
    absolute -- i.e. two significant digits short of what is reported."""
    from gpower_rea import solve

    res = solve("ttest-one-sample", "power", alpha=0.05, effect_size=-0.5,
                tails=1, n=30)
    direct = nm.nct_sf(res.critical_t, res.df, res.noncentrality)
    assert res.power == pytest.approx(direct, rel=1e-13)
    assert 1e-6 < res.power < 1e-5


@needs_scipy
def test_nct_sf_matches_scipy():
    worst = 0.0
    for df in [1, 2, 3, 7, 25, 208, 2000]:
        for ncp in [0.1, 1.0, 3.6, 8.0, 30.0]:
            for t in [-4.0, 0.0, 1.96, 6.0, 40.0]:
                worst = max(
                    worst, abs(nm.nct_sf(t, df, ncp) - float(_sp.nct.sf(t, df, ncp)))
                )
    assert worst < 1e-12, f"worst nct_sf deviation {worst:g}"


def test_t_isf_matches_the_exact_cauchy_quantile():
    """df = 1 has a closed form: the upper q-quantile is cot(pi*q).

    Written as ``1/tan(pi*q)`` rather than the algebraically equal
    ``tan(pi*(1/2 - q))`` -- the latter forms ``0.5 - q`` and then evaluates
    tan next to its pole, which loses six digits at q = 1e-06.  The same
    class of mistake as the one this whole module is built to avoid.
    """
    for q in (0.4, 0.25, 0.1, 0.025, 0.005, 1e-6, 1e-10):
        assert nm.t_isf(q, 1) == pytest.approx(
            1.0 / math.tan(math.pi * q), rel=1e-12
        )


def test_phi_transition_gets_its_own_panels():
    """A huge critical value pushes Phi's turn far into the density's left
    tail; without a breakpoint there, Gauss-Legendre cannot resolve it."""
    from gpower_rea.numerics import _log_scale_panels, _panels_with_phi_transition

    base = _log_scale_panels(0.05)
    refined = _panels_with_phi_transition(0.05, 1.2e25, 1e-30)
    assert len(refined) > len(base)
    # the refinement must still tile exactly the same interval
    assert refined[0][0] == base[0][0]
    assert refined[-1][1] == base[-1][1]


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        nm.norm_ppf(0.0)
    with pytest.raises(ValueError):
        nm.t_ppf(1.0, 10)
    with pytest.raises(ValueError):
        nm.t_cdf(0.5, 0.0)
    with pytest.raises(ValueError):
        nm.nct_cdf(0.5, -1.0, 1.0)


# --------------------------------------------------------------------------
# Against SciPy -- an independent implementation, not our own
# --------------------------------------------------------------------------
@needs_scipy
def test_nct_cdf_matches_scipy():
    """Measured worst deviation: 1.7e-14 (docs/VALIDATION.md)."""
    worst = 0.0
    for df in [1, 2, 3, 4, 7, 12, 25, 53, 108, 208, 500, 2000, 10_000]:
        for ncp in [0.1, 0.5, 1.0, 2.0, 3.6, 5.0, 8.0, 15.0]:
            for t in [-4.0, -1.0, 0.0, 1.0, 1.96, 3.0, 6.0, 12.0]:
                worst = max(
                    worst, abs(nm.nct_cdf(t, df, ncp) - float(_sp.nct.cdf(t, df, ncp)))
                )
    assert worst < 1e-12, f"worst nct_cdf deviation {worst:g}"


@needs_scipy
def test_critical_values_match_scipy():
    """Accuracy where the engine actually uses t_ppf."""
    worst = 0.0
    for df in range(1, 300):
        for alpha in (0.001, 0.01, 0.05, 0.1, 0.2):
            for p in (1 - alpha, 1 - alpha / 2):
                a, b = nm.t_ppf(p, df), float(_sp.t.ppf(p, df))
                worst = max(worst, abs(a - b) / abs(b))
    assert worst < 1e-9, f"worst critical-value deviation {worst:g}"


@needs_scipy
def test_t_cdf_matches_scipy():
    """Measured worst deviation: 2.9e-14 (docs/VALIDATION.md)."""
    worst = 0.0
    for df in [1, 2, 5, 13, 60, 208, 5000, 20_000]:
        for t in [-9.0, -2.0, -0.3, 0.0, 0.7, 1.96, 4.0, 11.0]:
            worst = max(worst, abs(nm.t_cdf(t, df) - float(_sp.t.cdf(t, df))))
    assert worst < 1e-12, f"worst t_cdf deviation {worst:g}"


def _mpmath_t_ppf(mp, p: str, df: int, start: str) -> float:
    def exact_cdf(t):
        tt, d = mp.mpf(t), mp.mpf(df)
        x = d / (d + tt * tt)
        tail = mp.mpf(1) / 2 * mp.betainc(
            d / 2, mp.mpf(1) / 2, 0, x, regularized=True
        )
        return 1 - tail

    return float(mp.findroot(lambda t: exact_cdf(t) - mp.mpf(p), mp.mpf(start)))


def test_t_ppf_accuracy_against_a_50_digit_oracle():
    """Arbitration by a third oracle (mpmath at 50 digits).

    This asserts the engine's **own** accuracy, which is the only
    version-independent claim available.  At df = 75, p = 0.95 the exact
    quantile is 1.6654253733225633 and the engine lands 3.8e-15 away --
    7 orders of magnitude inside the 1e-10 that SPEC section 4 requires.

    It deliberately does **not** assert that the engine beats SciPy.  It did
    on SciPy 1.14.1 (which was 7.9e-11 off at this point), and it does not on
    the version CI installs, which is accurate to 4.4e-16.  The durable lesson
    from that episode is in docs/VALIDATION.md and it is not "we are better":
    it is that a library's accuracy is a property of its version, so an
    external library must never be the thing that bounds your own error bar.
    """
    mp = pytest.importorskip("mpmath")
    mp.mp.dps = 50
    exact = _mpmath_t_ppf(mp, "0.95", 75, "1.6654")
    mine = nm.t_ppf(0.95, 75)
    assert abs(mine - exact) < 1e-13, f"engine error {abs(mine - exact):g}"


@needs_scipy
def test_t_ppf_agrees_with_scipy_within_the_stated_tolerance():
    """Agreement, not superiority.  Either side may be the less accurate one
    depending on the installed SciPy; both are far inside what SPEC requires."""
    worst = 0.0
    for df in (1, 5, 13, 75, 208, 2000):
        for p in (0.9, 0.95, 0.975, 0.99, 0.995):
            a, b = nm.t_ppf(p, df), float(_sp.t.ppf(p, df))
            worst = max(worst, abs(a - b) / abs(b))
    assert worst < 1e-9, f"worst relative disagreement {worst:g}"
