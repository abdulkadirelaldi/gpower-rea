"""Effect-size calculators -- the equivalent of G*Power's "Determine =>" drawer.

Each function returns a small dict carrying the value, the formula actually
used, and the inputs, so that CLI / MCP / agent output is self-documenting and
auditable.

The non-obvious part is ``d_two_independent_means``: G*Power offers two
different pooled standard deviations, and the ``n1 = n2`` option is **not** the
textbook pooled SD -- it is the root-mean-square of the two SDs.  See SPEC
finding F-11 and docs/EVIDENCE/E-011-effect-size-pooling.md: on the worked
example there the two options differ by 49% in the number of participants
required.
"""

from __future__ import annotations

import math

from .procedures import ValidationError

__all__ = [
    "d_two_independent_means",
    "dz_matched_pairs",
    "dz_from_difference",
    "d_one_sample",
    "f2_from_r_squared",
    "f2_from_partial_r_squared",
    "r_from_d_balanced",
    "CALCULATORS",
]


def _pos(name: str, value: float) -> float:
    v = float(value)
    if v <= 0.0:
        raise ValidationError(f"{name} must be > 0, got {v}")
    return v


def d_two_independent_means(
    mean1: float,
    mean2: float,
    sd1: float,
    sd2: float,
    *,
    equal_n: bool = True,
    n1: int | None = None,
    n2: int | None = None,
) -> dict:
    """Cohen's d for two independent groups.

    equal_n=True  -> sigma = sqrt((sd1^2 + sd2^2) / 2)              [RMS]
    equal_n=False -> sigma = sqrt(((n1-1)sd1^2 + (n2-1)sd2^2) / (n1+n2-2))
    """
    sd1 = _pos("sd1", sd1)
    sd2 = _pos("sd2", sd2)
    if equal_n:
        sigma = math.sqrt(0.5 * (sd1 * sd1 + sd2 * sd2))
        formula = "sigma = sqrt((sd1^2 + sd2^2) / 2)   [G*Power 'n1 = n2' option]"
        inputs = {"mean1": mean1, "mean2": mean2, "sd1": sd1, "sd2": sd2}
    else:
        if n1 is None or n2 is None:
            raise ValidationError(
                "the unequal-n pooling option requires both n1 and n2"
            )
        n1i, n2i = int(n1), int(n2)
        if n1i < 2 or n2i < 2:
            raise ValidationError("n1 and n2 must both be >= 2")
        sigma = math.sqrt(
            ((n1i - 1) * sd1 * sd1 + (n2i - 1) * sd2 * sd2) / (n1i + n2i - 2)
        )
        formula = (
            "sigma = sqrt(((n1-1)sd1^2 + (n2-1)sd2^2) / (n1+n2-2))   "
            "[G*Power 'n1 != n2' option]"
        )
        inputs = {
            "mean1": mean1,
            "mean2": mean2,
            "sd1": sd1,
            "sd2": sd2,
            "n1": n1i,
            "n2": n2i,
        }
    d = (float(mean1) - float(mean2)) / sigma
    return {
        "effect_size": {"name": "d", "value": d},
        "pooled_sd": sigma,
        "formula": formula,
        "inputs": inputs,
        "for_test": "ttest-indep-means",
    }


def dz_matched_pairs(
    mean1: float,
    mean2: float,
    sd1: float,
    sd2: float,
    correlation: float,
) -> dict:
    """dz from the two marginal means/SDs and the pre-post correlation."""
    sd1 = _pos("sd1", sd1)
    sd2 = _pos("sd2", sd2)
    rho = float(correlation)
    if not (-1.0 < rho < 1.0):
        raise ValidationError("correlation must be in (-1, 1)")
    var_diff = sd1 * sd1 + sd2 * sd2 - 2.0 * rho * sd1 * sd2
    if var_diff <= 0.0:
        raise ValidationError(
            "implied variance of the difference is <= 0; check sd1, sd2, rho"
        )
    sd_diff = math.sqrt(var_diff)
    return {
        "effect_size": {"name": "dz", "value": (mean1 - mean2) / sd_diff},
        "sd_difference": sd_diff,
        "formula": "dz = (mu1 - mu2) / sqrt(sd1^2 + sd2^2 - 2*rho*sd1*sd2)",
        "inputs": {
            "mean1": mean1,
            "mean2": mean2,
            "sd1": sd1,
            "sd2": sd2,
            "correlation": rho,
        },
        "for_test": "ttest-paired-means",
    }


def dz_from_difference(mean_difference: float, sd_difference: float) -> dict:
    sd = _pos("sd_difference", sd_difference)
    return {
        "effect_size": {"name": "dz", "value": float(mean_difference) / sd},
        "formula": "dz = mu_diff / sigma_diff",
        "inputs": {
            "mean_difference": mean_difference,
            "sd_difference": sd,
        },
        "for_test": "ttest-paired-means",
    }


def d_one_sample(mean: float, reference: float, sd: float) -> dict:
    s = _pos("sd", sd)
    return {
        "effect_size": {"name": "d", "value": (float(mean) - float(reference)) / s},
        "formula": "d = (mu - mu0) / sigma",
        "inputs": {"mean": mean, "reference": reference, "sd": s},
        "for_test": "ttest-one-sample",
    }


def f2_from_r_squared(r_squared: float) -> dict:
    r2 = float(r_squared)
    if not (0.0 <= r2 < 1.0):
        raise ValidationError("r_squared must be in [0, 1)")
    return {
        "effect_size": {"name": "f2", "value": r2 / (1.0 - r2)},
        "formula": "f2 = R^2 / (1 - R^2)",
        "inputs": {"r_squared": r2},
        "for_test": "ttest-regression-coef",
    }


def f2_from_partial_r_squared(partial_r_squared: float) -> dict:
    pr2 = float(partial_r_squared)
    if not (0.0 <= pr2 < 1.0):
        raise ValidationError("partial_r_squared must be in [0, 1)")
    return {
        "effect_size": {"name": "f2", "value": pr2 / (1.0 - pr2)},
        "formula": "f2 = partial R^2 / (1 - partial R^2)",
        "inputs": {"partial_r_squared": pr2},
        "for_test": "ttest-regression-coef",
    }


def r_from_d_balanced(d: float) -> dict:
    """Point biserial r implied by a Cohen's d on a 50/50 dichotomy."""
    dd = float(d)
    r = dd / math.sqrt(dd * dd + 4.0)
    return {
        "effect_size": {"name": "r", "value": r},
        "formula": "r = d / sqrt(d^2 + 4)   (balanced dichotomy)",
        "inputs": {"d": dd},
        "for_test": "ttest-point-biserial",
    }


CALCULATORS = {
    "d-two-independent-means": d_two_independent_means,
    "dz-matched-pairs": dz_matched_pairs,
    "dz-from-difference": dz_from_difference,
    "d-one-sample": d_one_sample,
    "f2-from-r-squared": f2_from_r_squared,
    "f2-from-partial-r-squared": f2_from_partial_r_squared,
    "r-from-d-balanced": r_from_d_balanced,
}
