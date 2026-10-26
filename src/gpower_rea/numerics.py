"""Self-contained numerical special functions.

Zero third-party dependencies on purpose: the engine must be importable in a
bare CPython so that the CLI, the MCP server and the agent all share exactly
one implementation of the maths (see docs/ARCHITECTURE.md, invariant I-3).

Everything here is a pure function.  Accuracy targets (verified in
tests/test_numerics.py against closed forms and, when available, SciPy):

    norm_cdf / norm_ppf      ~1e-15 absolute
    betainc (regularised)    ~1e-15 relative
    t_cdf / t_ppf            ~1e-14
    nct_cdf                  ~1e-12  (Gauss-Legendre on chi-quantile panels)
"""

from __future__ import annotations

import math
from functools import lru_cache

__all__ = [
    "norm_cdf",
    "norm_pdf",
    "norm_ppf",
    "betainc",
    "gammainc_lower",
    "chi2_cdf",
    "chi2_ppf",
    "t_cdf",
    "t_pdf",
    "t_ppf",
    "t_sf",
    "t_isf",
    "nct_cdf",
    "nct_sf",
]

_SQRT2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)
_TINY = 1e-300


# --------------------------------------------------------------------------
# Normal distribution
# --------------------------------------------------------------------------
def norm_cdf(x: float) -> float:
    """Standard normal CDF via the complementary error function."""
    return 0.5 * math.erfc(-x / _SQRT2)


def norm_pdf(x: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * x * x)


# Wichura (1988), Algorithm AS 241 -- PPND16.  |error| < 1e-16 over (0,1).
_A = (
    3.3871328727963666080e0,
    1.3314166789178437745e2,
    1.9715909503065514427e3,
    1.3731693765509461125e4,
    4.5921953931549871457e4,
    6.7265770927008700853e4,
    3.3430575583588128105e4,
    2.5090809287301226727e3,
)
_B = (
    1.0,
    4.2313330701600911252e1,
    6.8718700749205790830e2,
    5.3941960214247511077e3,
    2.1213794301586595867e4,
    3.9307895800092710610e4,
    2.8729085735721942674e4,
    5.2264952788528545610e3,
)
_C = (
    1.42343711074968357734e0,
    4.63033784615654529590e0,
    5.76949722146069140550e0,
    3.64784832476320460504e0,
    1.27045825245236838258e0,
    2.41780725177450611770e-1,
    2.27238449892691845833e-2,
    7.74545014278341407640e-4,
)
_D = (
    1.0,
    2.05319162663775882187e0,
    1.67638483018380384940e0,
    6.89767334985100004550e-1,
    1.48103976427480074590e-1,
    1.51986665636164571966e-2,
    5.47593808499534494600e-4,
    1.05075007164441684324e-9,
)
_E = (
    6.65790464350110377720e0,
    5.46378491116411436990e0,
    1.78482653991729133580e0,
    2.96560571828504891230e-1,
    2.65321895265761230930e-2,
    1.24266094738807843860e-3,
    2.71155556874348757815e-5,
    2.01033439929228813265e-7,
)
_F = (
    1.0,
    5.99832206555887937690e-1,
    1.36929880922735805310e-1,
    1.48753612908506148525e-2,
    7.86869131145613259100e-4,
    1.84631831751005468180e-5,
    1.42151175831644588870e-7,
    2.04426310338993978564e-15,
)


def _poly(coef, x: float) -> float:
    out = 0.0
    for c in reversed(coef):
        out = out * x + c
    return out


def norm_ppf(p: float) -> float:
    """Standard normal quantile (inverse CDF)."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"norm_ppf: p must be in (0,1), got {p!r}")
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        return q * _poly(_A, r) / _poly(_B, r)
    r = p if q < 0.0 else 1.0 - p
    r = math.sqrt(-math.log(r))
    if r <= 5.0:
        r -= 1.6
        val = _poly(_C, r) / _poly(_D, r)
    else:
        r -= 5.0
        val = _poly(_E, r) / _poly(_F, r)
    return -val if q < 0.0 else val


# --------------------------------------------------------------------------
# Cancellation-free log-gamma differences
#
# ``lgamma(a+b) - lgamma(a)`` is the accuracy bottleneck of every beta- and
# chi-based routine below.  Evaluated naively it subtracts two numbers of size
# ~a*ln(a); at df = 5000 those are ~1.9e4, so double rounding alone injects
# ~2e-12 of absolute error into the exponent and therefore ~2e-12 of relative
# error into the result.  Rewriting the Stirling series so that every term is
# O(1) removes it: measured t_cdf error drops from 4e-13 to ~1e-16.
# --------------------------------------------------------------------------
_HALF_LOG_2PI = 0.5 * math.log(2.0 * math.pi)
_STIRLING_MIN = 30.0


def _log_gamma_ratio(a: float, b: float) -> float:
    """ln Gamma(a+b) - ln Gamma(a) for a > 0, b >= 0."""
    if a < _STIRLING_MIN:
        return math.lgamma(a + b) - math.lgamma(a)
    ab = a + b
    out = b * math.log(a) + (ab - 0.5) * math.log1p(b / a) - b
    # Stirling corrections, each written as an expanded difference so that no
    # subtraction of nearly-equal large quantities survives.
    out -= b / (12.0 * a * ab)
    a3, ab3 = a**3, ab**3
    out += b * (3.0 * a * a + 3.0 * a * b + b * b) / (360.0 * a3 * ab3)
    a5, ab5 = a**5, ab**5
    out -= (
        b
        * (5.0 * a**4 + 10.0 * a**3 * b + 10.0 * a * a * b * b + 5.0 * a * b**3 + b**4)
        / (1260.0 * a5 * ab5)
    )
    return out


def log_beta(a: float, b: float) -> float:
    """ln B(a, b) = ln Gamma(a) + ln Gamma(b) - ln Gamma(a+b)."""
    if a < b:
        a, b = b, a
    return math.lgamma(b) - _log_gamma_ratio(a, b)


# --------------------------------------------------------------------------
# Incomplete beta  ->  central Student t
# --------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    """Modified Lentz continued fraction for the incomplete beta function."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _TINY:
        d = _TINY
    d = 1.0 / d
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _TINY:
            d = _TINY
        c = 1.0 + aa / c
        if abs(c) < _TINY:
            c = _TINY
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _TINY:
            d = _TINY
        c = 1.0 + aa / c
        if abs(c) < _TINY:
            c = _TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3.0e-16:
            break
    return h


def betainc_xy(a: float, b: float, x: float, y: float) -> float:
    """Regularised incomplete beta I_x(a, b), given 1 - x = y separately.

    Taking the complement as an argument matters.  In the Student-t tail
    ``x = df/(df+t^2)`` sits within 1e-16 of 1.0 for large df, so recovering
    ``1-x`` by subtraction destroys up to eleven significant digits -- which
    then shows up as ~5e-13 of error in ``t_cdf``.  The caller can compute
    ``y = t^2/(df+t^2)`` exactly, so it does.
    """
    if x <= 0.0:
        return 0.0
    if y <= 0.0:
        return 1.0
    log_x = math.log1p(-y) if x > 0.5 else math.log(x)
    log_y = math.log1p(-x) if y > 0.5 else math.log(y)
    front = math.exp(-log_beta(a, b) + a * log_x + b * log_y)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, y) / b


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return betainc_xy(a, b, x, 1.0 - x)


def t_cdf(t: float, df: float) -> float:
    """CDF of the central Student t distribution."""
    if df <= 0.0:
        raise ValueError("t_cdf: df must be > 0")
    if t == 0.0:
        return 0.5
    tt = t * t
    denom = df + tt
    # x and y are each computed directly from (t, df): no cancellation.
    tail = 0.5 * betainc_xy(0.5 * df, 0.5, df / denom, tt / denom)
    return 1.0 - tail if t > 0.0 else tail


def t_pdf(t: float, df: float) -> float:
    if df <= 0.0:
        raise ValueError("t_pdf: df must be > 0")
    lg = (
        math.lgamma(0.5 * (df + 1.0))
        - math.lgamma(0.5 * df)
        - 0.5 * math.log(df * math.pi)
    )
    return math.exp(lg - 0.5 * (df + 1.0) * math.log1p(t * t / df))


#: Above this, t*t overflows a double (sqrt(DBL_MAX) is about 1.34e154), so
#: the survival function switches to its asymptotic form.
_T_SQUARE_SAFE = 1e120


def _log_t_sf_asymptotic(t: float, df: float) -> float:
    """log P(T > t) for t so large that t*t is not representable.

    With x = df/(df+t^2) small, I_x(a, b) -> x^a / (a * B(a, b)), so

        log P(T > t) = (df/2)*(log df - 2 log t) - log df - log B(df/2, 1/2)

    The relative error of dropping the next term is O(df/t^2), i.e. below
    1e-200 at the threshold where this branch is used.
    """
    return (
        0.5 * df * (math.log(df) - 2.0 * math.log(t))
        - math.log(df)
        - log_beta(0.5 * df, 0.5)
    )


def t_sf(t: float, df: float) -> float:
    """Survival function P(T > t) of the central Student t distribution.

    Computed from the tail directly, and with an asymptotic branch for huge
    ``t``: squaring 1e200 overflows, after which every downstream quantity is
    silently garbage.  That mattered -- it made ``t_isf`` return a
    plausible-looking wrong quantile for a tiny tail probability with small
    ``df``.
    """
    if df <= 0.0:
        raise ValueError("t_sf: df must be > 0")
    if t == 0.0:
        return 0.5
    if abs(t) > _T_SQUARE_SAFE:
        lg = _log_t_sf_asymptotic(abs(t), df)
        tail = math.exp(lg) if lg > -745.0 else 0.0
        return tail if t > 0.0 else 1.0 - tail
    tt = t * t
    denom = df + tt
    tail = 0.5 * betainc_xy(0.5 * df, 0.5, df / denom, tt / denom)
    return tail if t > 0.0 else 1.0 - tail


def t_isf(q: float, df: float) -> float:
    """Upper-tail quantile: the t with P(T > t) = q.

    This, not :func:`t_ppf`, is the right-conditioned way to obtain a critical
    value.  ``t_ppf(1 - alpha/2)`` has to form ``1 - alpha/2``, which loses
    every significant digit of a small alpha and rounds to exactly 1.0 below
    about 1e-16 -- and the criterion analysis reaches alpha ~ 1e-60 routinely
    (SPEC F-13 item 5).  Working from the tail probability never forms that
    difference.
    """
    if not (0.0 < q < 1.0):
        raise ValueError(f"t_isf: q must be in (0,1), got {q!r}")
    if df <= 0.0:
        raise ValueError("t_isf: df must be > 0")
    if q == 0.5:
        return 0.0
    if q > 0.5:
        # 1 - q is well conditioned here: q > 0.5 means it keeps full
        # relative precision.
        return -t_isf(1.0 - q, df)

    # Starting point.  Inverting the asymptotic tail is the only thing that
    # gets close when q is tiny and df is small -- there the quantile is
    # enormous (df = 0.05, q = 0.025 puts it near 1e26) and a Cornish-Fisher
    # expansion around the normal quantile is nowhere near.
    log_asym = (
        0.5 * (math.log(df) - (2.0 / df) * (math.log(q) + math.log(df)
                                            + log_beta(0.5 * df, 0.5)))
    )
    if log_asym > 709.0:
        raise ValueError(
            f"t_isf: the upper q={q!r} quantile of t with df={df!r} exceeds "
            f"the range of a double (it is about exp({log_asym:.1f}))"
        )
    z = -norm_ppf(q)
    z3, z5, z7 = z**3, z**5, z**7
    cf = (
        z
        + (z3 + z) / (4.0 * df)
        + (5.0 * z5 + 16.0 * z3 + 3.0 * z) / (96.0 * df * df)
        + (3.0 * z7 + 19.0 * z5 + 17.0 * z3 - 15.0 * z) / (384.0 * df**3)
    )
    asym = math.exp(log_asym) if log_asym < 709.0 else math.inf
    # The asymptotic form is the better guess once it exceeds the
    # Cornish-Fisher one, which is exactly the regime it is meant for.
    t = max(cf, 1e-6) if cf >= asym else asym

    lo, hi = 0.0, max(2.0 * t, 2.0)
    while t_sf(hi, df) > q:
        hi *= 2.0
        if hi > 1e300:
            raise ValueError(
                f"t_isf: the upper q={q!r} quantile of t with df={df!r} "
                f"exceeds the range of a double"
            )
    if not (lo < t < hi):
        t = 0.5 * (lo + hi)

    for _ in range(200):
        f = t_sf(t, df) - q
        if f < 0.0:
            hi = t
        else:
            lo = t
        d = t_pdf(t, df)
        nxt = t + f / d if d > 0.0 else 0.5 * (lo + hi)
        if not (lo < nxt < hi):
            nxt = 0.5 * (lo + hi)
        if abs(nxt - t) <= 1e-15 * max(1.0, abs(t)):
            return nxt
        t = nxt
    return t


def t_ppf(p: float, df: float) -> float:
    """Quantile of the central Student t distribution.

    Cornish-Fisher start, then safeguarded Newton (bisection fallback).  For a
    critical value prefer :func:`t_isf`, which takes the tail probability and
    so stays accurate for a tiny alpha.
    """
    if not (0.0 < p < 1.0):
        raise ValueError(f"t_ppf: p must be in (0,1), got {p!r}")
    if df <= 0.0:
        raise ValueError("t_ppf: df must be > 0")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -t_isf(p, df)

    z = norm_ppf(p)
    z3, z5, z7 = z**3, z**5, z**7
    t = (
        z
        + (z3 + z) / (4.0 * df)
        + (5.0 * z5 + 16.0 * z3 + 3.0 * z) / (96.0 * df * df)
        + (3.0 * z7 + 19.0 * z5 + 17.0 * z3 - 15.0 * z) / (384.0 * df**3)
    )
    lo, hi = 0.0, max(2.0 * max(t, 1.0), 2.0)
    while t_cdf(hi, df) < p:
        hi *= 2.0
        if hi > 1e300:
            # The root is outside the double range.  This happens for a tiny
            # df with a small tail probability -- the t tail decays like
            # t**(-df), so for df = 0.05 the 0.005 quantile is about 1e60**4.
            # Bisecting an unbracketed interval would return a plausible-looking
            # wrong number, so refuse instead.  (Latent defect found while
            # extending the quadrature below df = 1.)
            raise ValueError(
                f"t_ppf: the p={p!r} quantile of t with df={df!r} exceeds the "
                f"range of a double; the critical value is not representable"
            )
    if not (lo < t < hi):
        t = 0.5 * (lo + hi)

    for _ in range(200):
        f = t_cdf(t, df) - p
        if f > 0.0:
            hi = t
        else:
            lo = t
        d = t_pdf(t, df)
        nxt = t - f / d if d > 0.0 else 0.5 * (lo + hi)
        if not (lo < nxt < hi):
            nxt = 0.5 * (lo + hi)
        if abs(nxt - t) <= 1e-15 * max(1.0, abs(t)):
            return nxt
        t = nxt
    return t


# --------------------------------------------------------------------------
# Incomplete gamma  ->  chi-square
# --------------------------------------------------------------------------
def gammainc_lower(a: float, x: float) -> float:
    """Regularised lower incomplete gamma P(a, x)."""
    if a <= 0.0:
        raise ValueError("gammainc_lower: a must be > 0")
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        ap = a
        total = 1.0 / a
        term = total
        for _ in range(2000):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-17:
                break
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1.0 - a
    c = 1.0 / _TINY
    d = 1.0 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _TINY:
            d = _TINY
        c = b + an / c
        if abs(c) < _TINY:
            c = _TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-17:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1.0 - q


def chi2_cdf(x: float, df: float) -> float:
    if df <= 0.0:
        raise ValueError("chi2_cdf: df must be > 0")
    return gammainc_lower(0.5 * df, 0.5 * x)


def chi2_ppf(p: float, df: float) -> float:
    """Chi-square quantile; Wilson-Hilferty start then bracketed bisection."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"chi2_ppf: p must be in (0,1), got {p!r}")
    z = norm_ppf(p)
    guess = df * (1.0 - 2.0 / (9.0 * df) + z * math.sqrt(2.0 / (9.0 * df))) ** 3
    if not math.isfinite(guess) or guess <= 0.0:
        guess = max(df, 1e-6)

    lo = guess * 0.5
    while lo > 1e-300 and chi2_cdf(lo, df) > p:
        lo *= 0.5
    if lo <= 1e-300:
        lo = 1e-300
    hi = max(guess * 2.0, lo * 2.0)
    while chi2_cdf(hi, df) < p:
        hi *= 2.0
        if hi > 1e300:
            return hi

    # Pure bisection to full double precision: the bracket is halved until the
    # midpoint coincides with an endpoint.  A relative tolerance would lose
    # accuracy in the far tails, where the quantile itself is tiny.
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid <= lo or mid >= hi:
            break
        if chi2_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------
# Gauss-Legendre nodes (generated once per order, then cached)
# --------------------------------------------------------------------------
@lru_cache(maxsize=16)
def _gauss_legendre(n: int):
    xs = [0.0] * n
    ws = [0.0] * n
    m = (n + 1) // 2
    for i in range(m):
        z = math.cos(math.pi * (i + 0.75) / (n + 0.5))
        dp = 1.0
        for _ in range(100):
            p0, p1 = 1.0, 0.0
            for j in range(1, n + 1):
                p2, p1 = p1, p0
                p0 = ((2.0 * j - 1.0) * z * p1 - (j - 1.0) * p2) / j
            dp = n * (z * p0 - p1) / (z * z - 1.0)
            z_new = z - p0 / dp
            if abs(z_new - z) < 1e-16:
                z = z_new
                break
            z = z_new
        w = 2.0 / ((1.0 - z * z) * dp * dp)
        xs[i], xs[n - 1 - i] = -z, z
        ws[i] = ws[n - 1 - i] = w
    return tuple(xs), tuple(ws)


# Quantile levels used to cut the chi-quantile integration domain into panels.
_PANEL_LEVELS = (
    1e-14,
    1e-10,
    1e-7,
    1e-4,
    1e-2,
    5e-2,
    0.15,
    0.30,
    0.50,
    0.70,
    0.85,
    0.95,
    0.99,
    1.0 - 1e-4,
    1.0 - 1e-7,
    1.0 - 1e-10,
    1.0 - 1e-14,
)

_GL_ORDER = 24


@lru_cache(maxsize=4096)
def _scale_panels(df: float):
    """Panel edges for S = sqrt(V/df), V ~ chi2(df)."""
    edges = [0.0]
    for q in _PANEL_LEVELS:
        edges.append(math.sqrt(chi2_ppf(q, df) / df))
    out = []
    for lo, hi in zip(edges, edges[1:]):
        if hi > lo:
            out.append((lo, hi))
    return tuple(out)


@lru_cache(maxsize=4096)
def _log_scale_params(df: float) -> tuple[float, float]:
    """Constants of the mixing density in ``y = log s``.

    The mixture representation integrates over `S = sqrt(V/df)`.  Substituting
    `y = log s` gives, with `a = df/2`,

        log h(y) = L0 - a * (expm1(2y) - 2y),   L0 = log h(0)

    which has three properties the `s`-space form lacks:

    * the mode sits at `y = 0` for **every** `df > 0`;
    * the `s**(df-1)` endpoint singularity (integrable but unresolvable by
      Gauss-Legendre for `df < 1`) becomes an entire function;
    * `expm1(2y) - 2y` is exactly 0 at the mode and `O(y**2)` around it, so no
      term in the exponent is a difference of large nearly-equal numbers.

    The second property is what matters for correctness: in `s` space the
    quadrature silently lost accuracy below `df = 1` (measured: power 0.252
    where the true answer was 0.100).
    """
    a = 0.5 * df
    if a >= _STIRLING_MIN:
        corr = (
            1.0 / (12.0 * a)
            - 1.0 / (360.0 * a**3)
            + 1.0 / (1260.0 * a**5)
            - 1.0 / (1680.0 * a**7)
        )
        l0 = math.log(2.0) - _HALF_LOG_2PI + 0.5 * math.log(a) - corr
    else:
        l0 = math.log(2.0) + a * math.log(a) - math.lgamma(a) - a
    return a, l0


def _log_h(y: float, a: float, l0: float) -> float:
    """log of the mixing density at ``y = log s``."""
    return l0 - a * (math.expm1(2.0 * y) - 2.0 * y)


#: Depth of the log-density ladder used to place quadrature panels.  Panels are
#: delimited by the points where the log-density has fallen this far below its
#: mode, which concentrates nodes where the mass is for every df.
_PANEL_LEVELS_LOG = (
    0.02, 0.1, 0.35, 1.0, 2.2, 4.5, 9.0, 18.0, 36.0, 75.0, 160.0, 350.0, 720.0,
)


def _solve_level(level: float, a: float, negative: bool) -> float:
    """Find y on one side of the mode where a*(expm1(2y) - 2y) == level."""

    def q(y: float) -> float:
        return a * (math.expm1(2.0 * y) - 2.0 * y)

    if negative:
        lo, hi = -1e-9, -1e-9
        step = max(1.0, 0.5 * level / a)
        hi = -1e-12
        lo = -step
        while q(lo) < level:
            lo *= 2.0
            if lo < -1e7:
                break
    else:
        lo, hi = 1e-12, max(1e-9, 0.5 * math.log1p(level / a + 1.0) + 1.0)
        while q(hi) < level:
            hi *= 2.0
            if hi > 1e4:
                break
        lo = 1e-12
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid == lo or mid == hi:
            break
        if (q(mid) < level) == (not negative):
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@lru_cache(maxsize=4096)
def _log_scale_panels(df: float) -> tuple[tuple[float, float], ...]:
    """Panel edges in ``y`` space, delimited by log-density level sets."""
    a, _ = _log_scale_params(df)
    left = [_solve_level(lv, a, True) for lv in reversed(_PANEL_LEVELS_LOG)]
    right = [_solve_level(lv, a, False) for lv in _PANEL_LEVELS_LOG]
    edges = left + [0.0] + right
    out = []
    for lo, hi in zip(edges, edges[1:]):
        if hi > lo:
            out.append((lo, hi))
    return tuple(out)


#: Where Phi(x) does its work.  The integrand of the mixture representation is
#: Phi(t*exp(y) - ncp) times a smooth density; Phi is flat outside roughly
#: +/- 8 and turns over sharply inside it.  Gauss-Legendre cannot resolve that
#: turn if it falls in the middle of a wide panel -- which is exactly what
#: happens for a huge critical value, where the turn sits far out in the
#: left tail of the density.  So the turn gets its own breakpoints.
_PHI_LEVELS = (-8.0, -4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0, 8.0)


def _panels_with_phi_transition(
    df: float, t: float, ncp: float
) -> tuple[tuple[float, float], ...]:
    """Density-level panels, refined where Phi(t*exp(y) - ncp) turns over."""
    base = _log_scale_panels(df)
    if t == 0.0:
        return base
    lo_edge, hi_edge = base[0][0], base[-1][1]
    cuts = set()
    for level in _PHI_LEVELS:
        arg = (level + ncp) / t
        if arg <= 0.0:
            continue
        y = math.log(arg)
        if lo_edge < y < hi_edge:
            cuts.add(y)
    if not cuts:
        return base
    edges = sorted({lo_edge, hi_edge, *(e for p in base for e in p), *cuts})
    return tuple(
        (a, b) for a, b in zip(edges, edges[1:]) if b > a
    )


@lru_cache(maxsize=4096)
def _scale_params(df: float) -> tuple[float, float, bool]:
    """Pre-computed constants for the density of S = sqrt(V/df), V ~ chi2(df).

    Exactly, with a = df/2:

        log g(s) = log 2 + a*log(a) - lgamma(a) + (2a-1)*log(s) - a*s^2

    For large a, ``a*log(a) - lgamma(a)`` is a difference of huge nearly-equal
    terms, and so is the rest of the expression at s ~ 1.  Substituting the
    Stirling series and collecting gives the algebraically identical

        log g(s) = [log 2 - 0.5*log(2*pi) + 0.5*log(a) - corr - log s]
                   + a * (1 + 2*log s - s^2)

    in which the bracket is O(1) and the second factor is O((s-1)^2), so the
    only remaining cancellation is benign.
    """
    a = 0.5 * df
    if a >= _STIRLING_MIN:
        corr = (
            1.0 / (12.0 * a)
            - 1.0 / (360.0 * a**3)
            + 1.0 / (1260.0 * a**5)
            - 1.0 / (1680.0 * a**7)
        )
        base = math.log(2.0) - _HALF_LOG_2PI + 0.5 * math.log(a) - corr
        return a, base, True
    return a, math.log(2.0) + a * math.log(a) - math.lgamma(a), False


def _scale_pdf(s: float, params: tuple[float, float, bool]) -> float:
    """Density of S = sqrt(V/df) with V ~ chi2(df)."""
    if s <= 0.0:
        return 0.0
    a, base, stirling = params
    if stirling:
        u = s - 1.0
        # h(s) = 1 + 2*log(s) - s^2, written so that it is exactly 0 at s = 1.
        h = 2.0 * math.log1p(u) - u * (u + 2.0)
        lg = base - math.log(s) + a * h
    else:
        lg = base + (2.0 * a - 1.0) * math.log(s) - a * s * s
    if lg < -745.0:
        return 0.0
    return math.exp(lg)


def _nct_mixture(t: float, df: float, ncp: float, upper: bool) -> float:
    """Shared quadrature for the noncentral t CDF and survival function.

    ``upper=False`` integrates ``Phi(t*s - ncp)`` and gives ``P(T <= t)``;
    ``upper=True`` integrates ``Phi(ncp - t*s)`` and gives ``P(T > t)``.
    """
    a, l0 = _log_scale_params(df)
    nodes, weights = _gauss_legendre(_GL_ORDER)
    total = 0.0
    for lo, hi in _panels_with_phi_transition(df, t, ncp):
        half = 0.5 * (hi - lo)
        mid = 0.5 * (hi + lo)
        acc = 0.0
        for x, w in zip(nodes, weights):
            y = mid + half * x
            lh = _log_h(y, a, l0)
            if lh < -745.0:
                continue
            ts = t * math.exp(y)
            acc += w * math.exp(lh) * norm_cdf(ncp - ts if upper else ts - ncp)
        total += half * acc
    if total < 0.0:
        return 0.0
    if total > 1.0:
        return 1.0
    return total


def nct_sf(t: float, df: float, ncp: float) -> float:
    """Survival function P(T > t) of the noncentral Student t distribution.

    Computed directly, as ``E_S[Phi(ncp - t*S)]``, and **not** as
    ``1 - nct_cdf(t)``.  The difference is a sum of positive terms versus a
    subtraction from 1: when the answer is small -- a one-tailed test pointed
    the wrong way has power 7.7e-06, and an alpha of 1e-12 makes the size
    itself tiny -- the subtraction keeps only absolute accuracy, while this
    keeps relative accuracy.  Power is exactly this quantity (SPEC F-02), so
    the distinction is not academic.
    """
    if df <= 0.0:
        raise ValueError("nct_sf: df must be > 0")
    if ncp == 0.0:
        return t_sf(t, df)
    if df > 1e8:  # degenerate limit, S -> 1
        return norm_cdf(ncp - t)
    return _nct_mixture(t, df, ncp, upper=True)


def nct_cdf(t: float, df: float, ncp: float) -> float:
    """CDF of the noncentral Student t distribution.

    Uses the exact mixture representation

        P(T <= t) = E_S[ Phi(t * S - ncp) ],      S = sqrt(V/df), V ~ chi2(df)

    which follows from T = (Z + ncp) / S with Z ~ N(0,1) independent of V.
    The expectation is evaluated with 24-point Gauss-Legendre quadrature on
    panels delimited by chi-square quantiles, so the integrand is smooth and
    well resolved for every df from 1 upward.
    """
    if df <= 0.0:
        raise ValueError("nct_cdf: df must be > 0")
    if ncp == 0.0:
        return t_cdf(t, df)
    if df > 1e8:  # degenerate limit, S -> 1
        return norm_cdf(t - ncp)

    return _nct_mixture(t, df, ncp, upper=False)
