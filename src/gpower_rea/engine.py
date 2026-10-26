"""The one and only computation engine.

Invariant I-3 (docs/ARCHITECTURE.md): the CLI, the MCP server and the AI agent
are thin adapters over ``solve()``.  No power arithmetic lives anywhere else.

Public surface
--------------
    power(...)        -> PowerPoint        one (alpha, N, ES) -> power
    solve(...)        -> Result            the five G*Power analysis types
    power_curve(...)  -> list[PowerPoint]  N sweep, for plots / agents
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from typing import Mapping

from . import numerics as nm
from .procedures import (
    PROCEDURES,
    Procedure,
    Sample,
    ValidationError,
    resolve,
)

__all__ = [
    "ENGINE_VERSION",
    "SPEC_VERSION",
    "ALLOCATION_RULES",
    "DEFAULT_ALLOCATION_RULE",
    "NoSolutionError",
    "PowerPoint",
    "Result",
    "power",
    "solve",
    "power_curve",
    "SOLVE_MODES",
]

ENGINE_VERSION = "1.1.0"
SPEC_VERSION = "SPEC.md v1.1"

SOLVE_MODES = ("n", "power", "alpha", "effect-size", "compromise")

#: Spellings accepted for ``solve_for``, including the labels the G*Power GUI
#: uses for its "Type of power analysis" dropdown.  Keys are normalised by
#: ``_norm_solve`` (lower-cased, non-alphanumerics removed).
_SOLVE_ALIASES = {
    # a priori -- compute required sample size
    "n": "n",
    "samplesize": "n",
    "totalsamplesize": "n",
    "apriori": "n",
    "aprioricomputerequiredsamplesize": "n",
    "computerequiredsamplesize": "n",
    "requiredsamplesize": "n",
    # post hoc -- compute achieved power
    "power": "power",
    "posthoc": "power",
    "posthoccomputeachievedpower": "power",
    "computeachievedpower": "power",
    "achievedpower": "power",
    # criterion -- compute required alpha
    "alpha": "alpha",
    "criterion": "alpha",
    "criterioncomputerequiredalpha": "alpha",
    "computerequiredalpha": "alpha",
    "requiredalpha": "alpha",
    # sensitivity -- compute required effect size
    "effectsize": "effect-size",
    "es": "effect-size",
    "sensitivity": "effect-size",
    "sensitivitycomputerequiredeffectsize": "effect-size",
    "computerequiredeffectsize": "effect-size",
    "requiredeffectsize": "effect-size",
    "d": "effect-size",
    # compromise
    "compromise": "compromise",
    "compromisecomputeimpliedalphapower": "compromise",
}


def _norm_solve(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())

#: Hard ceiling on the a-priori search so a pathological request terminates.
N_SEARCH_CAP = 10_000_000

#: Closed bracket for the criterion analysis (SPEC F-13).  The search runs on
#: log(alpha), so the lower end costs nothing and a genuinely tiny answer is
#: reported rather than clipped to a round number.
ALPHA_SEARCH_MIN = 1e-300
ALPHA_SEARCH_MAX = 1.0 - 1e-15


class NoSolutionError(RuntimeError):
    """The requested quantity cannot be attained inside the search domain."""


# --------------------------------------------------------------------------
# Allocation rules (SPEC F-05 / evidence E-005)
# --------------------------------------------------------------------------
def _round_half_up(x: float) -> int:
    """Round halves away from zero -- NOT Python's banker's rounding."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def _alloc_n1_grid(step: int, ratio: float, min_sample: Sample) -> Sample:
    """Search n1 over the integers, set n2 = round_half_up(ratio * n1).

    This is the documented default.  With ratio = 1 it forces n1 == n2, which
    is why G*Power never reports an odd total N for a balanced a-priori
    two-group t test (evidence E-005).
    """
    n1 = max(step, min_sample.n1)
    n2 = max(_round_half_up(ratio * n1), min_sample.n2)
    return Sample(n1, n2)


def _alloc_total_grid(step: int, ratio: float, min_sample: Sample) -> Sample:
    """Search total N, split it as n1 = round_half_up(N/(1+ratio))."""
    total = max(step, min_sample.total)
    n1 = max(_round_half_up(total / (1.0 + ratio)), min_sample.n1)
    n2 = max(total - n1, min_sample.n2)
    return Sample(n1, n2)


ALLOCATION_RULES = {
    "n1-grid": _alloc_n1_grid,
    "total-grid": _alloc_total_grid,
}
DEFAULT_ALLOCATION_RULE = "n1-grid"


def _allocate(
    proc: Procedure,
    step: int,
    ratio: float,
    extra: Mapping,
    rule: str,
) -> Sample:
    min_sample = proc.min_sample(extra)
    if not proc.two_group:
        return Sample(max(step, min_sample.total))
    try:
        fn = ALLOCATION_RULES[rule]
    except KeyError:
        raise ValidationError(
            f"unknown allocation rule {rule!r}; "
            f"choose from {sorted(ALLOCATION_RULES)}"
        ) from None
    return fn(step, ratio, min_sample)


# --------------------------------------------------------------------------
# The single power formula (SPEC F-01 / F-02, evidence E-002)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PowerPoint:
    power: float
    alpha: float
    df: float
    ncp: float
    critical_t: float
    tails: int
    sample: Sample

    def as_dict(self) -> dict:
        out = {
            "power": self.power,
            "alpha": self.alpha,
            "df": self.df,
            "noncentrality": self.ncp,
            "critical_t": self.critical_t,
            "tails": self.tails,
        }
        out["sample_size"] = self.sample.as_dict()
        return out


def _power_from_ncp(alpha: float, df: float, ncp: float, tails: int) -> tuple[float, float]:
    """Return (power, critical_t).

    One tail   : power = 1 - F_nct(t_{1-alpha}; df, ncp)
    Two tails  : power = 1 - F_nct(t_{1-alpha/2}) + F_nct(-t_{1-alpha/2})

    The second term in the two-tailed case is the "wrong side" rejection
    region.  Dropping it -- as many textbook formulas and several R helpers do
    -- is detectable: at ncp = 0 the correct formula returns exactly alpha,
    the truncated one returns alpha/2.  See evidence E-002.
    """
    # The critical value is obtained as -t_ppf(tail), not t_ppf(1 - tail).
    # Central t is symmetric, so the two are equal in exact arithmetic -- but
    # `1 - alpha` loses every significant digit of a tiny alpha (at
    # alpha = 1e-300, `1 - alpha/2` rounds to exactly 1.0 and the quantile
    # call fails outright).  The criterion analysis routinely reaches that
    # regime: see SPEC F-13 item 5.
    try:
        if tails == 1:
            t_crit = nm.t_isf(alpha, df)
        elif tails == 2:
            t_crit = nm.t_isf(0.5 * alpha, df)
        else:
            raise ValidationError(f"tails must be 1 or 2, got {tails!r}")
    except ValueError as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(
            f"the critical value for alpha={alpha!r}, df={df!r}, "
            f"tails={tails} is not representable: {exc}"
        ) from None

    # Both terms come from a survival/CDF pair that is computed directly, so
    # the sum is of positive quantities.  Writing the first term as
    # `1 - nct_cdf(t_crit)` would keep only absolute accuracy, and power is
    # genuinely tiny in two places the engine reaches: a one-tailed test
    # pointed the wrong way (7.7e-06) and the size of a test at alpha = 1e-12.
    upper = nm.nct_sf(t_crit, df, ncp)
    if tails == 1:
        return upper, t_crit
    return upper + nm.nct_cdf(-t_crit, df, ncp), t_crit


def _beta_and_alpha(c: float, df: float, ncp: float, tails: int) -> tuple[float, float]:
    """(beta, alpha) implied by using |t| > c (two tails) or t > c (one tail)."""
    if tails == 1:
        alpha = 1.0 - nm.t_cdf(c, df)
        beta = nm.nct_cdf(c, df, ncp)
    else:
        alpha = 2.0 * (1.0 - nm.t_cdf(c, df))
        beta = nm.nct_cdf(c, df, ncp) - nm.nct_cdf(-c, df, ncp)
    return beta, alpha


def _validate_common(alpha: float | None, tails: int) -> None:
    if tails not in (1, 2):
        raise ValidationError(f"tails must be 1 or 2, got {tails!r}")
    if alpha is not None and not (0.0 < alpha < 1.0):
        raise ValidationError(f"alpha must be in (0,1), got {alpha!r}")


def _require_nonzero_effect_size(effect_size: float, solve_for: str) -> None:
    """A zero effect size makes three of the five analyses meaningless.

    With delta = 0 the power of F-02 equals alpha for every N and every alpha,
    so no finite design and no admissible alpha can reach a target power above
    alpha.  Refuse up front instead of exhausting a 10-million-step search
    (SPEC F-13 / G-08).
    """
    if effect_size == 0.0:
        raise ValidationError(
            f"solve={solve_for} is undefined for a zero effect size: with "
            f"delta = 0 the power equals alpha for every design, so no target "
            f"above alpha is attainable (SPEC F-13)"
        )


def power(
    test: str | Procedure,
    *,
    alpha: float,
    effect_size: float,
    tails: int = 2,
    n: int | None = None,
    n1: int | None = None,
    n2: int | None = None,
    allocation_ratio: float | None = None,
    extra: Mapping | None = None,
) -> PowerPoint:
    """Post-hoc power for an explicit design."""
    proc = test if isinstance(test, Procedure) else resolve(test)
    _validate_common(alpha, tails)
    ex = proc.normalise_extra(extra)
    proc.check_effect_size(effect_size)
    sample = _explicit_sample(proc, ex, n=n, n1=n1, n2=n2, ratio=allocation_ratio)
    df = proc.df(sample, ex)
    if df <= 0:
        raise ValidationError(
            f"{proc.key}: sample size too small, degrees of freedom = {df:g}"
        )
    ncp = proc.ncp(sample, effect_size, ex)
    pw, t_crit = _power_from_ncp(alpha, df, ncp, tails)
    return PowerPoint(pw, alpha, df, ncp, t_crit, tails, sample)


def _explicit_sample(
    proc: Procedure,
    extra: Mapping,
    *,
    n: int | None,
    n1: int | None,
    n2: int | None,
    ratio: float | None,
) -> Sample:
    if proc.key == "ttest-generic":
        return Sample(0)
    if proc.two_group:
        if n1 is not None and n2 is not None:
            return Sample(int(n1), int(n2))
        if n is not None:
            r = 1.0 if ratio is None else float(ratio)
            if r <= 0:
                raise ValidationError("allocation_ratio must be > 0")
            a = _round_half_up(int(n) / (1.0 + r))
            return Sample(a, int(n) - a)
        if n1 is not None and ratio is not None:
            return Sample(int(n1), max(_round_half_up(float(ratio) * int(n1)), 1))
        raise ValidationError(
            f"{proc.key} needs either (n1 and n2) or (n and allocation_ratio)"
        )
    if n is None:
        if n1 is not None:
            return Sample(int(n1))
        raise ValidationError(f"{proc.key} needs n (total sample size)")
    return Sample(int(n))


# --------------------------------------------------------------------------
# Monotone integer search (SPEC F-06, evidence E-005 / E-006)
# --------------------------------------------------------------------------
def _smallest_step(predicate, start: int, cap: int) -> int:
    """Smallest integer step >= start satisfying a (locally monotone) predicate."""
    if predicate(start):
        return start
    lo, span = start, 1
    hi = start
    while True:
        hi = lo + span
        if hi > cap:
            hi = cap
            if predicate(hi):
                break
            raise NoSolutionError(
                f"no solution with sample size up to {cap}: the requested "
                f"power is unattainable for this effect size / alpha"
            )
        if predicate(hi):
            break
        lo = hi
        span *= 2
    # binary search in (lo, hi]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if predicate(mid):
            hi = mid
        else:
            lo = mid
    # Walk down once more: guards against the rare non-monotone blip that a
    # rounding rule can introduce for allocation_ratio != 1.
    while hi > start and predicate(hi - 1):
        hi -= 1
    return hi


def _bisect_scalar(fn, lo: float, hi: float, target: float, iters: int = 200) -> float:
    """Bisection for a monotone-increasing fn on [lo, hi] solving fn(x)=target."""
    f_lo, f_hi = fn(lo), fn(hi)
    if f_lo > target and f_hi > target:
        return lo
    if f_lo < target and f_hi < target:
        raise NoSolutionError(
            f"target {target:g} outside the attainable range "
            f"[{f_lo:g}, {f_hi:g}]"
        )
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-14 * max(1.0, abs(hi)):
            break
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------
# Result object
# --------------------------------------------------------------------------
@dataclass
class Result:
    schema: str
    test: str
    test_title: str
    family: str
    solve_for: str
    tails: int
    alpha: float
    power: float
    df: float
    noncentrality: float
    critical_t: float
    effect_size: dict
    sample_size: dict
    target: dict = field(default_factory=dict)
    engine: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _build_result(
    proc: Procedure,
    solve_for: str,
    pt: PowerPoint,
    effect_size: float,
    extra: Mapping,
    target: Mapping,
    allocation_ratio: float | None,
    allocation_rule: str | None,
    warnings: list,
) -> Result:
    sample = pt.sample.as_dict()
    if proc.two_group and allocation_ratio is not None:
        sample["allocation_ratio"] = allocation_ratio
        sample["actual_ratio"] = (
            pt.sample.n2 / pt.sample.n1 if pt.sample.n1 else None
        )
    engine = {
        "name": "gpower-rea",
        "version": ENGINE_VERSION,
        "spec": SPEC_VERSION,
    }
    if proc.two_group:
        engine["allocation_rule"] = allocation_rule or DEFAULT_ALLOCATION_RULE
    return Result(
        schema="gpower-rea/result/1",
        test=proc.key,
        test_title=proc.title,
        family="t tests",
        solve_for=solve_for,
        tails=pt.tails,
        alpha=pt.alpha,
        power=pt.power,
        df=pt.df,
        noncentrality=pt.ncp,
        critical_t=pt.critical_t,
        effect_size={
            "name": proc.effect_size_name,
            "value": effect_size,
            **({"parameters": dict(extra)} if extra else {}),
        },
        sample_size=sample,
        target=dict(target),
        engine=engine,
        warnings=warnings,
    )


# --------------------------------------------------------------------------
# solve(): the five G*Power "Type of power analysis" modes
# --------------------------------------------------------------------------
def solve(
    test: str,
    solve_for: str = "n",
    *,
    alpha: float | None = None,
    power_target: float | None = None,
    effect_size: float | None = None,
    tails: int = 2,
    n: int | None = None,
    n1: int | None = None,
    n2: int | None = None,
    allocation_ratio: float | None = None,
    allocation_rule: str | None = None,
    beta_alpha_ratio: float | None = None,
    extra: Mapping | None = None,
) -> Result:
    """Run one G*Power analysis.

    ``solve_for``:
        "n"             a priori     -> smallest sample size reaching power
        "power"         post hoc     -> power of an explicit design
        "alpha"         criterion    -> alpha giving the requested power
        "effect-size"   sensitivity  -> detectable effect size
        "compromise"    compromise   -> alpha & beta with beta/alpha = q
    """
    proc = resolve(test)
    requested = solve_for or "n"
    solve_for = _SOLVE_ALIASES.get(_norm_solve(requested), "")
    if solve_for not in SOLVE_MODES:
        raise ValidationError(
            f"unknown solve target {requested!r}; choose from {list(SOLVE_MODES)} "
            f"(the G*Power labels 'a priori', 'post hoc', 'criterion', "
            f"'sensitivity' and 'compromise' are also accepted)"
        )
    if solve_for not in proc.supports_solve:
        raise ValidationError(
            f"{proc.key} does not support solve={solve_for} "
            f"(supported: {list(proc.supports_solve)})"
        )

    _validate_common(alpha if solve_for != "alpha" else None, tails)
    ex = proc.normalise_extra(extra)
    warnings: list[str] = []
    rule = (allocation_rule or DEFAULT_ALLOCATION_RULE).strip().lower()
    ratio = 1.0 if allocation_ratio is None else float(allocation_ratio)
    if proc.two_group and ratio <= 0:
        raise ValidationError("allocation_ratio must be > 0")

    # ---------------------------------------------------------------- a priori
    if solve_for == "n":
        missing = [
            name
            for name, val in (
                ("alpha", alpha),
                ("power", power_target),
                ("effect-size", effect_size),
            )
            if val is None
        ]
        if missing:
            raise ValidationError(
                f"solve=n requires alpha, power and effect-size; "
                f"missing: {', '.join(missing)}"
            )
        if not (0.0 < power_target < 1.0):
            raise ValidationError("power must be in (0,1)")
        _require_nonzero_effect_size(effect_size, "n")
        proc.check_effect_size(effect_size)
        es_eff = abs(effect_size)
        if effect_size < 0:
            warnings.append(
                "negative effect size: |ES| used for the directional search "
                "(SPEC F-08)"
            )
        if power_target <= alpha:
            warnings.append(
                "requested power does not exceed alpha; the smallest "
                "admissible design already satisfies it"
            )

        min_sample = proc.min_sample(ex)
        start = min_sample.n1 if proc.two_group else min_sample.total

        def attains(step: int) -> bool:
            s = _allocate(proc, step, ratio, ex, rule)
            df = proc.df(s, ex)
            if df <= 0:
                return False
            ncp = proc.ncp(s, es_eff, ex)
            pw, _ = _power_from_ncp(alpha, df, ncp, tails)
            return pw >= power_target

        step = _smallest_step(attains, start, N_SEARCH_CAP)
        sample = _allocate(proc, step, ratio, ex, rule)
        df = proc.df(sample, ex)
        ncp = proc.ncp(sample, es_eff, ex)
        pw, t_crit = _power_from_ncp(alpha, df, ncp, tails)
        pt = PowerPoint(pw, alpha, df, ncp, t_crit, tails, sample)
        return _build_result(
            proc,
            "n",
            pt,
            effect_size,
            ex,
            {"power": power_target},
            ratio if proc.two_group else None,
            rule,
            warnings,
        )

    # ---------------------------------------------------------------- post hoc
    if solve_for == "power":
        if alpha is None or effect_size is None:
            raise ValidationError("solve=power requires alpha and effect-size")
        pt = power(
            proc,
            alpha=alpha,
            effect_size=effect_size,
            tails=tails,
            n=n,
            n1=n1,
            n2=n2,
            allocation_ratio=allocation_ratio,
            extra=ex,
        )
        return _build_result(
            proc,
            "power",
            pt,
            effect_size,
            ex,
            {},
            ratio if proc.two_group else None,
            rule,
            warnings,
        )

    # --------------------------------------------------------------- criterion
    if solve_for == "alpha":
        if power_target is None or effect_size is None:
            raise ValidationError("solve=alpha requires power and effect-size")
        if not (0.0 < power_target < 1.0):
            raise ValidationError("power must be in (0,1)")
        _require_nonzero_effect_size(effect_size, "alpha")
        proc.check_effect_size(effect_size)
        sample = _explicit_sample(
            proc, ex, n=n, n1=n1, n2=n2, ratio=allocation_ratio
        )
        df = proc.df(sample, ex)
        if df <= 0:
            raise ValidationError("sample size too small (df <= 0)")
        ncp = proc.ncp(sample, abs(effect_size), ex)
        if effect_size < 0:
            warnings.append(
                "negative effect size: |ES| used for the directional search "
                "(SPEC F-08)"
            )

        # Bisect on log(alpha), not alpha.  The honest answer can be
        # astronomically small -- a large effect at a large N needs
        # alpha ~ 4e-60 to bring power down to 0.05 -- and a linear bracket
        # floored at 1e-12 silently returns the floor instead.  This was a
        # real defect, found by the clean-room pass (SPEC F-13 / G-05).
        def pw_of_log_alpha(la: float) -> float:
            return _power_from_ncp(math.exp(la), df, ncp, tails)[0]

        la = _bisect_scalar(
            pw_of_log_alpha,
            math.log(ALPHA_SEARCH_MIN),
            math.log(ALPHA_SEARCH_MAX),
            power_target,
        )
        a_star = min(max(math.exp(la), ALPHA_SEARCH_MIN), ALPHA_SEARCH_MAX)
        pw, t_crit = _power_from_ncp(a_star, df, ncp, tails)
        pt = PowerPoint(pw, a_star, df, ncp, t_crit, tails, sample)
        return _build_result(
            proc,
            "alpha",
            pt,
            effect_size,
            ex,
            {"power": power_target},
            ratio if proc.two_group else None,
            rule,
            warnings,
        )

    # ------------------------------------------------------------- sensitivity
    if solve_for == "effect-size":
        if alpha is None or power_target is None:
            raise ValidationError("solve=effect-size requires alpha and power")
        if not (0.0 < power_target < 1.0):
            raise ValidationError("power must be in (0,1)")
        sample = _explicit_sample(
            proc, ex, n=n, n1=n1, n2=n2, ratio=allocation_ratio
        )
        df = proc.df(sample, ex)
        if df <= 0:
            raise ValidationError("sample size too small (df <= 0)")

        def pw_of_es(e: float) -> float:
            return _power_from_ncp(alpha, df, proc.ncp(sample, e, ex), tails)[0]

        lo, hi = proc.es_bounds
        es_star = _bisect_scalar(pw_of_es, lo, hi, power_target)
        ncp = proc.ncp(sample, es_star, ex)
        pw, t_crit = _power_from_ncp(alpha, df, ncp, tails)
        pt = PowerPoint(pw, alpha, df, ncp, t_crit, tails, sample)
        return _build_result(
            proc,
            "effect-size",
            pt,
            es_star,
            ex,
            {"power": power_target},
            ratio if proc.two_group else None,
            rule,
            warnings,
        )

    # -------------------------------------------------------------- compromise
    if effect_size is None or beta_alpha_ratio is None:
        raise ValidationError(
            "solve=compromise requires effect-size and beta-alpha-ratio (q)"
        )
    if beta_alpha_ratio <= 0:
        raise ValidationError("beta-alpha-ratio must be > 0")
    _require_nonzero_effect_size(effect_size, "compromise")
    proc.check_effect_size(effect_size)
    sample = _explicit_sample(proc, ex, n=n, n1=n1, n2=n2, ratio=allocation_ratio)
    df = proc.df(sample, ex)
    if df <= 0:
        raise ValidationError("sample size too small (df <= 0)")
    # SPEC F-13 / G-01: compromise is a *solving* analysis, so like the other
    # three it works from |delta|.  SPEC v1.0 listed only three analyses in
    # F-08 and left compromise unassigned; two independent readers then chose
    # differently (alpha = 0.133 vs 0.867 on the same input).
    ncp = proc.ncp(sample, abs(effect_size), ex)
    if effect_size < 0:
        warnings.append(
            "negative effect size: |ES| used for the directional search "
            "(SPEC F-08)"
        )

    def ratio_of_c(c: float) -> float:
        beta, a = _beta_and_alpha(c, df, ncp, tails)
        if a <= 0.0:
            return float("inf")
        return beta / a

    c_star = _bisect_scalar(ratio_of_c, 1e-8, 1e6, beta_alpha_ratio)
    beta, a_star = _beta_and_alpha(c_star, df, ncp, tails)
    pt = PowerPoint(1.0 - beta, a_star, df, ncp, c_star, tails, sample)
    res = _build_result(
        proc,
        "compromise",
        pt,
        effect_size,
        ex,
        {"beta_alpha_ratio": beta_alpha_ratio},
        ratio if proc.two_group else None,
        rule,
        warnings,
    )
    res.target["beta"] = beta
    return res


# --------------------------------------------------------------------------
# Convenience: power as a function of N (for plots / agent explanations)
# --------------------------------------------------------------------------
def power_curve(
    test: str,
    *,
    alpha: float,
    effect_size: float,
    tails: int = 2,
    n_from: int,
    n_to: int,
    n_step: int = 1,
    allocation_ratio: float | None = None,
    allocation_rule: str | None = None,
    extra: Mapping | None = None,
    max_points: int = 500,
) -> list[dict]:
    proc = resolve(test)
    if proc.key == "ttest-generic":
        raise ValidationError("power_curve is not defined for the generic t test")
    _validate_common(alpha, tails)
    ex = proc.normalise_extra(extra)
    proc.check_effect_size(effect_size)
    if n_step <= 0:
        raise ValidationError("n_step must be >= 1")
    if n_to < n_from:
        raise ValidationError("n_to must be >= n_from")
    count = (n_to - n_from) // n_step + 1
    if count > max_points:
        raise ValidationError(
            f"power_curve would produce {count} rows (max {max_points}); "
            f"increase n_step"
        )
    rule = (allocation_rule or DEFAULT_ALLOCATION_RULE).strip().lower()
    ratio = 1.0 if allocation_ratio is None else float(allocation_ratio)

    rows = []
    for step in range(n_from, n_to + 1, n_step):
        sample = _allocate(proc, step, ratio, ex, rule)
        df = proc.df(sample, ex)
        if df <= 0:
            continue
        ncp = proc.ncp(sample, abs(effect_size), ex)
        pw, t_crit = _power_from_ncp(alpha, df, ncp, tails)
        row = {"power": pw, "df": df, "noncentrality": ncp, "critical_t": t_crit}
        row.update(sample.as_dict())
        rows.append(row)
    return rows
