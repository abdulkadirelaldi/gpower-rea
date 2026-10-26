"""Independent re-derivation of every bundled vector with SciPy.

This is the differential-testing half of the validation story: the engine's
hand-written noncentral-t quadrature and integer search are checked against a
reference built from nothing but the formulas in SPEC.md plus
``scipy.stats.nct`` / ``scipy.stats.t``.  The reference searches N by brute
force (linear scan), so it also cross-checks the bracketing search.

Skipped automatically when SciPy is not installed; docs/VALIDATION.md records
the result of the last full run.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

sp = pytest.importorskip("scipy.stats", reason="scipy not installed")

from gpower_rea import solve  # noqa: E402
from gpower_rea.cli import PUBLIC_VECTORS  # noqa: E402
from gpower_rea.engine import _round_half_up  # noqa: E402


# --------------------------------------------------------------------------
# The reference implementation: SPEC.md F-01..F-07, straight from the text
# --------------------------------------------------------------------------
def ref_power(df: float, ncp: float, alpha: float, tails: int) -> float:
    if tails == 1:
        tc = sp.t.ppf(1.0 - alpha, df)
        return float(1.0 - sp.nct.cdf(tc, df, ncp))
    tc = sp.t.ppf(1.0 - alpha / 2.0, df)
    return float(1.0 - sp.nct.cdf(tc, df, ncp) + sp.nct.cdf(-tc, df, ncp))


def ref_df_ncp(test: str, es: float, n1: int, n2: int, predictors: int | None):
    if test == "ttest-indep-means":
        return float(n1 + n2 - 2), es * math.sqrt(n1 * n2 / (n1 + n2))
    total = n1
    if test in ("ttest-one-sample", "ttest-paired-means"):
        return float(total - 1), es * math.sqrt(total)
    if test == "ttest-point-biserial":
        return float(total - 2), es * math.sqrt(total / (1.0 - es * es))
    if test == "ttest-regression-coef":
        return float(total - predictors - 1), math.sqrt(es * total)
    raise AssertionError(f"reference missing for {test}")


def ref_required_n(
    test: str,
    es: float,
    alpha: float,
    target: float,
    tails: int,
    ratio: float | None,
    predictors: int | None,
) -> int:
    """Brute-force linear scan for the smallest sufficient design."""
    if test == "ttest-indep-means":
        r = 1.0 if ratio is None else ratio
        n1 = 2
        while n1 <= 200_000:
            n2 = max(_round_half_up(r * n1), 2)
            df, ncp = ref_df_ncp(test, es, n1, n2, predictors)
            if df > 0 and ref_power(df, ncp, alpha, tails) >= target:
                return n1 + n2
            n1 += 1
        raise AssertionError("reference search exhausted")
    start = {
        "ttest-one-sample": 2,
        "ttest-paired-means": 2,
        "ttest-point-biserial": 3,
        "ttest-regression-coef": (predictors or 1) + 2,
    }[test]
    n = start
    while n <= 500_000:
        df, ncp = ref_df_ncp(test, es, n, 0, predictors)
        if df > 0 and ref_power(df, ncp, alpha, tails) >= target:
            return n
        n += 1
    raise AssertionError("reference search exhausted")


def _load_vectors():
    rows = []
    with Path(PUBLIC_VECTORS).open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


VECTORS = _load_vectors()


def test_vector_file_is_non_trivial():
    assert len(VECTORS) >= 300, "the bundled vector set shrank unexpectedly"
    tests = {r["test"] for r in VECTORS}
    assert tests >= {
        "ttest-indep-means",
        "ttest-one-sample",
        "ttest-paired-means",
        "ttest-point-biserial",
        "ttest-regression-coef",
    }


@pytest.mark.parametrize("row", VECTORS, ids=[r["id"] for r in VECTORS])
def test_vector_against_scipy_reference(row):
    test = row["test"]
    alpha = float(row["alpha"])
    target = float(row["power"])
    es = float(row["effect_size"])
    tails = int(row["tails"])
    ratio = float(row["ratio"]) if row["ratio"] else None
    predictors = int(row["predictors"]) if row["predictors"] else None

    expected = ref_required_n(test, es, alpha, target, tails, ratio, predictors)
    assert int(row["expected_N"]) == expected, "committed vector disagrees with SciPy"

    got = solve(
        test,
        "n",
        alpha=alpha,
        power_target=target,
        effect_size=es,
        tails=tails,
        allocation_ratio=ratio,
        extra={"predictors": predictors} if predictors is not None else None,
    )
    assert got.sample_size["total"] == expected, "engine disagrees with SciPy"
    assert got.power == pytest.approx(float(row["expected_power"]), abs=5e-7)


def test_post_hoc_power_matches_scipy_everywhere():
    worst = 0.0
    for test in (
        "ttest-indep-means",
        "ttest-one-sample",
        "ttest-paired-means",
        "ttest-point-biserial",
        "ttest-regression-coef",
    ):
        es = {"ttest-point-biserial": 0.3, "ttest-regression-coef": 0.15}.get(test, 0.5)
        predictors = 3 if test == "ttest-regression-coef" else None
        for n in (12, 23, 48, 97, 201):
            for alpha in (0.01, 0.05, 0.10):
                for tails in (1, 2):
                    if test == "ttest-indep-means":
                        n1 = n2 = n
                        kw = {"n1": n1, "n2": n2}
                    else:
                        n1, n2 = n, 0
                        kw = {"n": n}
                    df, ncp = ref_df_ncp(test, es, n1, n2, predictors)
                    if df <= 0:
                        continue
                    ref = ref_power(df, ncp, alpha, tails)
                    got = solve(
                        test,
                        "power",
                        alpha=alpha,
                        effect_size=es,
                        tails=tails,
                        extra={"predictors": predictors} if predictors else None,
                        **kw,
                    ).power
                    worst = max(worst, abs(ref - got))
    assert worst < 1e-10, f"worst post-hoc power deviation {worst:g}"
