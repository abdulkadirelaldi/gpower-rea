"""Self-checks for the clean-room gpower_cleanroom engine.

Run:  python selfcheck.py      (from this directory, with src/ on sys.path)

Nothing here is a pytest suite; it is a script that prints a line per check and
exits non-zero on any failure.  The checks are of four kinds:

  * numerical tolerances demanded by SPEC.md section 4 (mass closure,
    T(x;nu), t_{p,nu}, T(x;nu,delta)) measured against closed forms and
    against the same quadrature run at much higher resolution;
  * the three internal-consistency identities of F-03, F-04 and F-07;
  * the observable consequences of F-02, F-05, F-06, F-08..F-12;
  * the F-06 published example, to seven decimals.
"""

from __future__ import annotations

import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from gpower_cleanroom import (  # noqa: E402
    TESTS,
    achieved_power,
    cohen_d_from_means,
    compromise,
    detectable_effect_size,
    pooled_sd_equal_n,
    pooled_sd_unequal_n,
    required_alpha,
    required_sample_size,
)
from gpower_cleanroom import _numerics as NUM  # noqa: E402
from gpower_cleanroom._designs import round_half_up  # noqa: E402
from gpower_cleanroom._power import (  # noqa: E402
    alpha_from_critical,
    critical_t,
    power as power_of,
    power_and_beta,
)
from gpower_cleanroom.report import round_for_display  # noqa: E402

FAILURES: list[str] = []
NCHECK = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global NCHECK
    NCHECK += 1
    status = "ok  " if ok else "FAIL"
    print("[%s] %-58s %s" % (status, name, detail))
    if not ok:
        FAILURES.append(name)


def close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


# High-resolution settings for the independent convergence comparison.
DENSE = dict(
    gl_n=40,
    width_factor=1.2,
    levels=(0.125, 0.25, 0.375, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0,
            11.0, 16.0, 23.0, 32.0, 42.0, 52.0, 62.0, 72.0),
)


# ===========================================================================
# 1. SPEC.md section 4 -- numerical requirements
# ===========================================================================

def sec4_mass_closure() -> None:
    """Quadrature mass closure: integrate the weight function alone."""
    dfs = [float(i) for i in range(1, 101)]
    dfs += [1.5, 2.5, 7.25, 123.75]
    v = 100.0
    while v <= 100000.0:
        dfs.append(v)
        v *= 1.3
    dfs.append(100000.0)
    worst = 0.0
    worst_df = None
    for nu in dfs:
        for (x, d) in ((0.0, 0.0), (1.96, 2.5), (-2.0, 1.0), (30.0, 0.0)):
            m = NUM.weight_mass(nu, x, d)
            e = abs(m - 1.0)
            if e > worst:
                worst = e
                worst_df = (nu, x, d)
    check("S4 quadrature mass closure (df 1..1e5) <= 1e-13", worst <= 1e-13,
          "worst %.3e at %s" % (worst, worst_df))

    # also below df = 1, where s^(nu-1) is singular in s (we integrate in log s)
    worst_lo = max(abs(NUM.weight_mass(nu) - 1.0)
                   for nu in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9))
    check("S4 mass closure also holds for 0 < df < 1", worst_lo <= 1e-13,
          "worst %.3e" % worst_lo)


def _central_closed_form(x: float, nu: int) -> float:
    if nu == 1:
        return 0.5 + math.atan(x) / math.pi
    if nu == 2:
        return 0.5 * (1.0 + x / math.sqrt(2.0 + x * x))
    if nu == 3:
        u = x / math.sqrt(3.0)
        return 0.5 + (math.atan(u) + u / (1.0 + u * u)) / math.pi
    if nu == 4:
        s = x / math.sqrt(4.0 + x * x)
        return 0.5 + 0.75 * (s - s ** 3 / 3.0)
    raise AssertionError


def sec4_central_cdf() -> None:
    worst = 0.0
    worst_at = None
    for nu in (1, 2, 3, 4):
        for x in (-400.0, -20.0, -3.3, -1.0, -0.25, 0.0, 0.25, 1.0, 3.3, 20.0,
                  400.0, 1e5):
            got = NUM.student_t_cdf(x, float(nu))
            ref = _central_closed_form(x, nu)
            e = abs(got - ref)
            if e > worst:
                worst = e
                worst_at = (nu, x)
    check("S4 T(x;nu) vs closed forms (nu=1..4) <= 1e-11", worst <= 1e-11,
          "worst %.3e at %s" % (worst, worst_at))

    # normal limit
    worst2 = 0.0
    for x in (-3.0, -1.0, 0.0, 0.5, 1.96, 4.0):
        worst2 = max(worst2, abs(NUM.student_t_cdf(x, 1e13) - NUM.norm_cdf(x)))
    check("S4 T(x;nu) -> Phi(x) as nu -> inf", worst2 <= 1e-11,
          "worst %.3e" % worst2)

    # cdf + sf == 1
    worst3 = 0.0
    for nu in (1.0, 3.5, 17.0, 1000.0, 50000.0):
        for x in (-5.0, -1.0, 0.3, 2.0, 9.0):
            worst3 = max(worst3, abs(NUM.student_t_cdf(x, nu)
                                     + NUM.student_t_sf(x, nu) - 1.0))
    check("S4 T(x;nu) + (1 - T(x;nu)) == 1", worst3 <= 1e-14,
          "worst %.3e" % worst3)


def sec4_quantile() -> None:
    # closed-form inverses for nu = 1 and nu = 2
    worst = 0.0
    worst_at = None
    # SPEC.md section 4 asks for t_{p,nu} with p in [0.5, 1); the natural,
    # well-conditioned parametrisation of that range is the tail probability
    # q = 1-p, which is what student_t_isf takes.  (Writing p = 1-1e-8 as a
    # double already destroys more than 1e-10 of the quantile for nu = 1, so a
    # test phrased in p could not distinguish engine error from input
    # granularity.)  The closed-form references below are likewise written in
    # complement form so that they are the accurate side of the comparison.
    for q in (1e-12, 1e-8, 1e-4, 0.001, 0.01, 0.025, 0.05, 0.1, 0.3, 0.49):
        # nu = 1 :  sf(t) = q  =>  t = cot(pi*q)
        ref1 = 1.0 / math.tan(math.pi * q)
        got1 = NUM.student_t_isf(q, 1.0)
        e = abs(got1 - ref1) / abs(ref1)
        if e > worst:
            worst = e
            worst_at = ("nu=1, p=1-%g" % q, got1)
        # nu = 2 :  t = (1-2q)/sqrt(2*q*(1-q))
        ref2 = (1.0 - 2.0 * q) / math.sqrt(2.0 * q * (1.0 - q))
        got2 = NUM.student_t_isf(q, 2.0)
        e = abs(got2 - ref2) / abs(ref2)
        if e > worst:
            worst = e
            worst_at = ("nu=2, p=1-%g" % q, got2)
        # and the mirrored lower tail, through student_t_ppf
        for nu, ref in ((1.0, -ref1), (2.0, -ref2)):
            got = NUM.student_t_ppf(q, nu)
            e = abs(got - ref) / abs(ref)
            if e > worst:
                worst = e
                worst_at = ("ppf nu=%g p=%g" % (nu, q), got)
    check("S4 t_{p,nu} vs closed forms (nu=1,2) <= 1e-10 rel", worst <= 1e-10,
          "worst %.3e at %s" % (worst, worst_at))
    check("S4 t_{0.5,nu} == 0 exactly",
          all(NUM.student_t_ppf(0.5, nu) == 0.0
              for nu in (1.0, 2.0, 7.5, 1e5)))

    # round trip over a wide grid
    worst2 = 0.0
    worst_at2 = None
    for nu in (1.0, 1.7, 2.0, 5.0, 13.0, 98.0, 208.0, 5000.0, 100000.0):
        for p in (1e-14, 1e-10, 1e-6, 1e-3, 0.005, 0.025, 0.05, 0.2, 0.5,
                  0.8, 0.95, 0.999, 1 - 1e-6):
            t = NUM.student_t_isf(p, nu)
            back = NUM.student_t_sf(t, nu)
            e = abs(back - p) / p
            if e > worst2:
                worst2 = e
                worst_at2 = (nu, p)
    check("S4 sf(t_{1-p,nu}) == p to 1e-11 rel", worst2 <= 1e-11,
          "worst %.3e at %s" % (worst2, worst_at2))


def sec4_noncentral() -> None:
    # T(0;nu,delta) == Phi(-delta) exactly
    worst = 0.0
    for nu in (1.0, 2.5, 10.0, 500.0, 1e5):
        for d in (-4.0, -1.0, 0.0, 0.7, 3.0, 9.0):
            worst = max(worst, abs(NUM.nct_cdf(0.0, nu, d) - NUM.norm_cdf(-d)))
    check("S4 T(0;nu,delta) == Phi(-delta)", worst == 0.0, "worst %.3e" % worst)

    # reflection identity  T(x;nu,delta) + T(-x;nu,-delta) == 1
    worst = 0.0
    worst_at = None
    for nu in (1.0, 3.0, 11.5, 208.0, 20000.0):
        for x in (-6.0, -1.3, 0.4, 2.0, 7.0):
            for d in (-5.0, -0.5, 0.0, 1.0, 4.5):
                e = abs(NUM.nct_cdf(x, nu, d) + NUM.nct_cdf(-x, nu, -d) - 1.0)
                if e > worst:
                    worst = e
                    worst_at = (nu, x, d)
    check("S4 T(x;nu,d) + T(-x;nu,-d) == 1 <= 1e-14", worst <= 1e-14,
          "worst %.3e at %s" % (worst, worst_at))

    # normal limit
    worst = 0.0
    for x in (-2.0, 0.5, 2.0, 5.0):
        for d in (-1.0, 0.0, 2.5):
            worst = max(worst, abs(NUM.nct_cdf(x, 1e13, d) - NUM.norm_cdf(x - d)))
    check("S4 T(x;nu,d) -> Phi(x-d) as nu -> inf", worst <= 1e-10,
          "worst %.3e" % worst)

    # independent resolution comparison: default grid vs a much denser one
    random.seed(20240101)
    worst_abs = 0.0
    worst_at = None
    for _ in range(400):
        nu = math.exp(random.uniform(math.log(1.0), math.log(2e5)))
        x = random.uniform(-9.0, 12.0)
        d = random.uniform(-10.0, 10.0)
        for fn in (NUM.nct_cdf, NUM.nct_sf):
            a = fn(x, nu, d)
            b = fn(x, nu, d, **DENSE)
            e = abs(a - b)
            if e > worst_abs:
                worst_abs = e
                worst_at = (nu, x, d, fn.__name__)
    check("S4 T(x;nu,delta) resolution-converged <= 1e-10 abs",
          worst_abs <= 1e-10, "worst %.3e at %s" % (worst_abs, worst_at))

    # cdf + sf == 1 for the noncentral case
    worst = 0.0
    for nu in (1.0, 4.0, 77.0, 9000.0):
        for x in (-3.0, 1.1, 6.0):
            for d in (-2.0, 0.0, 3.0):
                worst = max(worst, abs(NUM.nct_cdf(x, nu, d)
                                       + NUM.nct_sf(x, nu, d) - 1.0))
    check("S4 T + (1-T) == 1 (noncentral)", worst <= 1e-14, "worst %.3e" % worst)


def sec4_lgamma_cancellation() -> None:
    """log_gamma_ratio must beat the naive lgamma difference."""
    worst_naive = 0.0
    worst_ours = 0.0
    for a in (0.5, 1.0, 7.0, 100.0, 2500.0, 50000.0, 5e6):
        # exact-ish reference: build the ratio by a long double-free route --
        # Gauss multiplication is unavailable, so compare the two against each
        # other and against the recurrence identity
        #   G(a,0.5) + G(a+0.5,0.5) == log(a)      (since Gamma(a+1)=a*Gamma(a))
        ours = NUM.log_gamma_ratio(a, 0.5) + NUM.log_gamma_ratio(a + 0.5, 0.5)
        naive = ((math.lgamma(a + 0.5) - math.lgamma(a))
                 + (math.lgamma(a + 1.0) - math.lgamma(a + 0.5)))
        ref = math.log(a)
        worst_ours = max(worst_ours, abs(ours - ref))
        worst_naive = max(worst_naive, abs(naive - ref))
    check("S4 log_gamma_ratio identity G(a,.5)+G(a+.5,.5)=log a <= 1e-14",
          worst_ours <= 1e-14,
          "ours %.3e vs naive lgamma diff %.3e" % (worst_ours, worst_naive))


# ===========================================================================
# 2. The findings
# ===========================================================================

def f02_far_tail() -> None:
    """At delta = 0 the full two-tailed expression returns exactly alpha."""
    worst = 0.0
    worst_at = None
    for nu in (1.0, 2.0, 9.0, 53.0, 208.0, 10000.0):
        for alpha in (0.001, 0.01, 0.05, 0.2, 0.5, 0.8, 0.95):
            p2 = power_of(nu, 0.0, alpha, 2)
            p1 = power_of(nu, 0.0, alpha, 1)
            e = max(abs(p2 - alpha), abs(p1 - alpha))
            if e > worst:
                worst = e
                worst_at = (nu, alpha)
    check("F-02 power at delta=0 equals alpha exactly (k=1 and k=2)",
          worst <= 5e-15, "worst %.3e at %s" % (worst, worst_at))

    # the truncated (far-tail-dropped) formula is observably different
    nu, alpha = 20.0, 0.5
    c = critical_t(alpha, nu, 2)
    full = power_of(nu, 0.0, alpha, 2)
    trunc = NUM.nct_sf(c, nu, 0.0)
    check("F-02 dropping the far-tail term halves the answer at delta=0",
          close(full, alpha, 1e-15) and close(trunc, alpha / 2.0, 1e-15),
          "full %.12f truncated %.12f" % (full, trunc))

    # it matters at small, non-zero delta too
    nu, delta, alpha = 40.0, 0.35, 0.10
    c = critical_t(alpha, nu, 2)
    full = power_of(nu, delta, alpha, 2)
    trunc = NUM.nct_sf(c, nu, delta)
    check("F-02 far-tail term is non-negligible at small delta",
          full - trunc > 1e-3, "difference %.3e" % (full - trunc))

    # ... and negligible for large |delta| (SPEC: below 1e-9 at delta >~ 6)
    c = critical_t(0.05, 100.0, 2)
    gap = NUM.nct_cdf(-c, 100.0, 6.5)
    check("F-02 far-tail term < 1e-9 at delta ~ 6.5", gap < 1e-9,
          "far tail %.3e" % gap)


def f03_one_sample_equals_paired() -> None:
    bad = []
    for alpha in (0.01, 0.05):
        for tails in (1, 2):
            for es in (-0.8, 0.2, 0.5, 1.3):
                for n in (2, 3, 7, 30, 54, 500):
                    a = achieved_power("ttest-one-sample", alpha=alpha,
                                       effect_size=es, tails=tails, n=n)
                    b = achieved_power("ttest-paired-means", alpha=alpha,
                                       effect_size=es, tails=tails, n=n)
                    for k in ("power", "df", "ncp", "critical_t", "n1", "total"):
                        if a[k] != b[k]:
                            bad.append((alpha, tails, es, n, k))
            for pw in (0.8, 0.95):
                a = required_sample_size("ttest-one-sample", alpha=alpha,
                                         power=pw, effect_size=0.4, tails=tails)
                b = required_sample_size("ttest-paired-means", alpha=alpha,
                                         power=pw, effect_size=0.4, tails=tails)
                for k in ("n1", "total", "power", "df", "ncp"):
                    if a[k] != b[k]:
                        bad.append((alpha, tails, "apriori", k))
    check("F-03 one sample == matched pairs, bit-identical", not bad,
          "%d mismatches" % len(bad))

    # N is the number of pairs: nu = N - 1, delta = ES*sqrt(N)
    r = achieved_power("ttest-paired-means", alpha=0.05, effect_size=0.5, n=54)
    check("F-03 matched pairs with 54 pairs has nu = 53 (not 107)",
          r["df"] == 53.0 and close(r["ncp"], 0.5 * math.sqrt(54), 1e-15),
          "nu=%g ncp=%.10f" % (r["df"], r["ncp"]))


def f04_point_biserial_equals_two_group() -> None:
    bad = []
    worst = 0.0
    for r in (0.05, 0.1, 0.3, 0.5, 0.7, 0.9):
        d = 2.0 * r / math.sqrt(1.0 - r * r)
        for N in (4, 6, 10, 30, 64, 200, 1000):
            a = achieved_power("ttest-point-biserial", alpha=0.05,
                               effect_size=r, n=N)
            b = achieved_power("ttest-indep-means", alpha=0.05,
                               effect_size=d, n1=N // 2, n2=N // 2)
            if a["df"] != b["df"]:
                bad.append(("df", r, N))
            worst = max(worst, abs(a["ncp"] - b["ncp"]) / max(1.0, abs(a["ncp"])),
                        abs(a["power"] - b["power"]))
    check("F-04 point biserial == balanced two group under d=2r/sqrt(1-r^2)",
          not bad and worst <= 1e-14, "worst %.3e, %d df mismatches"
          % (worst, len(bad)))

    # the radicand is N, not N-2
    N, r = 12, 0.4
    res = achieved_power("ttest-point-biserial", alpha=0.05, effect_size=r, n=N)
    want = r * math.sqrt(N / (1.0 - r * r))
    wrong = r * math.sqrt((N - 2) / (1.0 - r * r))
    check("F-04 delta uses sqrt(N/(1-r^2)), not sqrt((N-2)/(1-r^2))",
          close(res["ncp"], want, 1e-15) and abs(want - wrong) > 1e-3,
          "ncp %.10f (sqrt(N-2) form would be %.10f)" % (res["ncp"], wrong))


def f07_regression_equals_point_biserial() -> None:
    bad = []
    worst = 0.0
    for r in (0.1, 0.25, 0.5, 0.8):
        f2 = r * r / (1.0 - r * r)
        for N in (4, 5, 11, 40, 123, 900):
            a = achieved_power("ttest-point-biserial", alpha=0.05,
                               effect_size=r, n=N)
            b = achieved_power("ttest-regression-coef", alpha=0.05,
                               effect_size=f2, n=N, predictors=1)
            if a["df"] != b["df"]:
                bad.append(("df", r, N))
            worst = max(worst, abs(a["ncp"] - b["ncp"]),
                        abs(a["power"] - b["power"]))
        for pw in (0.8, 0.95):
            a = required_sample_size("ttest-point-biserial", alpha=0.05,
                                     power=pw, effect_size=r)
            b = required_sample_size("ttest-regression-coef", alpha=0.05,
                                     power=pw, effect_size=f2, predictors=1)
            if (a["n1"], a["total"]) != (b["n1"], b["total"]):
                bad.append(("N", r, pw, a["total"], b["total"]))
            worst = max(worst, abs(a["power"] - b["power"]))
    check("F-07 regression (p=1, f2=r^2/(1-r^2)) == point biserial",
          not bad and worst <= 1e-13, "worst %.3e, %d mismatches"
          % (worst, len(bad)))

    # the predictor count enters nu only
    res = achieved_power("ttest-regression-coef", alpha=0.05, effect_size=0.15,
                         n=60, predictors=4)
    check("F-07 nu = N-p-1 and delta = sqrt(f2*N) (p absent from delta)",
          res["df"] == 55.0 and close(res["ncp"], math.sqrt(0.15 * 60), 1e-15),
          "nu=%g ncp=%.10f" % (res["df"], res["ncp"]))


def f05_f06_balanced_grid() -> None:
    odd = []
    checked = 0
    for alpha in (0.01, 0.05, 0.1):
        for pw in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99):
            for d in (0.15, 0.2, 0.3, 0.5, 0.8, 1.2, 2.0):
                for tails in (1, 2):
                    r = required_sample_size("ttest-indep-means", alpha=alpha,
                                             power=pw, effect_size=d,
                                             tails=tails, allocation_ratio=1.0)
                    checked += 1
                    if r["total"] % 2 == 1:
                        odd.append((alpha, pw, d, tails, r["total"]))
                    if r["n1"] != r["n2"]:
                        odd.append(("unbalanced", alpha, pw, d, tails))
    check("F-05 balanced a-priori never returns an odd total (%d settings)"
          % checked, not odd, "%d violations" % len(odd))

    # The search space is n1, not N: there exist settings where the odd split
    # (n, n+1) already reaches the target and (n+1, n+1) is reported anyway.
    found = None
    for alpha in (0.05, 0.01, 0.1):
        for pw in (0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
            for d in [0.1 + 0.01 * i for i in range(0, 120)]:
                r = required_sample_size("ttest-indep-means", alpha=alpha,
                                         power=pw, effect_size=d, tails=2)
                n = r["n1"]
                if n < 3:
                    continue
                odd_power = achieved_power("ttest-indep-means", alpha=alpha,
                                           effect_size=d, n1=n - 1, n2=n)["power"]
                if odd_power >= pw:
                    found = (alpha, pw, round(d, 4), n, odd_power, r["power"])
                    break
            if found:
                break
        if found:
            break
    check("F-05 an odd split (n,n+1) can already reach the target yet "
          "(n+1,n+1) is reported", found is not None, str(found))

    # F-06 minimality: the predecessor grid point must miss the target
    bad = []
    for alpha in (0.05, 0.02):
        for pw in (0.8, 0.9, 0.95):
            for d in (0.2, 0.35, 0.6, 1.0):
                r = required_sample_size("ttest-indep-means", alpha=alpha,
                                         power=pw, effect_size=d, tails=2)
                if r["power"] < pw:
                    bad.append(("actual below target", alpha, pw, d))
                if r["n1"] > 2:
                    prev = achieved_power("ttest-indep-means", alpha=alpha,
                                          effect_size=d, n1=r["n1"] - 1,
                                          n2=r["n1"] - 1)["power"]
                    if prev >= pw:
                        bad.append(("not minimal", alpha, pw, d))
    check("F-06 returned design is minimal and its power >= target", not bad,
          "%d violations" % len(bad))


def f06_published_example() -> None:
    r = required_sample_size("ttest-indep-means", alpha=0.05, power=0.95,
                             effect_size=0.5, tails=2, allocation_ratio=1.0)
    disp = round_for_display(r)
    ok = (r["n1"] == 105 and r["n2"] == 105 and r["total"] == 210
          and disp["df"] == 208
          and disp["ncp"] == 3.6228442
          and disp["power"] == 0.9501287)
    check("F-06 published example reproduced to 7 decimals", ok,
          "n1=%d n2=%d N=%d nu=%s delta=%.7f actual power=%.7f"
          % (r["n1"], r["n2"], r["total"], disp["df"], r["ncp"], r["power"]))
    # target and actual are two distinct reported numbers
    check("F-06 target and actual power are reported separately",
          r["target_power"] == 0.95 and r["power"] != r["target_power"],
          "target %.7f actual %.7f" % (r["target_power"], r["power"]))


def f08_sign() -> None:
    a = achieved_power("ttest-one-sample", alpha=0.05, effect_size=-0.5,
                       tails=1, n=30)
    check("F-08 one-tailed post-hoc power with negative ES is below alpha "
          "and unclamped", 0.0 < a["power"] < 0.05,
          "power %.3e" % a["power"])

    b = achieved_power("ttest-one-sample", alpha=0.05, effect_size=-0.5,
                       tails=2, n=30)
    c = achieved_power("ttest-one-sample", alpha=0.05, effect_size=0.5,
                       tails=2, n=30)
    check("F-08 two-tailed power is sign-symmetric",
          close(b["power"], c["power"], 1e-15),
          "%.12f vs %.12f" % (b["power"], c["power"]))

    for fn, kw in (
        (required_sample_size, dict(alpha=0.05, power=0.8, effect_size=-0.5,
                                    tails=1)),
        (required_alpha, dict(power=0.8, effect_size=-0.5, tails=1, n=30)),
    ):
        r = fn("ttest-one-sample", **kw)
        pos = fn("ttest-one-sample", **{**kw, "effect_size": 0.5})
        same = all(r[k] == pos[k] for k in ("n1", "total", "power", "alpha", "df"))
        check("F-08 %s uses |delta| and warns" % fn.__name__,
              same and any("F-08" in w for w in r["warnings"]),
              "warnings=%d" % len(r["warnings"]))


def f09_allocation() -> None:
    check("F-09 round_half_up(2.5) == 3 (not IEEE half-to-even)",
          round_half_up(2.5) == 3 and round_half_up(3.5) == 4
          and round_half_up(0.5) == 1 and round(2.5) == 2,
          "round_half_up(2.5)=%d, python round(2.5)=%d"
          % (round_half_up(2.5), round(2.5)))

    # n1-grid reproduces the ratio exactly; n2 = round_half_up(R*n1)
    bad = []
    for R in (0.5, 0.75, 1.5, 2.0, 2.5, 3.0, 4.0, 1.0 / 3.0):
        for d in (0.2, 0.5, 0.9):
            for pw in (0.8, 0.95):
                r = required_sample_size("ttest-indep-means", alpha=0.05,
                                         power=pw, effect_size=d, tails=2,
                                         allocation_ratio=R)
                if r["n2"] != round_half_up(R * r["n1"]):
                    bad.append((R, d, pw, r["n1"], r["n2"]))
    check("F-09 n1-grid sets n2 = round_half_up(R*n1)", not bad,
          "%d violations" % len(bad))

    # total-grid never needs more participants than n1-grid
    worse = []
    equal = 0
    differ = 0
    for R in (0.5, 0.75, 1.5, 2.0, 2.5, 3.0, 4.0, 1.0 / 3.0):
        for d in (0.2, 0.35, 0.5, 0.7, 0.9, 1.3):
            for pw in (0.8, 0.9, 0.95):
                a = required_sample_size("ttest-indep-means", alpha=0.05,
                                         power=pw, effect_size=d, tails=2,
                                         allocation_ratio=R,
                                         allocation_rule="n1-grid")
                b = required_sample_size("ttest-indep-means", alpha=0.05,
                                         power=pw, effect_size=d, tails=2,
                                         allocation_ratio=R,
                                         allocation_rule="total-grid")
                if b["total"] > a["total"]:
                    worse.append((R, d, pw, a["total"], b["total"]))
                if b["total"] == a["total"]:
                    equal += 1
                else:
                    differ += 1
    check("F-09 total-grid never needs more than n1-grid", not worse,
          "%d violations; grids differ on %d/%d settings"
          % (len(worse), differ, differ + equal))

    # R = 1.5 with odd n1 lands on a half-integer -> rounding rule observable
    check("F-09 R=1.5, n1=5 -> n2=8 (half-away-from-zero)",
          round_half_up(1.5 * 5) == 8, "round_half_up(7.5)=%d"
          % round_half_up(1.5 * 5))

    # R = 1 under total-grid must still be balanced-equivalent
    a = required_sample_size("ttest-indep-means", alpha=0.05, power=0.95,
                             effect_size=0.5, allocation_rule="n1-grid")
    b = required_sample_size("ttest-indep-means", alpha=0.05, power=0.95,
                             effect_size=0.5, allocation_rule="total-grid")
    check("F-09 at R=1 both grids agree on the F-06 example",
          b["total"] <= a["total"] and a["total"] == 210,
          "n1-grid N=%d, total-grid N=%d (n1=%d n2=%d)"
          % (a["total"], b["total"], b["n1"], b["n2"]))


def f10_compromise() -> None:
    bad = []
    worst = 0.0
    for test, kw in (
        ("ttest-indep-means", dict(n1=30, n2=45)),
        ("ttest-one-sample", dict(n=25)),
        ("ttest-point-biserial", dict(n=40)),
        ("ttest-regression-coef", dict(n=60, predictors=3)),
        ("ttest-generic", dict(df=17.0)),
    ):
        es = 1.5 if test == "ttest-generic" else (
            0.3 if test == "ttest-point-biserial" else
            (0.1 if test == "ttest-regression-coef" else 0.5))
        for tails in (1, 2):
            for q in (0.01, 0.2, 1.0, 4.0, 50.0):
                r = compromise(test, effect_size=es, beta_alpha_ratio=q,
                               tails=tails, **kw)
                c = r["critical_t"]
                nu, delta = r["df"], r["ncp"]
                a = alpha_from_critical(nu, c, tails)
                pw, bt = power_and_beta(nu, delta, c, tails)
                if a <= 0.0:
                    bad.append((test, tails, q, "alpha<=0"))
                    continue
                worst = max(worst, abs(bt / a - q) / q)
                if not close(r["alpha"], a, 1e-14):
                    bad.append((test, tails, q, "alpha"))
                if not close(r["power"], 1.0 - bt, 1e-14):
                    bad.append((test, tails, q, "power"))
                if not close(r["power"] + r["beta"], 1.0, 1e-14):
                    bad.append((test, tails, q, "sum"))
    check("F-10 compromise solves beta(c)/alpha(c) = q and reports alpha, 1-beta",
          not bad and worst <= 1e-9,
          "worst ratio error %.3e rel, %d inconsistencies" % (worst, len(bad)))

    # beta(c) for k=2 is the exact complement of F-02's power expression
    nu, delta, c = 48.0, 2.0, 1.8
    pw, bt = power_and_beta(nu, delta, c, 2)
    direct = (NUM.nct_cdf(c, nu, delta) - NUM.nct_cdf(-c, nu, delta))
    check("F-10 k=2 beta includes the far-tail term",
          close(bt, direct, 1e-14) and close(pw + bt, 1.0, 1e-15),
          "beta %.12f vs direct %.12f" % (bt, direct))


def f11_pooling() -> None:
    rms = pooled_sd_equal_n(2.0, 6.0)
    pooled = pooled_sd_unequal_n(2.0, 6.0, 10, 40)
    rel = abs(rms - pooled) / pooled
    check("F-11 equal-n option is an RMS, not the pooled SD",
          close(rms, math.sqrt((4.0 + 36.0) / 2.0), 1e-15) and 0.10 < rel < 0.20,
          "rms %.6f pooled %.6f differ by %.1f%%" % (rms, pooled, 100 * rel))

    check("F-11 the two coincide when sd1 == sd2",
          close(pooled_sd_equal_n(3.0, 3.0),
                pooled_sd_unequal_n(3.0, 3.0, 7, 90), 1e-15))
    check("F-11 the two coincide when n1 == n2",
          close(pooled_sd_equal_n(2.0, 6.0),
                pooled_sd_unequal_n(2.0, 6.0, 25, 25), 1e-15))

    d_rms = cohen_d_from_means(10.0, 8.0, 2.0, 6.0, n1=10, n2=40,
                              option="equal-n")
    d_pool = cohen_d_from_means(10.0, 8.0, 2.0, 6.0, n1=10, n2=40,
                                option="unequal-n")
    na = required_sample_size("ttest-indep-means", alpha=0.05, power=0.8,
                              effect_size=d_rms, allocation_ratio=4.0)
    nb = required_sample_size("ttest-indep-means", alpha=0.05, power=0.8,
                              effect_size=d_pool, allocation_ratio=4.0)
    check("F-11 the choice propagates into the required sample size",
          na["total"] != nb["total"],
          "d=%.6f -> N=%d ; d=%.6f -> N=%d"
          % (d_rms, na["total"], d_pool, nb["total"]))


def f12_boundary_and_precision() -> None:
    # No epsilon slack: a design whose power equals the target exactly in
    # double precision is accepted.
    d, alpha, tails = 0.5, 0.05, 2
    exact = achieved_power("ttest-indep-means", alpha=alpha, effect_size=d,
                           n1=64, n2=64)["power"]
    r = required_sample_size("ttest-indep-means", alpha=alpha, power=exact,
                             effect_size=d, tails=tails)
    check("F-12 power == target (to the last bit) is accepted, not rejected",
          r["n1"] == 64, "target %.17g -> n1 = %d" % (exact, r["n1"]))

    # ... and a target one ulp above is not
    nxt = math.nextafter(exact, 1.0)
    r2 = required_sample_size("ttest-indep-means", alpha=alpha, power=nxt,
                              effect_size=d, tails=tails)
    check("F-12 one ulp above that power needs the next grid point",
          r2["n1"] == 65, "target %.17g -> n1 = %d" % (nxt, r2["n1"]))

    # Searching on display-rounded power would differ: find a grid point whose
    # true power is below the target but whose 7-decimal rounding is not.
    found = None
    for alpha in (0.05, 0.01, 0.1):
        for d in (0.2, 0.3, 0.5, 0.8):
            for n in range(5, 400):
                p = achieved_power("ttest-indep-means", alpha=alpha,
                                   effect_size=d, n1=n, n2=n)["power"]
                tgt = round(p, 7)
                if p < tgt:
                    rr = required_sample_size("ttest-indep-means", alpha=alpha,
                                              power=tgt, effect_size=d)
                    if rr["n1"] == n + 1:
                        found = (alpha, d, n, p, tgt)
                        break
            if found:
                break
        if found:
            break
    check("F-12 searching on rounded power would differ by one grid point",
          found is not None,
          "" if found is None else
          "alpha=%g d=%g n=%d: true %.17g < rounded target %.7f, needs n=%d"
          % (found[0], found[1], found[2], found[3], found[4], found[2] + 1))

    # display rounding is display only
    r = required_sample_size("ttest-indep-means", alpha=0.05, power=0.95,
                             effect_size=0.5)
    disp = round_for_display(r)
    check("F-12 full precision kept in the result, rounded only for display",
          r["power"] != disp["power"] and isinstance(disp["df"], int),
          "%.17g -> %.7f, nu %r" % (r["power"], disp["power"], disp["df"]))


# ===========================================================================
# 3. Round trips, interface and error handling
# ===========================================================================

DESIGNS = {
    "ttest-indep-means": dict(n1=25, n2=35),
    "ttest-paired-means": dict(n=40),
    "ttest-one-sample": dict(n=40),
    "ttest-point-biserial": dict(n=52),
    "ttest-regression-coef": dict(n=80, predictors=5),
    "ttest-generic": dict(df=30.0),
}
EFFECTS = {
    "ttest-indep-means": 0.6,
    "ttest-paired-means": 0.45,
    "ttest-one-sample": 0.45,
    "ttest-point-biserial": 0.35,
    "ttest-regression-coef": 0.12,
    "ttest-generic": 2.4,
}


def round_trips() -> None:
    bad = []
    for test in TESTS:
        kw = DESIGNS[test]
        es = EFFECTS[test]
        for tails in (1, 2):
            ph = achieved_power(test, alpha=0.05, effect_size=es, tails=tails, **kw)
            # criterion
            cr = required_alpha(test, power=ph["power"], effect_size=es,
                                tails=tails, **kw)
            if not close(cr["alpha"], 0.05, 1e-10):
                bad.append(("criterion", test, tails, cr["alpha"]))
            # sensitivity
            se = detectable_effect_size(test, alpha=0.05, power=ph["power"],
                                        tails=tails, **kw)
            if not close(se["effect_size"], es, 1e-9):
                bad.append(("sensitivity", test, tails, se["effect_size"]))
            # compromise
            co = compromise(test, effect_size=es, beta_alpha_ratio=3.0,
                            tails=tails, **kw)
            if not close(co["beta"] / co["alpha"], 3.0, 1e-9):
                bad.append(("compromise", test, tails))
            # a priori -> post hoc
            if test != "ttest-generic":
                ap = required_sample_size(test, alpha=0.05, power=0.8,
                                          effect_size=es, tails=tails,
                                          predictors=kw.get("predictors"))
                sizes = ({"n1": ap["n1"], "n2": ap["n2"]}
                         if test == "ttest-indep-means" else {"n": ap["n1"]})
                back = achieved_power(test, alpha=0.05, effect_size=es,
                                      tails=tails,
                                      predictors=kw.get("predictors"), **sizes)
                if back["power"] != ap["power"]:
                    bad.append(("apriori/posthoc", test, tails))
    check("round trips: criterion / sensitivity / compromise / a priori",
          not bad, "%d mismatches %s" % (len(bad), bad[:3]))


def interface_surface() -> None:
    import gpower_cleanroom as G
    check("INTERFACE TESTS tuple has the six keys in order",
          G.TESTS == ("ttest-indep-means", "ttest-paired-means",
                      "ttest-one-sample", "ttest-point-biserial",
                      "ttest-regression-coef", "ttest-generic"),
          str(G.TESTS))
    required_keys = {"n1", "n2", "total", "power", "alpha", "effect_size",
                     "df", "ncp", "critical_t"}
    missing = []
    for test in TESTS:
        kw = DESIGNS[test]
        r = achieved_power(test, alpha=0.05, effect_size=EFFECTS[test], **kw)
        if not required_keys <= set(r):
            missing.append(test)
        if not (isinstance(r["n1"], int) and isinstance(r["n2"], int)
                and isinstance(r["total"], int)):
            missing.append((test, "int types"))
    check("every result dict carries the INTERFACE keys with the right types",
          not missing, str(missing))
    g = achieved_power("ttest-generic", alpha=0.05, effect_size=2.0, df=12.0)
    check("ttest-generic: effect_size is the ncp, total is 0",
          g["ncp"] == 2.0 and g["total"] == 0 and g["df"] == 12.0)


def error_handling() -> None:
    def raises(exc, fn, *a, **k):
        try:
            fn(*a, **k)
        except exc:
            return True
        except Exception as e:  # noqa: BLE001
            return "wrong exception: %r" % (e,)
        return False

    cases = [
        ("unknown test key", ValueError, achieved_power, ("nope",),
         dict(alpha=0.05, effect_size=0.5, n=10)),
        ("alpha out of (0,1)", ValueError, achieved_power, ("ttest-one-sample",),
         dict(alpha=0.0, effect_size=0.5, n=10)),
        ("alpha = 1", ValueError, achieved_power, ("ttest-one-sample",),
         dict(alpha=1.0, effect_size=0.5, n=10)),
        ("power out of (0,1)", ValueError, required_sample_size,
         ("ttest-one-sample",), dict(alpha=0.05, power=1.0, effect_size=0.5)),
        ("tails not in {1,2}", ValueError, achieved_power, ("ttest-one-sample",),
         dict(alpha=0.05, effect_size=0.5, n=10, tails=3)),
        ("|r| >= 1", ValueError, achieved_power, ("ttest-point-biserial",),
         dict(alpha=0.05, effect_size=1.0, n=10)),
        ("df <= 0 (N too small)", ValueError, achieved_power,
         ("ttest-one-sample",), dict(alpha=0.05, effect_size=0.5, n=1)),
        ("df <= 0 (two group)", ValueError, achieved_power,
         ("ttest-indep-means",), dict(alpha=0.05, effect_size=0.5, n1=1, n2=5)),
        ("df <= 0 (regression)", ValueError, achieved_power,
         ("ttest-regression-coef",),
         dict(alpha=0.05, effect_size=0.1, n=5, predictors=4)),
        ("generic df <= 0", ValueError, achieved_power, ("ttest-generic",),
         dict(alpha=0.05, effect_size=1.0, df=0.0)),
        ("a priori unsupported for generic", ValueError, required_sample_size,
         ("ttest-generic",), dict(alpha=0.05, power=0.8, effect_size=1.0)),
        ("missing predictors", ValueError, achieved_power,
         ("ttest-regression-coef",), dict(alpha=0.05, effect_size=0.1, n=50)),
        ("bad allocation rule", ValueError, required_sample_size,
         ("ttest-indep-means",), dict(alpha=0.05, power=0.8, effect_size=0.5,
                                      allocation_rule="whatever")),
        ("bad allocation ratio", ValueError, required_sample_size,
         ("ttest-indep-means",), dict(alpha=0.05, power=0.8, effect_size=0.5,
                                      allocation_ratio=0.0)),
    ]
    bad = []
    for name, exc, fn, a, k in cases:
        r = raises(exc, fn, *a, **k)
        if r is not True:
            bad.append((name, r))
    check("ValueError on out-of-domain input (%d cases)" % len(cases), not bad,
          str(bad))

    # RuntimeError, with the cap mentioned
    try:
        detectable_effect_size("ttest-one-sample", alpha=1e-10, power=0.999999,
                               n=2)
        ok1 = False
        msg1 = "no exception"
    except RuntimeError as e:
        ok1 = True
        msg1 = str(e)[:40]
    except Exception as e:  # noqa: BLE001
        ok1 = False
        msg1 = repr(e)
    check("RuntimeError when the sensitivity target is unattainable", ok1, msg1)

    try:
        required_sample_size("ttest-one-sample", alpha=1e-12, power=0.999999,
                             effect_size=1e-7)
        ok2 = False
        msg2 = "no exception"
    except RuntimeError as e:
        ok2 = "10000000" in str(e)
        msg2 = str(e)[:70]
    except Exception as e:  # noqa: BLE001
        ok2 = False
        msg2 = repr(e)
    check("RuntimeError naming the 10,000,000 cap", ok2, msg2)


def monotonicity() -> None:
    """Power must be monotone in n on every grid used by the a-priori search."""
    bad = []
    for R in (1.0, 1.5, 2.0, 0.4, 2.5):
        prev = -1.0
        for n1 in range(2, 90):
            n2 = round_half_up(R * n1)
            if n2 < 2:
                continue
            p = achieved_power("ttest-indep-means", alpha=0.05,
                               effect_size=0.4, n1=n1, n2=n2)["power"]
            if p < prev - 1e-15:
                bad.append(("n1-grid", R, n1))
            prev = p
        prev = -1.0
        for N in range(4, 200):
            a = round_half_up(N / (1.0 + R))
            b = N - a
            if a < 2 or b < 2:
                continue
            p = achieved_power("ttest-indep-means", alpha=0.05,
                               effect_size=0.4, n1=a, n2=b)["power"]
            if p < prev - 1e-15:
                bad.append(("total-grid", R, N))
            prev = p
    check("both F-09 grids are monotone in the search index (bisection exact)",
          not bad, "%d violations %s" % (len(bad), bad[:3]))


def main() -> int:
    t0 = time.time()
    print("=" * 96)
    print("SPEC.md section 4 -- numerical requirements")
    print("=" * 96)
    sec4_mass_closure()
    sec4_central_cdf()
    sec4_quantile()
    sec4_noncentral()
    sec4_lgamma_cancellation()
    print()
    print("=" * 96)
    print("SPEC.md section 2 -- findings F-01 .. F-12")
    print("=" * 96)
    f02_far_tail()
    f03_one_sample_equals_paired()
    f04_point_biserial_equals_two_group()
    f05_f06_balanced_grid()
    f06_published_example()
    f07_regression_equals_point_biserial()
    f08_sign()
    f09_allocation()
    f10_compromise()
    f11_pooling()
    f12_boundary_and_precision()
    print()
    print("=" * 96)
    print("interface, round trips, error handling")
    print("=" * 96)
    interface_surface()
    round_trips()
    monotonicity()
    error_handling()
    print()
    print("=" * 96)
    print("%d checks, %d failures, %.1f s" % (NCHECK, len(FAILURES),
                                             time.time() - t0))
    if FAILURES:
        for f in FAILURES:
            print("  FAILED: %s" % f)
    print("=" * 96)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
