"""The five analysis types of SPEC.md v1.3 section 3.

| type        | given                     | solve for | method                                         |
|-------------|---------------------------|-----------|------------------------------------------------|
| a priori    | alpha, 1-beta, ES, ratio  | N         | first grid point passing the stopping test,    |
|             |                           |           | searched up to N = 2**63 - 2                   |
| post hoc    | alpha, ES, design         | 1-beta    | direct evaluation of F-02                      |
| criterion   | 1-beta, ES, design        | alpha     | bisection on log alpha over [1e-300, 1-1e-15]  |
| sensitivity | alpha, 1-beta, design     | ES        | bisection over the closed bracket              |
| compromise  | q = beta/alpha, ES, design| alpha,1-b | bisection on the critical value (F-10)         |

Sign rule (F-08, observed): every probability is computed from ``|delta|``;
the reported ``ncp`` is ``sign(ES)*|delta|`` and the reported ``critical_t``
is ``sign(ES)*t_crit`` -- except in the criterion analysis, where it is
``+t_crit``.  A negative effect size adds a ``warnings[]`` entry.
"""

from __future__ import annotations

import math
from typing import Optional

from ._designs import (
    ALLOCATION_RULES,
    APRIORI_MIN_ES,
    APRIORI_MIN_ES_TESTS,
    APRIORI_N_CAP,
    R_ALLOC_MAX,
    R_ALLOC_MIN,
    DEFAULT_ALLOCATION_RULE,
    Design,
    apriori_grid,
    check_test,
    effect_size_bracket,
    effect_size_name,
    make_design,
    validate_effect_size,
)
from ._power import (
    alpha_from_critical,
    critical_t,
    power as _power_of,
    power_and_beta,
)

__all__ = [
    "SEARCH_CAP",
    "required_sample_size",
    "achieved_power",
    "required_alpha",
    "detectable_effect_size",
    "compromise",
]

#: SPEC.md section 3 / F-15: the a-priori N is searched up to 2**63 - 2.
#: (INTERFACE.md, as corrected for v1.3, states the same cap; F-16 G2-01.)
SEARCH_CAP = APRIORI_N_CAP

#: F-14: thresholds of the "G*Power itself is inexact here" region.
F14_ALPHA = 1e-9
F14_N = 1e7

#: F-15: admissible beta/alpha ratio.
Q_MIN, Q_MAX = 0.01, 100.0

_SIGN_WARNING = (
    "negative effect size %r: the sign is taken as the direction of the "
    "alternative; probabilities are computed from |delta|, and delta%s are "
    "reported with the sign of the effect (SPEC.md F-08)"
)


# ---------------------------------------------------------------------------
# shared validation / packaging
# ---------------------------------------------------------------------------


def _check_unit(name: str, value: float) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError("%s must be a number in (0, 1)" % name)
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number in (0, 1)" % name) from None
    if not math.isfinite(v) or not (0.0 < v < 1.0):
        raise ValueError("%s must be in (0, 1), got %r" % (name, value))
    return v


def _check_tails(tails: int) -> int:
    if isinstance(tails, bool) or tails not in (1, 2):
        raise ValueError("tails must be 1 or 2, got %r" % (tails,))
    return int(tails)


def _check_power_vs_alpha(target: float, alpha: float) -> None:
    # F-15 (D-13, D-20, D-32): power = alpha accepted, power < alpha refused.
    if target < alpha:
        raise ValueError(
            "power must be >= alpha (SPEC.md F-15), got power=%r < alpha=%r"
            % (target, alpha))


def _signed(test: str, effect_size: float, *, critical_signed: bool
            ) -> tuple[float, float, list[str]]:
    """``(|ES|, sign, warnings)`` per F-08.  ``sign(0)`` is taken as +1."""
    es = validate_effect_size(test, effect_size)
    warnings: list[str] = []
    if es < 0.0:
        warnings.append(_SIGN_WARNING % (
            effect_size, " and the critical t" if critical_signed else ""))
        return -es, -1.0, warnings
    return es, 1.0, warnings


def _result(test: str, design: Design, *, effect_size: float, alpha: float,
            power: float, tails: int, critical: float, ncp: float,
            warnings: list[str]) -> dict:
    return {
        "test": test,
        "n1": int(design.n1),
        "n2": int(design.n2),
        "total": int(design.total),
        "power": float(power),
        "alpha": float(alpha),
        "effect_size": float(effect_size),
        "effect_size_name": effect_size_name(test),
        "df": float(design.nu),
        "ncp": float(ncp),
        "critical_t": float(critical),
        "tails": int(tails),
        "warnings": warnings,
    }


def _f14_alpha_warning(alpha: float, warnings: list[str]) -> None:
    if alpha < F14_ALPHA:
        warnings.append(
            "alpha = %.6g < 1e-9: G*Power 3.1.9.6's own answer is inexact in "
            "this region (far-tail central-t quantile); the value reported "
            "here is the exact one (SPEC.md F-14)" % alpha)


# ---------------------------------------------------------------------------
# 1. a priori  (F-05, F-06, F-09, F-12, F-14, F-15, section 3)
# ---------------------------------------------------------------------------


def _unattainable(cap_n: int) -> RuntimeError:
    return RuntimeError(
        "requested power is unattainable within the bounded sample-size "
        "search: the a-priori search is capped at a total N = 2**63 - 2 = %d "
        "(SPEC.md section 3, F-15, F-16 G2-01)" % cap_n)


def _smallest_grid_point(pw, start: int, last: int, target: float) -> int:
    """Smallest grid index ``start <= i <= last`` with ``pw(i) >= target``.

    The comparison is ``>=`` in plain double precision with **no epsilon
    slack** (F-06, F-12).  ``pw`` returns a negative sentinel for skipped
    grid points; admissibility is an up-set and the stopping power is
    monotone in the index, so bracketing plus bisection returns exactly what
    a linear scan would.
    """
    if pw(start) >= target:
        return start
    lo = start
    hi = start
    while True:
        if hi >= last:
            raise _unattainable(APRIORI_N_CAP)
        hi = min(max(hi * 2, hi + 1), last)
        if pw(hi) >= target:
            break
        lo = hi
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if pw(mid) >= target:
            hi = mid
        else:
            lo = mid
    # Safety net against a numerically non-monotone grid: never return a
    # point whose predecessor already passes.  Bounded; can only shrink.
    for _ in range(16):
        if hi <= start or pw(hi - 1) < target:
            break
        hi -= 1
    return hi


def required_sample_size(test: str, *, alpha: float, power: float,
                         effect_size: float, tails: int = 2,
                         allocation_ratio: float = 1.0,
                         allocation_rule: str = DEFAULT_ALLOCATION_RULE,
                         predictors: Optional[int] = None) -> dict:
    """A-priori analysis: the first design on the F-05/F-09 grid whose
    stopping test passes.

    ``result["power"]`` is the power **recomputed at the reported integer
    design** (F-06, "Actual power").  For ``R != 1`` under the default
    ``"even-total"`` rule the stopping test is made on the unrounded split,
    so this power can be *below* the target (F-06, refuted clause); the
    design is not repaired.  The request is echoed as ``target_power``.
    """
    check_test(test)
    if test == "ttest-generic":
        raise ValueError(
            "a-priori analysis is not available for ttest-generic: "
            "the generic t test supplies nu and delta directly, so N has no "
            "meaning (SPEC.md section 3)")
    alpha = _check_unit("alpha", alpha)
    target = _check_unit("power", power)
    tails = _check_tails(tails)
    _check_power_vs_alpha(target, alpha)
    if allocation_rule not in ALLOCATION_RULES:
        raise ValueError(
            "allocation_rule must be one of %s" % (", ".join(ALLOCATION_RULES),))
    if test == "ttest-indep-means":
        if (isinstance(allocation_ratio, bool)
                or not isinstance(allocation_ratio, (int, float))
                or not math.isfinite(allocation_ratio)
                or not (R_ALLOC_MIN <= allocation_ratio <= R_ALLOC_MAX)):
            raise ValueError(
                "allocation_ratio N2/N1 must be in [0.01, 100] "
                "(SPEC.md F-15, F-16 G2-11), got %r" % (allocation_ratio,))
    else:
        # F-13 item 11: inapplicable parameters are rejected, not ignored.
        if allocation_ratio != 1.0:
            raise ValueError("allocation_ratio is only applicable to "
                             "ttest-indep-means (SPEC.md F-13 item 11)")
        if allocation_rule != DEFAULT_ALLOCATION_RULE:
            raise ValueError("allocation_rule is only applicable to "
                             "ttest-indep-means (SPEC.md F-13 item 11)")
    if test != "ttest-regression-coef" and predictors is not None:
        raise ValueError("predictors is only applicable to ttest-regression-coef "
                         "(SPEC.md F-13 item 11)")

    es, sign, warnings = _signed(test, effect_size, critical_signed=True)
    if es == 0.0:
        # section 3 / F-13 item 8: zero is a validation error in a priori.
        raise ValueError("a-priori analysis requires a non-zero effect size "
                         "(SPEC.md section 3, F-13 item 8)")
    if test in APRIORI_MIN_ES_TESTS and es < APRIORI_MIN_ES:
        # F-15 (D-31, D-40, X-G2-08b): d, dz and f2 -- not r (X-G2-08a).
        raise ValueError(
            "a-priori analysis requires |effect size| >= 0.00001 for %s "
            "(SPEC.md F-15), got %r" % (effect_size_name(test), effect_size))

    grid = apriori_grid(test, es, allocation_ratio=allocation_ratio,
                        predictors=predictors, allocation_rule=allocation_rule)

    def pw(i: int) -> float:
        pt = grid.stop(i)
        if pt is None:
            return -1.0
        return _power_of(pt[0], pt[1], alpha, tails)

    idx = _smallest_grid_point(pw, grid.start, grid.last, target)
    design = grid.report(idx)
    # F-06: recompute at the reported integer design.
    actual = _power_of(design.nu, design.delta, alpha, tails)
    crit = critical_t(alpha, design.nu, tails)
    if design.total > F14_N:
        warnings.append(
            "N = %d > 1e7: G*Power 3.1.9.6's own a-priori answer is inexact "
            "in this region; the value reported here is the exact one as "
            "nearly as this engine can compute it (SPEC.md F-14)" % design.total)
    out = _result(test, design, effect_size=float(effect_size), alpha=alpha,
                  power=actual, tails=tails, critical=sign * crit,
                  ncp=sign * design.delta, warnings=warnings)
    out["target_power"] = float(target)
    if test == "ttest-indep-means":
        out["allocation_ratio"] = float(allocation_ratio)
        out["allocation_rule"] = allocation_rule
        out["actual_allocation_ratio"] = (design.n2 / design.n1
                                          if design.n1 else math.inf)
    return out


# ---------------------------------------------------------------------------
# 2. post hoc  (F-02, F-08)
# ---------------------------------------------------------------------------


def achieved_power(test: str, *, alpha: float, effect_size: float,
                   tails: int = 2, n: Optional[int] = None,
                   n1: Optional[int] = None, n2: Optional[int] = None,
                   predictors: Optional[int] = None,
                   df: Optional[float] = None) -> dict:
    """Post-hoc analysis: power of a fully specified design, from ``|delta|``
    (F-08).  For ``ttest-generic``, ``effect_size`` *is* the noncentrality."""
    check_test(test)
    alpha = _check_unit("alpha", alpha)
    tails = _check_tails(tails)
    es, sign, warnings = _signed(test, effect_size, critical_signed=True)
    design = make_design(test, es, n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    pwr = _power_of(design.nu, design.delta, alpha, tails)
    crit = critical_t(alpha, design.nu, tails)
    return _result(test, design, effect_size=float(effect_size), alpha=alpha,
                   power=pwr, tails=tails, critical=sign * crit,
                   ncp=sign * design.delta, warnings=warnings)


# ---------------------------------------------------------------------------
# 3. criterion  (F-08: critical t NOT signed; F-13 item 5; F-14)
# ---------------------------------------------------------------------------

_ALPHA_LO = 1e-300
_ALPHA_HI = 1.0 - 1e-15


def required_alpha(test: str, *, power: float, effect_size: float,
                   tails: int = 2, n: Optional[int] = None,
                   n1: Optional[int] = None, n2: Optional[int] = None,
                   predictors: Optional[int] = None,
                   df: Optional[float] = None) -> dict:
    """Criterion analysis: the ``alpha`` at which the design attains the
    requested power; bisection on ``log alpha`` over ``[1e-300, 1-1e-15]``."""
    check_test(test)
    target = _check_unit("power", power)
    tails = _check_tails(tails)
    es, sign, warnings = _signed(test, effect_size, critical_signed=False)
    design = make_design(test, es, n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    if es == 0.0 or design.delta == 0.0:
        raise ValueError("criterion analysis requires a non-zero effect size "
                         "(SPEC.md section 3, F-13 item 8)")

    def f(a: float) -> float:
        return _power_of(design.nu, design.delta, a, tails)

    if f(_ALPHA_HI) < target:
        raise RuntimeError(
            "the requested power is unattainable: even alpha = %g yields only "
            "power %.12f" % (_ALPHA_HI, f(_ALPHA_HI)))
    if f(_ALPHA_LO) >= target:
        a = _ALPHA_LO
    else:
        lo = math.log(_ALPHA_LO)
        hi = math.log(_ALPHA_HI)
        for _ in range(300):
            mid = 0.5 * (lo + hi)
            if f(math.exp(mid)) >= target:
                hi = mid
            else:
                lo = mid
            if hi - lo <= 1e-16 * max(1.0, abs(hi)):
                break
        a = math.exp(hi)

    pwr = _power_of(design.nu, design.delta, a, tails)
    crit = critical_t(a, design.nu, tails)
    _f14_alpha_warning(a, warnings)
    # F-08: the criterion analysis does NOT apply the sign to the critical t.
    out = _result(test, design, effect_size=float(effect_size), alpha=a,
                  power=pwr, tails=tails, critical=crit,
                  ncp=sign * design.delta, warnings=warnings)
    out["target_power"] = float(target)
    return out


# ---------------------------------------------------------------------------
# 4. sensitivity
# ---------------------------------------------------------------------------


def detectable_effect_size(test: str, *, alpha: float, power: float,
                           tails: int = 2, n: Optional[int] = None,
                           n1: Optional[int] = None, n2: Optional[int] = None,
                           predictors: Optional[int] = None,
                           df: Optional[float] = None) -> dict:
    """Sensitivity analysis: the smallest effect size the design detects at
    the requested alpha and power, by bisection over the closed bracket of
    SPEC.md section 3.  ``result["effect_size"]`` carries the answer."""
    check_test(test)
    alpha = _check_unit("alpha", alpha)
    target = _check_unit("power", power)
    tails = _check_tails(tails)
    _check_power_vs_alpha(target, alpha)

    lo, hi = effect_size_bracket(test)

    def pw(es: float) -> float:
        d = make_design(test, es, n=n, n1=n1, n2=n2,
                        predictors=predictors, df=df)
        return _power_of(d.nu, d.delta, alpha, tails)

    # Validate the design once, with the message the user needs to see.
    make_design(test, lo, n=n, n1=n1, n2=n2, predictors=predictors, df=df)

    p_hi = pw(hi)
    if p_hi < target:
        raise RuntimeError(
            "the requested power is unattainable on this design within the "
            "effect-size bracket (%s in [%g, %g]): the upper end reaches only "
            "power %.12f" % (effect_size_name(test), lo, hi, p_hi))
    if pw(lo) >= target:
        es = lo
    else:
        for _ in range(300):
            mid = 0.5 * (lo + hi)
            if pw(mid) >= target:
                hi = mid
            else:
                lo = mid
            if hi - lo <= 1e-15 * max(1.0, abs(hi)):
                break
        es = hi

    design = make_design(test, es, n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    pwr = _power_of(design.nu, design.delta, alpha, tails)
    crit = critical_t(alpha, design.nu, tails)
    out = _result(test, design, effect_size=es, alpha=alpha, power=pwr,
                  tails=tails, critical=crit, ncp=design.delta, warnings=[])
    out["target_power"] = float(target)
    return out


# ---------------------------------------------------------------------------
# 5. compromise  (F-10, F-13 item 1, F-08, F-14, F-15)
# ---------------------------------------------------------------------------


def compromise(test: str, *, effect_size: float, beta_alpha_ratio: float,
               tails: int = 2, n: Optional[int] = None,
               n1: Optional[int] = None, n2: Optional[int] = None,
               predictors: Optional[int] = None,
               df: Optional[float] = None) -> dict:
    """Compromise analysis (F-10): fix the design and ``|ES|``, accept
    ``q = beta/alpha`` in ``[0.01, 100]`` (F-15), solve for the critical
    value ``c``; report ``alpha(c)``, ``1-beta(c)`` and ``sign(ES)*c``."""
    check_test(test)
    tails = _check_tails(tails)
    if (isinstance(beta_alpha_ratio, bool)
            or not isinstance(beta_alpha_ratio, (int, float))):
        raise ValueError("beta_alpha_ratio must be a number in [0.01, 100]")
    q = float(beta_alpha_ratio)
    if not math.isfinite(q) or not (Q_MIN <= q <= Q_MAX):
        raise ValueError("beta_alpha_ratio must be in [0.01, 100] "
                         "(SPEC.md F-15), got %r" % (beta_alpha_ratio,))
    es, sign, warnings = _signed(test, effect_size, critical_signed=True)

    design = make_design(test, es, n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    nu, delta = design.nu, design.delta
    if es == 0.0 or delta == 0.0:
        raise ValueError("compromise analysis requires a non-zero effect size "
                         "(SPEC.md section 3, F-13 item 8)")

    def ratio(c: float) -> float:
        a = alpha_from_critical(nu, c, tails)
        b = power_and_beta(nu, delta, c, tails)[1]
        if a <= 0.0:
            return math.inf
        return b / a

    # bracket
    if ratio(0.0) >= q:
        if tails == 2:
            # ratio(0) == 0 for k = 2, so this cannot happen for q > 0
            raise RuntimeError("could not bracket the compromise critical value")
        hi = 0.0
        lo = -1.0
        for _ in range(4000):
            if ratio(lo) <= q:
                break
            lo *= 2.0
        else:
            raise RuntimeError("could not bracket the compromise critical value")
    else:
        lo = 0.0
        hi = 1.0
        for _ in range(4000):
            if ratio(hi) >= q:
                break
            hi *= 2.0
        else:
            raise RuntimeError("could not bracket the compromise critical value")

    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if ratio(mid) >= q:
            hi = mid
        else:
            lo = mid
        if hi - lo <= 1e-15 * max(1.0, abs(hi)):
            break
    c = 0.5 * (lo + hi)

    a = alpha_from_critical(nu, c, tails)
    pwr, bt = power_and_beta(nu, delta, c, tails)
    _f14_alpha_warning(a, warnings)
    out = _result(test, design, effect_size=float(effect_size), alpha=a,
                  power=pwr, tails=tails, critical=sign * c,
                  ncp=sign * delta, warnings=warnings)
    out["beta"] = float(bt)
    out["beta_alpha_ratio"] = q
    out["achieved_beta_alpha_ratio"] = (bt / a) if a > 0.0 else math.inf
    return out
