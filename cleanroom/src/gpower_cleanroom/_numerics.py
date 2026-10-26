"""Numerical core: special functions, Gauss-Legendre quadrature, and the
central / noncentral Student-t distribution functions.

Everything here is standard library only (``math``).

Design notes (driven by SPEC.md section 4):

*   The noncentral t CDF is evaluated as the **mixture**

        T(x; nu, delta) = E_S[ Phi(x*S - delta) ],    S = sqrt(V/nu), V ~ chi^2_nu

    with Gauss-Legendre panels, *not* as a series.

*   The survival function is evaluated as ``E_S[Phi(delta - x*S)]`` -- a sum of
    strictly positive terms -- so that ``1 - T`` is never recovered by
    subtraction.  This is the first of the two cancellation sources SPEC.md
    section 4 warns about (it is what makes the two-tailed power expression of
    F-02 stable, since both of its terms are then computed directly).

*   ``lgamma(a+b) - lgamma(a)`` is never formed by subtracting two ``lgamma``
    values.  :func:`log_gamma_ratio` rewrites the Stirling series so every term
    is O(1).  The same trick normalises the mixing density (:func:`_log_weight_const`).

*   ``1 - nu/(nu+t^2)`` is never formed by subtraction: the complement
    ``t^2/(nu+t^2)`` is used directly, via ``log1p(t*t/nu)``.

*   The integration variable is ``y = log s``.  In that variable the mixing
    measure has log-density ``K(nu) + a*g(e^y)`` with ``g(s) = 1 - s^2 + 2 log s``
    and ``a = nu/2``; its mode is at ``y = 0`` for *every* ``nu > 0`` and the
    integrand is entire.  This removes the ``s^(nu-1)`` endpoint singularity
    that plagues integration in ``s`` for ``nu < 2``, and it makes the
    exponent a sum of O(1) terms for large ``nu``.
"""

from __future__ import annotations

import math

__all__ = [
    "stirling_remainder",
    "log_gamma_ratio",
    "norm_cdf",
    "norm_sf",
    "norm_ppf",
    "gauss_legendre",
    "weight_mass",
    "nct_cdf",
    "nct_sf",
    "student_t_cdf",
    "student_t_sf",
    "student_t_logpdf",
    "student_t_pdf",
    "student_t_isf",
    "student_t_ppf",
]

_SQRT2 = math.sqrt(2.0)
_LOG_SQRT_2PI = 0.5 * math.log(2.0 * math.pi)
_LOG2 = math.log(2.0)


# ---------------------------------------------------------------------------
# log-gamma machinery with the cancellation removed
# ---------------------------------------------------------------------------

# S(z) = sum_{n>=1} B_{2n} / (2n(2n-1) z^(2n-1))
_STIRLING = (
    1.0 / 12.0,
    -1.0 / 360.0,
    1.0 / 1260.0,
    -1.0 / 1680.0,
    1.0 / 1188.0,
    -691.0 / 360360.0,
    1.0 / 156.0,
    -3617.0 / 122400.0,
)

_STIRLING_MIN = 12.0


def stirling_remainder(z: float) -> float:
    """``lgamma(z) - ((z-0.5)*log(z) - z + 0.5*log(2*pi))`` for ``z >= 12``.

    Every term of the series is O(1) or smaller, so no cancellation occurs.
    """
    zi = 1.0 / z
    z2 = zi * zi
    p = zi
    s = 0.0
    for c in _STIRLING:
        s += c * p
        p *= z2
    return s


def log_gamma_ratio(a: float, b: float) -> float:
    """``lgamma(a+b) - lgamma(a)`` without forming the difference.

    ``a > 0``, ``b >= 0``.  Accurate to a few ulp of the *result* even when
    ``a`` is large (direct subtraction of two ``lgamma`` values loses
    ``a*log(a)*eps``, which is ~2e-12 at ``a = 2500``).
    """
    if b == 0.0:
        return 0.0
    if a <= 0.0:
        raise ValueError("log_gamma_ratio requires a > 0")
    corr = 0.0
    A = a
    while A < _STIRLING_MIN:
        # diff(A, b) = diff(A+1, b) - log1p(b/A)
        corr -= math.log1p(b / A)
        A += 1.0
    # lgamma(A+b) - lgamma(A), all terms O(1) except the honest b*log(A+b)
    d = (
        (A - 0.5) * math.log1p(b / A)
        + b * math.log(A + b)
        - b
        + stirling_remainder(A + b)
        - stirling_remainder(A)
    )
    return d + corr


# ---------------------------------------------------------------------------
# normal distribution
# ---------------------------------------------------------------------------


def norm_cdf(z: float) -> float:
    """Standard normal CDF, via ``erfc`` (good relative accuracy in both tails)."""
    return 0.5 * math.erfc(-z / _SQRT2)


def norm_sf(z: float) -> float:
    """Standard normal survival function."""
    return 0.5 * math.erfc(z / _SQRT2)


_PPF_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_PPF_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_PPF_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_PPF_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)


def norm_ppf(p: float) -> float:
    """Standard normal quantile.  Rational start plus Halley polish."""
    if not (0.0 < p < 1.0):
        raise ValueError("norm_ppf requires 0 < p < 1")
    plow = 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((_PPF_C[0] * q + _PPF_C[1]) * q + _PPF_C[2]) * q + _PPF_C[3]) * q
              + _PPF_C[4]) * q + _PPF_C[5]) / (
            (((_PPF_D[0] * q + _PPF_D[1]) * q + _PPF_D[2]) * q + _PPF_D[3]) * q + 1.0)
    elif p <= 1.0 - plow:
        q = p - 0.5
        r = q * q
        x = (((((_PPF_A[0] * r + _PPF_A[1]) * r + _PPF_A[2]) * r + _PPF_A[3]) * r
              + _PPF_A[4]) * r + _PPF_A[5]) * q / (
            ((((_PPF_B[0] * r + _PPF_B[1]) * r + _PPF_B[2]) * r + _PPF_B[3]) * r
             + _PPF_B[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log1p(-p))
        x = -(((((_PPF_C[0] * q + _PPF_C[1]) * q + _PPF_C[2]) * q + _PPF_C[3]) * q
               + _PPF_C[4]) * q + _PPF_C[5]) / (
            (((_PPF_D[0] * q + _PPF_D[1]) * q + _PPF_D[2]) * q + _PPF_D[3]) * q + 1.0)
    # Halley refinement on Phi(x) = p, done in the tail that is well scaled.
    for _ in range(3):
        if x * x * 0.5 > 690.0:
            break
        if x < 0.0:
            e = norm_cdf(x) - p
        else:
            e = (1.0 - p) - norm_sf(x)
        u = e * math.sqrt(2.0 * math.pi) * math.exp(0.5 * x * x)
        x -= u / (1.0 + 0.5 * x * u)
    return x


# ---------------------------------------------------------------------------
# Gauss-Legendre nodes / weights
# ---------------------------------------------------------------------------

_GL_CACHE: dict[int, tuple[tuple[float, ...], tuple[float, ...]]] = {}


def gauss_legendre(n: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Nodes and weights of the ``n``-point Gauss-Legendre rule on ``[-1, 1]``."""
    cached = _GL_CACHE.get(n)
    if cached is not None:
        return cached
    if n < 1:
        raise ValueError("n must be >= 1")
    xs = [0.0] * n
    ws = [0.0] * n
    m = (n + 1) // 2
    for i in range(m):
        x = math.cos(math.pi * (i + 0.75) / (n + 0.5))
        dp = 1.0
        for _ in range(200):
            p0 = 1.0
            p1 = 0.0
            for j in range(n):
                p2 = p1
                p1 = p0
                p0 = ((2 * j + 1) * x * p1 - j * p2) / (j + 1)
            dp = n * (x * p0 - p1) / (x * x - 1.0)
            dx = p0 / dp
            x -= dx
            if abs(dx) <= 1e-17 * max(1.0, abs(x)):
                break
        w = 2.0 / ((1.0 - x * x) * dp * dp)
        xs[i] = -x
        xs[n - 1 - i] = x
        ws[i] = w
        ws[n - 1 - i] = w
    out = (tuple(xs), tuple(ws))
    _GL_CACHE[n] = out
    return out


# ---------------------------------------------------------------------------
# mixing measure of S = sqrt(chi^2_nu / nu), in the variable y = log s
# ---------------------------------------------------------------------------


def _q(y: float) -> float:
    """``expm1(2y) - 2y``, with the cancellation at ``y -> 0`` removed.

    ``-a*_q(y)`` is ``a*g(e^y)`` with ``g(s) = 1 - s^2 + 2*log s``; it is <= 0
    with its maximum (zero) at ``y = 0``.
    """
    u = 2.0 * y
    if -0.5 <= u <= 0.5:
        # sum_{k>=2} u^k/k!  ==  u^2 * sum_{j>=0} u^j/(j+2)!
        # Truncated at j = 15; the next term is < 1e-20 relative for |u| <= 0.5.
        return u * u * (
            5.000000000000000e-01 + u * (
            1.666666666666667e-01 + u * (
            4.166666666666666e-02 + u * (
            8.333333333333333e-03 + u * (
            1.388888888888889e-03 + u * (
            1.984126984126984e-04 + u * (
            2.480158730158730e-05 + u * (
            2.755731922398589e-06 + u * (
            2.755731922398589e-07 + u * (
            2.505210838544172e-08 + u * (
            2.087675698786810e-09 + u * (
            1.605904383682161e-10 + u * (
            1.147074559772972e-11 + u * (
            7.647163731819816e-13 + u * (
            4.779477332387385e-14 + u * 2.811457254345521e-15)))))))))))))))
    return math.expm1(u) - u


def _log_weight_const(a: float) -> float:
    """``K`` with ``log(f_S(e^y) * e^y) = K - a*_q(y)``, ``a = nu/2``."""
    if a >= _STIRLING_MIN:
        # a*log a - lgamma(a) - a  ==  0.5*log a - 0.5*log(2pi) - S(a)
        return 0.5 * math.log(a) + _LOG2 - _LOG_SQRT_2PI - stirling_remainder(a)
    return a * math.log(a) + _LOG2 - math.lgamma(a) - a


# Panel boundaries are placed on level sets of the mixing log-density.
# exp(-72) ~ 5.4e-32, far below every tolerance in SPEC.md section 4.
_LEVELS = (0.5, 1.5, 4.0, 10.0, 24.0, 48.0, 72.0)

_LEVEL_CACHE: dict[tuple[float, tuple[float, ...]], tuple[float, ...]] = {}


def _solve_level(w: float) -> tuple[float, float]:
    """Both solutions of ``_q(y) = w`` (``w > 0``): one positive, one negative."""
    # positive branch: _q is increasing on (0, inf)
    hi = max(math.sqrt(2.0 * w), 1e-12)
    while _q(hi) < w:
        hi *= 2.0
    lo = 0.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _q(mid) < w:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * max(1.0, hi):
            break
    yp = 0.5 * (lo + hi)
    # negative branch: _q is increasing as y decreases
    hi2 = 0.0
    lo2 = -max(0.5 * (w + 1.0), math.sqrt(2.0 * w), 1e-12)
    while _q(lo2) < w:
        lo2 *= 2.0
    for _ in range(80):
        mid = 0.5 * (lo2 + hi2)
        if _q(mid) < w:
            hi2 = mid
        else:
            lo2 = mid
        if hi2 - lo2 <= 1e-12 * max(1.0, -lo2):
            break
    yn = 0.5 * (lo2 + hi2)
    return yp, yn


def _level_points(nu: float, levels: tuple[float, ...]) -> tuple[float, ...]:
    key = (nu, levels)
    hit = _LEVEL_CACHE.get(key)
    if hit is not None:
        return hit
    a = 0.5 * nu
    pts = [0.0]
    for d in levels:
        yp, yn = _solve_level(d / a)
        pts.append(yp)
        pts.append(yn)
    pts.sort()
    out = tuple(pts)
    if len(_LEVEL_CACHE) > 8192:
        _LEVEL_CACHE.clear()
    _LEVEL_CACHE[key] = out
    return out


_MODE_MASS = 0
_MODE_CDF = 1
_MODE_SF = 2

_PHI_OFFSETS = (
    0.0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 2.0, -2.0, 3.0, -3.0,
    4.0, -4.0, 6.0, -6.0, 9.0, -9.0, 13.0, -13.0,
)
_SIGMA_OFFSETS = (
    0.0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0, 4.0, -4.0,
    6.0, -6.0, 8.0, -8.0, 11.0, -11.0,
)


def _panels(nu: float, x: float, delta: float, width_factor: float,
            levels: tuple[float, ...]) -> list[tuple[float, float]]:
    sigma = 1.0 / math.sqrt(2.0 * nu)
    lv = _level_points(nu, levels)
    ylo = lv[0]
    yhi = lv[-1]
    pts = list(lv)
    if x != 0.0:
        # mode of the *product* integrand for the central-like case; the
        # Phi factor pulls the mass away from y = 0 when |x| is large.
        # -0.5*log1p(x^2/nu) written via hypot so that x^2 cannot overflow.
        ystar = -math.log(math.hypot(1.0, x / math.sqrt(nu)))
        if abs(ystar) > sigma:
            ext = ystar - 11.0 * sigma
            if ext < ylo:
                ylo = ext
            for j in _SIGMA_OFFSETS:
                pts.append(ystar + j * sigma)
        # resolve the Phi transition: x*s - delta = w
        for w in _PHI_OFFSETS:
            v = (delta + w) / x
            if v > 0.0:
                pts.append(math.log(v))
    pts = [p for p in pts if ylo < p < yhi]
    pts.append(ylo)
    pts.append(yhi)
    pts.sort()
    bp = [pts[0]]
    for p in pts[1:]:
        if p - bp[-1] > 1e-13 * max(1.0, abs(p)):
            bp.append(p)

    maxw = width_factor * sigma
    while True:
        n_tot = 0
        for i in range(len(bp) - 1):
            n_tot += min(32, int((bp[i + 1] - bp[i]) / maxw) + 1)
        if n_tot <= 600:
            break
        maxw *= 2.0

    panels: list[tuple[float, float]] = []
    for i in range(len(bp) - 1):
        p0 = bp[i]
        p1 = bp[i + 1]
        ns = min(32, int((p1 - p0) / maxw) + 1)
        step = (p1 - p0) / ns
        for j in range(ns):
            panels.append((p0 + j * step, p0 + (j + 1) * step))
    return panels


def _integrate(nu: float, x: float, delta: float, mode: int,
               gl_n: int = 20, width_factor: float = 4.0,
               levels: tuple[float, ...] = _LEVELS) -> float:
    if not (nu > 0.0):
        raise ValueError("degrees of freedom must be > 0")
    a = 0.5 * nu
    K = _log_weight_const(a)
    nodes, wts = gauss_legendre(gl_n)
    total = 0.0
    exp_ = math.exp
    erfc_ = math.erfc
    for p0, p1 in _panels(nu, x, delta, width_factor, levels):
        c = 0.5 * (p0 + p1)
        h = 0.5 * (p1 - p0)
        if h == 0.0:
            continue
        for xi, wi in zip(nodes, wts):
            y = c + h * xi
            lw = K - a * _q(y)
            if lw < -745.0:
                continue
            g = exp_(lw) * wi * h
            if mode == _MODE_MASS:
                total += g
            else:
                arg = x * exp_(y) - delta
                if mode == _MODE_CDF:
                    total += g * (0.5 * erfc_(-arg / _SQRT2))
                else:
                    total += g * (0.5 * erfc_(arg / _SQRT2))
    return total


# ---------------------------------------------------------------------------
# public distribution functions
# ---------------------------------------------------------------------------


def _clip01(v: float) -> float:
    """Probabilities are confined to [0, 1]; the quadrature can land a few ulp
    outside.  This is range enforcement, not tolerance slack."""
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def weight_mass(nu: float, x: float = 0.0, delta: float = 0.0, **kw) -> float:
    """Total mass of the mixing measure, integrated on the panels that would
    be used for ``(x, delta)``.  Must be 1.0; this is the quadrature closure
    test required by SPEC.md section 4."""
    return _integrate(nu, x, delta, _MODE_MASS, **kw)


def nct_cdf(x: float, nu: float, delta: float = 0.0, **kw) -> float:
    """``T(x; nu, delta)`` -- CDF of the noncentral t distribution."""
    if not (nu > 0.0):
        raise ValueError("degrees of freedom must be > 0")
    if x == 0.0:
        return norm_cdf(-delta)
    return _clip01(_integrate(nu, x, delta, _MODE_CDF, **kw))


def nct_sf(x: float, nu: float, delta: float = 0.0, **kw) -> float:
    """``1 - T(x; nu, delta)`` computed *directly* (no cancellation)."""
    if not (nu > 0.0):
        raise ValueError("degrees of freedom must be > 0")
    if x == 0.0:
        return norm_cdf(delta)
    return _clip01(_integrate(nu, x, delta, _MODE_SF, **kw))


def student_t_cdf(x: float, nu: float, **kw) -> float:
    """``T(x; nu)`` -- CDF of the central t distribution."""
    return nct_cdf(x, nu, 0.0, **kw)


def student_t_sf(x: float, nu: float, **kw) -> float:
    """``1 - T(x; nu)``, computed directly."""
    return nct_sf(x, nu, 0.0, **kw)


def student_t_logpdf(x: float, nu: float) -> float:
    """``log`` of the central t density.

    ``log1p(x*x/nu)`` is the stable complement form of ``1 - nu/(nu+x^2)``.
    """
    return (
        log_gamma_ratio(0.5 * nu, 0.5)
        - 0.5 * math.log(nu * math.pi)
        - 0.5 * (nu + 1.0) * math.log1p(x * x / nu)
    )


def student_t_pdf(x: float, nu: float) -> float:
    return math.exp(student_t_logpdf(x, nu))


_ISF_CACHE: dict[tuple[float, float], float] = {}


def _isf_start(p: float, nu: float) -> float:
    z = -norm_ppf(p)
    if z <= 0.0:
        return 0.0
    # Cornish-Fisher
    z2 = z * z
    t = (z
         + z * (z2 + 1.0) / (4.0 * nu)
         + z * (5.0 * z2 * z2 + 16.0 * z2 + 3.0) / (96.0 * nu * nu)
         + z * (3.0 * z2 * z2 * z2 + 19.0 * z2 * z2 + 17.0 * z2 - 15.0)
         / (384.0 * nu ** 3))
    # Tail asymptotic: sf(t) ~ A * nu^((nu-1)/2) * t^(-nu)
    lt = (log_gamma_ratio(0.5 * nu, 0.5)
          - 0.5 * math.log(nu * math.pi)
          + 0.5 * (nu - 1.0) * math.log(nu)
          - math.log(p)) / nu
    cands = []
    if math.isfinite(t) and t > 0.0:
        cands.append(t)
    if lt < 709.0:
        ta = math.exp(lt)
        if math.isfinite(ta) and ta > 0.0:
            cands.append(ta)
    if not cands:
        return max(z, 1.0)
    return max(cands)


def student_t_isf(p: float, nu: float) -> float:
    """``t`` such that ``1 - T(t; nu) = p``, i.e. the ``1-p`` quantile."""
    if not (0.0 < p < 1.0):
        raise ValueError("student_t_isf requires 0 < p < 1")
    if not (nu > 0.0):
        raise ValueError("degrees of freedom must be > 0")
    if p == 0.5:
        return 0.0
    key = (p, nu)
    hit = _ISF_CACHE.get(key)
    if hit is not None:
        return hit
    if p > 0.5:
        val = -_isf_upper(1.0 - p, nu)
    else:
        val = _isf_upper(p, nu)
    if len(_ISF_CACHE) > 8192:
        _ISF_CACHE.clear()
    _ISF_CACHE[key] = val
    return val


def _isf_upper(p: float, nu: float) -> float:
    """Solve ``student_t_sf(t) = p`` for ``0 < p < 0.5`` (so ``t > 0``)."""
    lo = 0.0           # sf(0) = 0.5 > p
    hi = max(1.0, _isf_start(p, nu))
    n = 0
    while student_t_sf(hi, nu) > p:
        lo = hi
        hi *= 2.0
        n += 1
        if n > 4000 or not math.isfinite(hi):
            raise RuntimeError("could not bracket the central t quantile")
    t = min(max(_isf_start(p, nu), lo + 1e-300), hi)
    for _ in range(200):
        s = student_t_sf(t, nu)
        if s > p:
            lo = t
        else:
            hi = t
        d = student_t_pdf(t, nu)
        if d <= 0.0 or not math.isfinite(d):
            step = 0.5 * (lo + hi) - t
        else:
            step = (s - p) / d
        tn = t + step
        if not (lo < tn < hi):
            tn = 0.5 * (lo + hi)
        done = abs(tn - t) <= 1e-16 * max(1.0, abs(tn))
        t = tn
        if done:
            break
    return t


def student_t_ppf(q: float, nu: float) -> float:
    """``t`` such that ``T(t; nu) = q``."""
    if not (0.0 < q < 1.0):
        raise ValueError("student_t_ppf requires 0 < q < 1")
    return -student_t_isf(q, nu)
