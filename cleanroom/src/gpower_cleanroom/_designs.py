"""Test definitions: the ``(nu, delta)`` map of every menu entry, the
a-priori search grids, and the admissible effect-size domains.

SPEC.md references
------------------
F-03  one sample / matched pairs : nu = N-1,      delta = ES*sqrt(N),  N >= 2
F-04  point biserial             : nu = N-2,      delta = r*sqrt(N/(1-r^2)), N >= 3
F-05  two independent means      : nu = n1+n2-2,  delta = ES*sqrt(n1*n2/(n1+n2))
                                   a-priori search enumerates n1 (NOT total N)
F-07  regression coefficient     : nu = N-p-1,    delta = sqrt(f2*N),  N >= p+2
F-09  allocation-ratio rounding  : n1-grid (default) vs total-grid, half-up
"""

from __future__ import annotations

import math
from typing import Callable, NamedTuple, Optional

__all__ = [
    "TESTS",
    "ALLOCATION_RULES",
    "Design",
    "round_half_up",
    "make_design",
    "apriori_grid",
    "effect_size_domain",
    "effect_size_name",
    "validate_effect_size",
    "is_single_group",
]

TESTS: tuple[str, ...] = (
    "ttest-indep-means",
    "ttest-paired-means",
    "ttest-one-sample",
    "ttest-point-biserial",
    "ttest-regression-coef",
    "ttest-generic",
)

ALLOCATION_RULES: tuple[str, ...] = ("n1-grid", "total-grid")

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

# SPEC.md section 3: admissible effect-size domains for the sensitivity bisection.
_EFFECT_DOMAIN = {
    "ttest-indep-means": (0.0, 100.0),
    "ttest-paired-means": (0.0, 100.0),
    "ttest-one-sample": (0.0, 100.0),
    "ttest-point-biserial": (0.0, 1.0),
    "ttest-regression-coef": (0.0, 1.0e6),
    "ttest-generic": (0.0, 1.0e6),
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


def effect_size_domain(test: str) -> tuple[float, float]:
    check_test(test)
    return _EFFECT_DOMAIN[test]


def round_half_up(v: float) -> int:
    """Half-away-from-zero rounding (SPEC.md F-09): ``round_half_up(2.5) == 3``.

    Python's / IEEE's ``round`` is half-to-even and would give 2.
    """
    if v >= 0.0:
        return int(math.floor(v + 0.5))
    return -int(math.floor(-v + 0.5))


def validate_effect_size(test: str, effect_size: float) -> None:
    check_test(test)
    if not math.isfinite(effect_size):
        raise ValueError("effect_size must be finite")
    if test == "ttest-point-biserial" and abs(effect_size) >= 1.0:
        raise ValueError("point biserial requires |r| < 1")
    if test == "ttest-regression-coef" and effect_size < 0.0:
        raise ValueError("f2 is a squared effect size and must be >= 0")


def _check_predictors(predictors: Optional[int]) -> int:
    if predictors is None:
        raise ValueError("ttest-regression-coef requires predictors=<total predictors>")
    if int(predictors) != predictors or predictors < 1:
        raise ValueError("predictors must be an integer >= 1")
    return int(predictors)


def make_design(test: str, effect_size: float, *, n: Optional[int] = None,
                n1: Optional[int] = None, n2: Optional[int] = None,
                predictors: Optional[int] = None,
                df: Optional[float] = None) -> Design:
    """Build the ``(nu, delta)`` pair of a fully specified design."""
    check_test(test)
    validate_effect_size(test, effect_size)

    if test == "ttest-generic":
        if df is None:
            raise ValueError("ttest-generic requires df")
        nu = float(df)
        if not (nu > 0.0):
            raise ValueError("df must be > 0")
        return Design(0, 0, 0, nu, float(effect_size))

    if test == "ttest-indep-means":
        a, b = _two_group_sizes(n1, n2)
        if a < 2 or b < 2:
            raise ValueError("two-group t test requires n1 >= 2 and n2 >= 2")
        nu = float(a + b - 2)
        delta = effect_size * math.sqrt(a * b / float(a + b))
        return Design(a, b, a + b, nu, delta)

    # single-group designs
    size = n if n is not None else n1
    if size is None:
        raise ValueError("this test requires the sample size n")
    if int(size) != size:
        raise ValueError("sample size must be an integer")
    size = int(size)

    if test in ("ttest-one-sample", "ttest-paired-means"):
        # F-03.  N is the number of pairs for matched pairs, not observations.
        if size < 2:
            raise ValueError("N >= 2 is required")
        nu = float(size - 1)
        delta = effect_size * math.sqrt(size)
        return Design(size, 0, size, nu, delta)

    if test == "ttest-point-biserial":
        # F-04.  The radicand is N, not N-2.
        if size < 3:
            raise ValueError("N >= 3 is required")
        nu = float(size - 2)
        r = effect_size
        delta = r * math.sqrt(size / (1.0 - r * r))
        return Design(size, 0, size, nu, delta)

    # ttest-regression-coef, F-07
    p = _check_predictors(predictors)
    if size < p + 2:
        raise ValueError("N >= predictors + 2 is required")
    nu = float(size - p - 1)
    delta = math.sqrt(effect_size * size)
    return Design(size, 0, size, nu, delta)


def _two_group_sizes(n1: Optional[int], n2: Optional[int]) -> tuple[int, int]:
    if n1 is None or n2 is None:
        raise ValueError("the two-group t test requires both n1 and n2")
    if int(n1) != n1 or int(n2) != n2:
        raise ValueError("group sizes must be integers")
    return int(n1), int(n2)


# ---------------------------------------------------------------------------
# a-priori search grids  (F-05, F-09)
# ---------------------------------------------------------------------------


def apriori_grid(test: str, effect_size: float, *,
                 allocation_ratio: float = 1.0,
                 predictors: Optional[int] = None,
                 allocation_rule: str = "n1-grid"
                 ) -> tuple[int, Callable[[int], Optional[Design]]]:
    """Return ``(first_index, builder)`` describing the a-priori search space.

    The grid *index* is the quantity actually enumerated:

    * ``ttest-indep-means`` with ``n1-grid``  -> ``n1`` (F-05: NOT the total N)
    * ``ttest-indep-means`` with ``total-grid`` -> the total ``N``
    * every single-group test              -> ``N``

    ``builder(i)`` returns ``None`` when the grid point is not an admissible
    design (and admissibility is an up-set in ``i``, so a monotone search is
    still exact).
    """
    check_test(test)
    validate_effect_size(test, effect_size)
    if test == "ttest-generic":
        raise ValueError(
            "a-priori analysis is not available for ttest-generic: "
            "the generic t test supplies nu and delta directly, so N has no meaning"
        )

    if test == "ttest-indep-means":
        if allocation_rule not in ALLOCATION_RULES:
            raise ValueError(
                "allocation_rule must be one of %s" % (", ".join(ALLOCATION_RULES),)
            )
        if not (allocation_ratio > 0.0) or not math.isfinite(allocation_ratio):
            raise ValueError("allocation_ratio must be a finite positive number")
        R = float(allocation_ratio)

        if allocation_rule == "n1-grid":
            def build_n1(i: int) -> Optional[Design]:
                a = i
                b = round_half_up(R * i)
                if a < 2 or b < 2:
                    return None
                return make_design(test, effect_size, n1=a, n2=b)
            return 2, build_n1

        def build_total(i: int) -> Optional[Design]:
            a = round_half_up(i / (1.0 + R))
            b = i - a
            if a < 2 or b < 2:
                return None
            return make_design(test, effect_size, n1=a, n2=b)
        return 4, build_total

    if test in ("ttest-one-sample", "ttest-paired-means"):
        start = 2
    elif test == "ttest-point-biserial":
        start = 3
    else:
        start = _check_predictors(predictors) + 2

    def build_single(i: int) -> Optional[Design]:
        try:
            return make_design(test, effect_size, n=i, predictors=predictors)
        except ValueError:
            return None

    return start, build_single
