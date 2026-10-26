"""The single power routine of the family (SPEC.md F-01, F-02) and the
critical-value / compromise primitives (F-10).

F-01: every test in the family reduces to a pair ``(nu, delta)``; power,
critical value, required N, required alpha and the detectable effect size are
all functions of ``(nu, delta, alpha, k)`` only.  Hence exactly one power
routine lives here and the test definitions supply nothing but ``(nu, delta)``.
"""

from __future__ import annotations

from ._numerics import _clip01, nct_cdf, nct_sf, student_t_isf, student_t_sf

__all__ = [
    "critical_t",
    "power",
    "power_at_critical",
    "alpha_from_critical",
    "beta_from_critical",
    "power_and_beta",
]


def critical_t(alpha: float, nu: float, tails: int) -> float:
    """The central-t critical value the test rejects beyond.

    ``k = 1`` -> ``t_{1-alpha, nu}``;  ``k = 2`` -> ``t_{1-alpha/2, nu}``.
    """
    if tails not in (1, 2):
        raise ValueError("tails must be 1 or 2")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1)")
    p = alpha if tails == 1 else 0.5 * alpha
    return student_t_isf(p, nu)


def power(nu: float, delta: float, alpha: float, tails: int) -> float:
    """SPEC.md F-02, verbatim, including the far-tail term for ``k = 2``.

        k = 1:  1-beta = 1 - T(t_{1-alpha,nu};   nu, delta)
        k = 2:  1-beta = 1 - T(t_{1-alpha/2,nu}; nu, delta)
                         + T(-t_{1-alpha/2,nu};  nu, delta)

    Both pieces are evaluated directly (never as ``1 - something``), so at
    ``delta = 0`` the two-tailed expression returns exactly ``alpha``.
    """
    return power_at_critical(nu, delta, critical_t(alpha, nu, tails), tails)


def power_at_critical(nu: float, delta: float, c: float, tails: int) -> float:
    """Power for a test that rejects beyond the critical value ``c``."""
    if tails == 1:
        return nct_sf(c, nu, delta)
    return _clip01(nct_sf(c, nu, delta) + nct_cdf(-c, nu, delta))


def alpha_from_critical(nu: float, c: float, tails: int) -> float:
    """SPEC.md F-10: ``alpha(c) = 1 - T(c;nu)`` (k=1) or ``2*(1 - T(c;nu))`` (k=2)."""
    s = student_t_sf(c, nu)
    return s if tails == 1 else 2.0 * s


def beta_from_critical(nu: float, delta: float, c: float, tails: int) -> float:
    """SPEC.md F-10: ``beta(c) = T(c;nu,delta)`` (k=1) or
    ``T(c;nu,delta) - T(-c;nu,delta)`` (k=2).

    The second form is the exact complement of F-02's two-tailed power
    expression, far-tail term included.  Whichever of the two algebraically
    equal routes is better conditioned is used.
    """
    return power_and_beta(nu, delta, c, tails)[1]


def power_and_beta(nu: float, delta: float, c: float, tails: int) -> tuple[float, float]:
    """``(1-beta, beta)`` at critical value ``c``, exactly complementary.

    Both quantities are available as a sum of positive terms; the smaller of
    the two is the well-conditioned one, so it is computed directly and the
    other is its complement.
    """
    if tails == 1:
        pw = nct_sf(c, nu, delta)
        bt = nct_cdf(c, nu, delta)
    else:
        pw = _clip01(nct_sf(c, nu, delta) + nct_cdf(-c, nu, delta))
        bt = _clip01(nct_cdf(c, nu, delta) - nct_cdf(-c, nu, delta))
    if pw <= bt:
        return pw, 1.0 - pw
    return 1.0 - bt, bt
