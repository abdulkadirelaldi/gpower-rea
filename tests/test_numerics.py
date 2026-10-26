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
    "df", [1, 2, 3, 5, 10, 29, 30, 31, 37, 208, 1000, 10_000, 100_000]
)
def test_scale_density_integrates_to_one(df):
    """The quadrature panels used by nct_cdf must carry all the probability.

    df = 29/30/31 straddle the Stirling threshold inside ``_scale_params``, so
    this also pins the two branches to each other.
    """
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


def test_t_ppf_is_more_accurate_than_scipy():
    """Arbitration by a third oracle (mpmath at 50 digits).

    At df = 75, p = 0.95 the exact quantile is 1.6654253733225633.  This
    engine lands 3.8e-15 away; SciPy 1.14 lands 7.9e-11 away.  Recorded in
    docs/VALIDATION.md because the usual reflex -- "trust SciPy" -- is wrong
    here, and the critical value feeds every power number we report.
    """
    mp = pytest.importorskip("mpmath")
    mp.mp.dps = 50
    exact = _mpmath_t_ppf(mp, "0.95", 75, "1.6654")
    mine = nm.t_ppf(0.95, 75)
    assert abs(mine - exact) < 1e-13
    if _sp is not None:
        theirs = float(_sp.t.ppf(0.95, 75))
        assert abs(mine - exact) < abs(theirs - exact)
