"""Test definitions: the ``(nu, delta)`` map of every menu entry, the
a-priori search grids, and the admissible input domains.

SPEC.md v1.3 references
-----------------------
F-03  one sample / matched pairs : nu = N-1,      delta = ES*sqrt(N)
F-04  point biserial             : nu = N-2,      delta = r*sqrt(N/(1-r^2))
F-05  two independent means      : nu = n1+n2-2,  delta = ES*sqrt(n1*n2/(n1+n2))
F-07  regression coefficient     : nu = N-p-1,    delta = sqrt(f2*N)
F-08  the sign of ES is a direction; probabilities use |delta|
F-09  a-priori allocation rule   : "even-total" (default), and the refuted
                                   v1.1 rules "n1-grid" / "total-grid"
F-13  item 7: grid points below F-05's minimum group sizes are skipped --
      for the v1.1 rules only; even-total skips nothing (F-16, G2-04)
F-15  the input domain G*Power accepts (explicit designs: each group >= 1,
      total N >= 3, regression N >= p+2, p >= 1; a-priori results as small
      as nu = 1; allocation ratio in [0.01, 100])
F-16  closure of the v1.2 gaps G2-01 ... G2-19
"""

from __future__ import annotations

import math
from typing import Callable, NamedTuple, Optional

__all__ = [
    "TESTS",
    "ALLOCATION_RULES",
    "DEFAULT_ALLOCATION_RULE",
    "APRIORI_N_CAP",
    "APRIORI_MIN_ES",
    "APRIORI_MIN_ES_TESTS",
    "R_ALLOC_MIN",
    "R_ALLOC_MAX",
    "R_MAX",
    "F2_MAX",
    "Design",
    "Grid",
    "round_half_up",
    "make_design",
    "apriori_grid",
    "effect_size_bracket",
    "effect_size_name",
    "validate_effect_size",
    "is_single_group",
    "check_test",
]

TESTS: tuple[str, ...] = (
    "ttest-indep-means",
    "ttest-paired-means",
    "ttest-one-sample",
    "ttest-point-biserial",
    "ttest-regression-coef",
    "ttest-generic",
)

#: F-09: "even-total" is the observed rule and the default; the other two are
#: the refuted v1.1 candidates, kept selectable for reproducing v1.1 output.
ALLOCATION_RULES: tuple[str, ...] = ("even-total", "n1-grid", "total-grid")
DEFAULT_ALLOCATION_RULE = "even-total"

#: SPEC section 3 / F-15: the a-priori N is searched up to 2**63 - 2.
APRIORI_N_CAP = 2 ** 63 - 2

#: F-15 (v1.3): a-priori effect size must satisfy |ES| >= 0.00001 for d, dz
#: and f2 -- NOT for r (X-G2-08a,b).
APRIORI_MIN_ES = 1e-5
APRIORI_MIN_ES_TESTS = frozenset({
    "ttest-indep-means", "ttest-paired-means", "ttest-one-sample",
    "ttest-regression-coef",
})

#: F-15 (v1.3): admissible allocation ratio N2/N1 (X-G2-11).
R_ALLOC_MIN, R_ALLOC_MAX = 0.01, 100.0

#: F-15 (v1.3): point biserial 0 <= r <= 0.999999 (r = 0 accepted, X-G2-06).
R_MAX = 0.999999

#: F-15: f2 range check (-20, 20); negatives then fail -> 0 <= f2 < 20.
F2_MAX = 20.0

_SINGLE_GROUP = frozenset({
    "ttest-paired-means",
    "ttest-one-sample",
    "ttest-point-biserial",
    "ttest-regression-coef",
})

_EFFECT_NAME = {
    "ttest-indep-means": "d",
    "ttest-paired-means": "dz",
    "ttest-one-sample": "d",
    "ttest-point-biserial": "r",
    "ttest-regression-coef": "f2",
    "ttest-generic": "ncp",
}

# SPEC section 3 / F-13 item 4 (v1.2): closed sensitivity brackets.
_EFFECT_BRACKET = {
    "ttest-indep-means": (1e-12, 100.0),
    "ttest-paired-means": (1e-12, 100.0),
    "ttest-one-sample": (1e-12, 100.0),
    "ttest-point-biserial": (1e-12, R_MAX),
    "ttest-regression-coef": (1e-12, 1.0e6),
    "ttest-generic": (1e-12, 1.0e6),
}


class Design(NamedTuple):
    n1: int
    n2: int
    total: int
    nu: float
    delta: float


def check_test(test: str) -> None:
    if test not in TESTS:
        raise ValueError(
            "unknown test key %r; expected one of %s" % (test, ", ".join(TESTS))
        )


def is_single_group(test: str) -> bool:
    return test in _SINGLE_GROUP


def effect_size_name(test: str) -> str:
    check_test(test)
    return _EFFECT_NAME[test]


def effect_size_bracket(test: str) -> tuple[float, float]:
    check_test(test)
    return _EFFECT_BRACKET[test]


def round_half_up(v: float) -> int:
    """Half-away-from-zero rounding (SPEC.md F-09): ``round_half_up(42.5) == 43``.

    Python's / IEEE's ``round`` is half-to-even and would give 42.
    """
    if v >= 0.0:
        return int(math.floor(v + 0.5))
    return -int(math.floor(-v + 0.5))


def validate_effect_size(test: str, effect_size: float) -> float:
    """Domain checks that hold in every analysis (F-08, F-13 item 2, F-15)."""
    check_test(test)
    if effect_size is None or isinstance(effect_size, bool):
        raise ValueError("effect_size must be a finite number")
    try:
        es = float(effect_size)
    except (TypeError, ValueError):
        raise ValueError("effect_size must be a finite number") from None
    if not math.isfinite(es):
        raise ValueError("effect_size must be finite")
    if test == "ttest-point-biserial" and not (0.0 <= es <= R_MAX):
        # F-08 / F-15 (N-07, D-01, D-02, X-G2-06): the field is |rho|; a
        # negative r is refused, and so is anything above 0.999999; r = 0 is
        # accepted.
        raise ValueError(
            "Effect size r is outside the admissible range [0, 0.999999] "
            "(SPEC.md F-15: point biserial requires 0 <= r <= 0.999999; "
            "a negative r is refused, F-08), got %r" % (effect_size,))
    if test == "ttest-regression-coef":
        if es < 0.0:
            raise ValueError(
                "f2 is a squared effect size and must be >= 0 "
                "(SPEC.md F-13 item 2, F-15), got %r" % (effect_size,))
        if es >= F2_MAX:
            raise ValueError(
                "f2 must be < 20 (SPEC.md F-15: admissible 0 <= f2 < 20), got %r"
                % (effect_size,))
    return es


def _check_predictors(predictors: Optional[int]) -> int:
    if predictors is None:
        raise ValueError("ttest-regression-coef requires predictors=<total predictors>")
    if isinstance(predictors, bool) or int(predictors) != predictors or predictors < 1:
        raise ValueError("predictors must be an integer >= 1")
    return int(predictors)


def _as_int(name: str, v) -> int:
    if isinstance(v, bool):
        raise ValueError("%s must be an integer" % name)
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s must be an integer" % name) from None
    if not math.isfinite(f) or int(v) != v:
        raise ValueError("%s must be an integer" % name)
    return int(v)


def _absent(v) -> bool:
    """An unused size parameter: ``None``, or ``0`` (the value the result
    dict itself carries for an absent group / for the generic test)."""
    return v is None or (not isinstance(v, bool) and v == 0)


def make_design(test: str, effect_size: float, *, n: Optional[int] = None,
                n1: Optional[int] = None, n2: Optional[int] = None,
                predictors: Optional[int] = None,
                df: Optional[float] = None) -> Design:
    """``(nu, delta)`` of an **explicit** design (post hoc, criterion,
    sensitivity, compromise).  ``effect_size`` is used as given (callers pass
    ``|ES|``, F-08).  Minimum sizes are those of F-15."""
    check_test(test)
    es = float(effect_size)

    # F-13 item 11: an inapplicable design parameter is rejected.
    if test != "ttest-regression-coef" and predictors is not None:
        raise ValueError("predictors is only applicable to ttest-regression-coef "
                         "(SPEC.md F-13 item 11)")
    if test != "ttest-generic" and df is not None:
        raise ValueError("df is only applicable to ttest-generic "
                         "(SPEC.md F-13 item 11)")

    if test == "ttest-generic":
        if not (_absent(n) and _absent(n1) and _absent(n2)):
            raise ValueError("ttest-generic takes df, not a sample size "
                             "(SPEC.md F-13 item 11)")
        if df is None or isinstance(df, bool):
            raise ValueError("ttest-generic requires df")
        nu = float(df)
        if not math.isfinite(nu) or not (nu > 0.0):
            raise ValueError("df must be finite and > 0 (SPEC.md F-15)")
        return Design(0, 0, 0, nu, es)

    if test == "ttest-indep-means":
        if n is not None:
            raise ValueError("the two-group t test takes n1 and n2, not n "
                             "(SPEC.md F-13 item 11)")
        if n1 is None or n2 is None:
            raise ValueError("the two-group t test requires both n1 and n2")
        a = _as_int("n1", n1)
        b = _as_int("n2", n2)
        if a < 1 or b < 1:
            raise ValueError("each group needs at least one observation")
        if a + b < 3:
            raise ValueError("an explicit design needs total N >= 3 "
                             "(SPEC.md F-15)")
        return _two_group(a, b, es)

    # single-group designs: n (n1 accepted as an alias, n2 must be absent)
    if not _absent(n2):
        raise ValueError("n2 is only applicable to ttest-indep-means "
                         "(SPEC.md F-13 item 11)")
    if n is not None and n1 is not None and n != n1:
        raise ValueError("conflicting sample sizes n=%r and n1=%r" % (n, n1))
    size = n if n is not None else n1
    if size is None:
        raise ValueError("this test requires the sample size n")
    size = _as_int("n", size)

    if test == "ttest-regression-coef":
        p = _check_predictors(predictors)
        if size < p + 2:
            raise ValueError("N >= predictors + 2 is required (SPEC.md F-07, F-15)")
    elif size < 3:
        # F-15 (D-08, D-41): N = 2 is refused as an explicit design even for
        # one sample / matched pairs, although nu = 1 there.
        raise ValueError("an explicit design needs total N >= 3 (SPEC.md F-15)")
    return _single(test, size, es, predictors)


def _two_group(a: int, b: int, es: float) -> Design:
    nu = float(a + b - 2)
    delta = es * math.sqrt(a * b / float(a + b))
    return Design(a, b, a + b, nu, delta)


def _single(test: str, size: int, es: float,
            predictors: Optional[int]) -> Design:
    if test in ("ttest-one-sample", "ttest-paired-means"):
        # F-03.  N is the number of pairs for matched pairs, not observations.
        return Design(size, 0, size, float(size - 1), es * math.sqrt(size))
    if test == "ttest-point-biserial":
        # F-04.  The radicand is N, not N-2.
        return Design(size, 0, size, float(size - 2),
                      es * math.sqrt(size / (1.0 - es * es)))
    p = int(predictors)
    # F-07: p enters nu only.
    return Design(size, 0, size, float(size - p - 1), math.sqrt(es * size))


# ---------------------------------------------------------------------------
# a-priori search grids  (F-05, F-09, F-13 item 7, F-15, SPEC section 3)
# ---------------------------------------------------------------------------


class Grid(NamedTuple):
    """The a-priori search space.

    ``stop(i)``   -> ``(nu, delta)`` on which the stopping test is made, or
                     ``None`` if index ``i`` is skipped (F-13 item 7);
    ``report(i)`` -> the integer :class:`Design` reported for index ``i``;
    ``start``/``last`` bound the index range (the latter from the
    SPEC section 3 cap ``N <= 2**63 - 2``).
    """
    start: int
    last: int
    stop: Callable[[int], Optional[tuple[float, float]]]
    report: Callable[[int], Design]


def apriori_grid(test: str, effect_size: float, *,
                 allocation_ratio: float = 1.0,
                 predictors: Optional[int] = None,
                 allocation_rule: str = DEFAULT_ALLOCATION_RULE) -> Grid:
    """Return the :class:`Grid` of the a-priori search for ``|ES|``."""
    check_test(test)
    es = float(effect_size)
    if test == "ttest-generic":
        raise ValueError(
            "a-priori analysis is not available for ttest-generic: "
            "the generic t test supplies nu and delta directly, so N has no meaning"
        )
    cap = APRIORI_N_CAP

    if test == "ttest-indep-means":
        R = float(allocation_ratio)

        if allocation_rule == "even-total":
            # F-09: N = 2i, stopping test on the unrounded split.  No grid
            # point is skipped (F-16, G2-04: R = 3, d = 8 reports 1 / 3), so
            # the reported split can contain a group of 1 -- or, at the
            # extreme ratios of F-15, of 0 (SPEC-GAPS-v1.3.md G3-01).
            def _split(i: int) -> tuple[int, int]:
                N = 2 * i
                a = round_half_up(N / (1.0 + R))
                return a, N - a

            def stop_even(i: int) -> Optional[tuple[float, float]]:
                N = float(2 * i)
                m1 = N / (1.0 + R)
                m2 = N * R / (1.0 + R)
                return N - 2.0, es * math.sqrt(m1 * m2 / N)

            def report_even(i: int) -> Design:
                a, b = _split(i)
                return _two_group(a, b, es)

            return Grid(2, cap // 2, stop_even, report_even)

        if allocation_rule == "n1-grid":
            def _pair(i: int) -> tuple[int, int]:
                return i, round_half_up(R * i)

            def stop_n1(i: int) -> Optional[tuple[float, float]]:
                a, b = _pair(i)
                if a < 2 or b < 2:
                    return None
                d = _two_group(a, b, es)
                return d.nu, d.delta

            last = int(cap / (1.0 + R))
            while last > 2 and sum(_pair(last)) > cap:
                last -= max(1, last // 10 ** 12)
            return Grid(2, max(last, 2), stop_n1,
                        lambda i: _two_group(*_pair(i), es))

        # total-grid
        def _tsplit(i: int) -> tuple[int, int]:
            a = round_half_up(i / (1.0 + R))
            return a, i - a

        def stop_total(i: int) -> Optional[tuple[float, float]]:
            a, b = _tsplit(i)
            if a < 2 or b < 2:
                return None
            d = _two_group(a, b, es)
            return d.nu, d.delta

        return Grid(4, cap, stop_total, lambda i: _two_group(*_tsplit(i), es))

    # single-group tests: smallest a-priori result has nu = 1 (F-15, D-23)
    if test in ("ttest-one-sample", "ttest-paired-means"):
        start = 2
    elif test == "ttest-point-biserial":
        start = 3
    else:
        start = _check_predictors(predictors) + 2

    def stop_single(i: int) -> Optional[tuple[float, float]]:
        d = _single(test, i, es, predictors)
        return d.nu, d.delta

    return Grid(start, cap, stop_single,
                lambda i: _single(test, i, es, predictors))
