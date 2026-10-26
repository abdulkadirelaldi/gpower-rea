"""The five analysis types of SPEC.md section 3.

| type        | given                     | solve for | method                                   |
|-------------|---------------------------|-----------|------------------------------------------|
| a priori    | alpha, 1-beta, ES, ratio  | N         | smallest grid point with power >= target |
| post hoc    | alpha, ES, design         | 1-beta    | direct evaluation of F-02                |
| criterion   | 1-beta, ES, design        | alpha     | bisection (power increases in alpha)     |
| sensitivity | alpha, 1-beta, design     | ES        | bisection over the admissible domain     |
| compromise  | q = beta/alpha, ES, design| alpha,1-b | bisection on the critical value (F-10)   |
"""

from __future__ import annotations

import math
from typing import Optional

from ._designs import (
    TESTS,
    ALLOCATION_RULES,
    Design,
    apriori_grid,
    check_test,
    effect_size_domain,
    effect_size_name,
    is_single_group,
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

#: SPEC/INTERFACE: the sample-size search is bounded at ten million grid points.
SEARCH_CAP = 10_000_000

_SIGN_WARNING = (
    "negative effect size: the hypothesis direction is taken to match the sign "
    "of the supplied effect size, so |delta| was used (SPEC.md F-08)"
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
    if tails not in (1, 2):
        raise ValueError("tails must be 1 or 2, got %r" % (tails,))
    return int(tails)


def _result(test: str, design: Design, *, effect_size: float, alpha: float,
            power: float, tails: int, critical: float,
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
        "ncp": float(design.delta),
        "critical_t": float(critical),
        "tails": int(tails),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 1. a priori  (F-05, F-06, F-09, F-12)
# ---------------------------------------------------------------------------


def _smallest_grid_point(pw, start: int, target: float, cap: int) -> int:
    """Smallest grid index ``i >= start`` with ``pw(i) >= target``.

    The comparison is ``>=`` in plain double precision with **no epsilon
    slack** (SPEC.md F-06, F-12).  ``pw`` returns a negative sentinel for
    inadmissible grid points; admissibility and power are both monotone in the
    index, so bracketing plus bisection returns exactly what a linear scan
    would.
    """
    if start > cap:
        raise RuntimeError(
            "the smallest admissible design already exceeds the sample-size "
            "search cap of %d" % cap
        )
    if pw(start) >= target:
        return start
    lo = start
    hi = start
    while True:
        nxt = min(max(hi * 2, hi + 1), cap)
        if nxt <= hi:
            raise RuntimeError(
                "requested power is unattainable within the bounded "
                "sample-size search (cap: %d grid points)" % cap
            )
        hi = nxt
        if pw(hi) >= target:
            break
        lo = hi
        if hi >= cap:
            raise RuntimeError(
                "requested power is unattainable within the bounded "
                "sample-size search (cap: %d grid points)" % cap
            )
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if pw(mid) >= target:
            hi = mid
        else:
            lo = mid
    # Safety net: never return a non-minimal point if the grid turned out not
    # to be monotone.  Bounded, and can only shrink the answer.
    for _ in range(16):
        if hi <= start or pw(hi - 1) < target:
            break
        hi -= 1
    return hi


def required_sample_size(test: str, *, alpha: float, power: float,
                         effect_size: float, tails: int = 2,
                         allocation_ratio: float = 1.0,
                         predictors: Optional[int] = None,
                         allocation_rule: str = "n1-grid") -> dict:
    """A-priori analysis: smallest design on the F-05/F-09 grid whose power
    reaches the target.

    ``result["power"]`` is the power **recomputed at the returned integer
    design** (F-06, "Actual power"), not the requested value; the request is
    echoed separately as ``result["target_power"]``.

    ``allocation_rule`` selects between the two candidate grids of F-09;
    ``"n1-grid"`` is the documented default.
    """
    check_test(test)
    alpha = _check_unit("alpha", alpha)
    target = _check_unit("power", power)
    tails = _check_tails(tails)
    validate_effect_size(test, effect_size)
    if allocation_rule not in ALLOCATION_RULES:
        raise ValueError(
            "allocation_rule must be one of %s" % (", ".join(ALLOCATION_RULES),))

    warnings: list[str] = []
    es = float(effect_size)
    if es < 0.0:
        warnings.append(_SIGN_WARNING)
        es = -es
    if es == 0.0:
        raise ValueError("a-priori analysis requires a non-zero effect size")

    start, build = apriori_grid(
        test, es, allocation_ratio=allocation_ratio,
        predictors=predictors, allocation_rule=allocation_rule,
    )

    def pw(i: int) -> float:
        d = build(i)
        if d is None:
            return -1.0
        return _power_of(d.nu, d.delta, alpha, tails)

    idx = _smallest_grid_point(pw, start, target, SEARCH_CAP)
    design = build(idx)
    assert design is not None
    # F-06: recompute at the integer design.
    actual = _power_of(design.nu, design.delta, alpha, tails)
    crit = critical_t(alpha, design.nu, tails)
    out = _result(test, design, effect_size=es, alpha=alpha, power=actual,
                  tails=tails, critical=crit, warnings=warnings)
    out["target_power"] = float(target)
    out["effect_size_input"] = float(effect_size)
    if test == "ttest-indep-means":
        out["allocation_ratio"] = float(allocation_ratio)
        out["allocation_rule"] = allocation_rule
        out["actual_allocation_ratio"] = design.n2 / design.n1
    return out


# ---------------------------------------------------------------------------
# 2. post hoc  (F-02, F-08)
# ---------------------------------------------------------------------------


def achieved_power(test: str, *, alpha: float, effect_size: float,
                   tails: int = 2, n: Optional[int] = None,
                   n1: Optional[int] = None, n2: Optional[int] = None,
                   predictors: Optional[int] = None,
                   df: Optional[float] = None) -> dict:
    """Post-hoc analysis: power of a fully specified design.

    Computed from the **signed** noncentrality (F-08): a one-tailed test with a
    negative effect size returns power below ``alpha``, and that is not
    clamped.  For ``ttest-generic``, ``effect_size`` *is* the noncentrality.
    """
    check_test(test)
    alpha = _check_unit("alpha", alpha)
    tails = _check_tails(tails)
    design = make_design(test, float(effect_size), n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    pwr = _power_of(design.nu, design.delta, alpha, tails)
    crit = critical_t(alpha, design.nu, tails)
    warnings: list[str] = []
    if design.delta < 0.0 and tails == 1:
        warnings.append(
            "post-hoc power is computed from the signed noncentrality, so a "
            "negative effect size yields power below alpha (SPEC.md F-08)")
    return _result(test, design, effect_size=float(effect_size), alpha=alpha,
                   power=pwr, tails=tails, critical=crit, warnings=warnings)


# ---------------------------------------------------------------------------
# 3. criterion
# ---------------------------------------------------------------------------

_ALPHA_LO = 1e-300
_ALPHA_HI = 1.0 - 1e-15


def required_alpha(test: str, *, power: float, effect_size: float,
                   tails: int = 2, n: Optional[int] = None,
                   n1: Optional[int] = None, n2: Optional[int] = None,
                   predictors: Optional[int] = None,
                   df: Optional[float] = None) -> dict:
    """Criterion analysis: the ``alpha`` at which the design attains the
    requested power.  Power is increasing in ``alpha``, so a bisection (here in
    ``log alpha``, which gives relative accuracy) is enough."""
    check_test(test)
    target = _check_unit("power", power)
    tails = _check_tails(tails)
    validate_effect_size(test, effect_size)

    warnings: list[str] = []
    es = float(effect_size)
    if es < 0.0:
        warnings.append(_SIGN_WARNING)
        es = -es
    design = make_design(test, es, n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    if design.delta == 0.0:
        raise ValueError("criterion analysis requires a non-zero effect size")

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
    out = _result(test, design, effect_size=es, alpha=a, power=pwr,
                  tails=tails, critical=crit, warnings=warnings)
    out["target_power"] = float(target)
    out["effect_size_input"] = float(effect_size)
    return out


# ---------------------------------------------------------------------------
# 4. sensitivity
# ---------------------------------------------------------------------------


def detectable_effect_size(test: str, *, alpha: float, power: float,
                           tails: int = 2, n: Optional[int] = None,
                           n1: Optional[int] = None, n2: Optional[int] = None,
                           predictors: Optional[int] = None,
                           df: Optional[float] = None) -> dict:
    """Sensitivity analysis: the smallest effect size the design can detect at
    the requested alpha and power.  ``result["effect_size"]`` carries the
    answer.  The bisection runs over the test's admissible domain
    (SPEC.md section 3)."""
    check_test(test)
    alpha = _check_unit("alpha", alpha)
    target = _check_unit("power", power)
    tails = _check_tails(tails)

    lo_dom, hi_dom = effect_size_domain(test)
    lo = max(lo_dom, 1e-12)
    hi = hi_dom
    if test == "ttest-point-biserial":
        hi = 1.0 - 1e-12           # open at 1

    def pw(es: float) -> float:
        d = make_design(test, es, n=n, n1=n1, n2=n2,
                        predictors=predictors, df=df)
        return _power_of(d.nu, d.delta, alpha, tails)

    # Validate the design once, with the message the user needs to see.
    make_design(test, lo, n=n, n1=n1, n2=n2, predictors=predictors, df=df)

    if pw(hi) < target:
        raise RuntimeError(
            "the requested power is unattainable on this design within the "
            "admissible effect-size domain (%s in (%g, %g]): the largest "
            "admissible effect size reaches only power %.12f"
            % (effect_size_name(test), lo_dom, hi_dom, pw(hi)))
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
                  tails=tails, critical=crit, warnings=[])
    out["target_power"] = float(target)
    return out


# ---------------------------------------------------------------------------
# 5. compromise  (F-10)
# ---------------------------------------------------------------------------


def compromise(test: str, *, effect_size: float, beta_alpha_ratio: float,
               tails: int = 2, n: Optional[int] = None,
               n1: Optional[int] = None, n2: Optional[int] = None,
               predictors: Optional[int] = None,
               df: Optional[float] = None) -> dict:
    """Compromise analysis (F-10): fix the design and the effect size, accept a
    desired error ratio ``q = beta/alpha``, and solve for the **critical
    value**.

        k = 1:  alpha(c) = 1 - T(c;nu)        beta(c) = T(c;nu,delta)
        k = 2:  alpha(c) = 2*(1 - T(c;nu))    beta(c) = T(c;nu,delta) - T(-c;nu,delta)

    ``beta(c)/alpha(c)`` is strictly increasing in ``c``, so the root is unique
    and a bisection suffices.  The ``k = 2`` beta is the exact complement of
    F-02's power expression, far-tail term included.
    """
    check_test(test)
    tails = _check_tails(tails)
    if not isinstance(beta_alpha_ratio, (int, float)) or isinstance(beta_alpha_ratio, bool):
        raise ValueError("beta_alpha_ratio must be a positive number")
    q = float(beta_alpha_ratio)
    if not math.isfinite(q) or q <= 0.0:
        raise ValueError("beta_alpha_ratio must be a finite positive number")
    validate_effect_size(test, effect_size)

    design = make_design(test, float(effect_size), n=n, n1=n1, n2=n2,
                         predictors=predictors, df=df)
    nu, delta = design.nu, design.delta
    if delta == 0.0:
        raise ValueError("compromise analysis requires a non-zero effect size")

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
    out = _result(test, design, effect_size=float(effect_size), alpha=a,
                  power=pwr, tails=tails, critical=c, warnings=[])
    out["beta"] = float(bt)
    out["beta_alpha_ratio"] = q
    out["achieved_beta_alpha_ratio"] = (bt / a) if a > 0.0 else math.inf
    return out
