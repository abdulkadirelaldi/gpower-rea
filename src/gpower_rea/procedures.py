"""The t-test family: one procedure object per G*Power "Statistical test".

A procedure is nothing but a pair of maps

    (sample size, effect size, extra params)  ->  (df, noncentrality)

plus the metadata needed to validate input and label output.  Every power
value in this project is then computed by the *single* shared routine in
``power.py``.  Adding a new member of the family means adding one object here
and nothing else.

Mapping to the G*Power 3.1 UI (Test family = "t tests"):

    key                         Statistical test
    --------------------------  ---------------------------------------------
    ttest-indep-means           Means: Difference between two independent
                                means (two groups)
    ttest-paired-means          Means: Difference between two dependent means
                                (matched pairs)
    ttest-one-sample            Means: Difference from constant (one sample
                                case)
    ttest-point-biserial        Correlation: Point biserial model
    ttest-regression-coef       Linear multiple regression: Fixed model,
                                single regression coefficient
    ttest-generic               Generic t test

Every (df, ncp) formula is traceable to a numbered finding in SPEC.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

__all__ = [
    "Sample",
    "Procedure",
    "PROCEDURES",
    "resolve",
    "list_keys",
    "ValidationError",
]


class ValidationError(ValueError):
    """Raised when the caller supplies parameters outside a test's domain."""


@dataclass(frozen=True)
class Sample:
    """A concrete sample-size allocation.

    ``n2 == 0`` means a single-group design (``total == n1``).
    """

    n1: int
    n2: int = 0

    @property
    def total(self) -> int:
        return self.n1 + self.n2

    def as_dict(self) -> dict:
        if self.n2:
            return {
                "n1": self.n1,
                "n2": self.n2,
                "total": self.total,
            }
        return {"n": self.n1, "total": self.total}


@dataclass(frozen=True)
class ExtraParam:
    name: str
    label: str
    kind: str  # "int" | "float"
    default: float | int | None = None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class Procedure:
    key: str
    title: str
    effect_size_name: str
    effect_size_label: str
    df_fn: Callable[[Sample, Mapping], float]
    ncp_fn: Callable[[Sample, float, Mapping], float]
    min_sample_fn: Callable[[Mapping], Sample]
    two_group: bool = False
    aliases: tuple[str, ...] = ()
    extra: tuple[ExtraParam, ...] = ()
    es_bounds: tuple[float, float] = (1e-9, 100.0)
    es_check: Callable[[float], bool] | None = None
    supports_solve: tuple[str, ...] = (
        "n",
        "power",
        "alpha",
        "effect-size",
        "compromise",
    )
    spec_refs: tuple[str, ...] = ()
    notes: str = ""

    # -- derived quantities -------------------------------------------------
    def df(self, sample: Sample, extra: Mapping) -> float:
        return self.df_fn(sample, extra)

    def ncp(self, sample: Sample, es: float, extra: Mapping) -> float:
        return self.ncp_fn(sample, es, extra)

    def min_sample(self, extra: Mapping) -> Sample:
        return self.min_sample_fn(extra)

    # -- validation ---------------------------------------------------------
    def normalise_extra(self, given: Mapping | None) -> dict:
        given = dict(given or {})
        out: dict = {}
        known = {p.name for p in self.extra}
        unknown = set(given) - known
        if unknown:
            raise ValidationError(
                f"{self.key}: unknown parameter(s) {sorted(unknown)}; "
                f"expected {sorted(known) or 'none'}"
            )
        for p in self.extra:
            if p.name in given and given[p.name] is not None:
                raw = given[p.name]
                try:
                    val = int(raw) if p.kind == "int" else float(raw)
                except (TypeError, ValueError):
                    raise ValidationError(
                        f"{self.key}: parameter '{p.name}' must be {p.kind}"
                    ) from None
            elif p.required:
                raise ValidationError(
                    f"{self.key}: parameter '{p.name}' ({p.label}) is required"
                )
            else:
                val = p.default
            if val is not None:
                if p.minimum is not None and val < p.minimum:
                    raise ValidationError(
                        f"{self.key}: '{p.name}' must be >= {p.minimum}"
                    )
                if p.maximum is not None and val > p.maximum:
                    raise ValidationError(
                        f"{self.key}: '{p.name}' must be <= {p.maximum}"
                    )
            out[p.name] = val
        return out

    def check_effect_size(self, es: float) -> None:
        if self.es_check is not None and not self.es_check(es):
            raise ValidationError(
                f"{self.key}: effect size {self.effect_size_name}={es} is "
                f"outside the admissible domain"
            )

    def describe(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "family": "t tests",
            "aliases": list(self.aliases),
            "design": "two-group" if self.two_group else "single-group",
            "effect_size": {
                "name": self.effect_size_name,
                "label": self.effect_size_label,
            },
            "extra_parameters": [
                {
                    "name": p.name,
                    "label": p.label,
                    "type": p.kind,
                    "default": p.default,
                    "required": p.required,
                }
                for p in self.extra
            ],
            "supports_solve": list(self.supports_solve),
            "spec_refs": list(self.spec_refs),
            "notes": self.notes,
        }


# --------------------------------------------------------------------------
# 1) Means: Difference between two independent means (two groups)
# --------------------------------------------------------------------------
_INDEP = Procedure(
    key="ttest-indep-means",
    title="Means: Difference between two independent means (two groups)",
    aliases=("indep", "two-sample", "independent-means", "ttest2"),
    effect_size_name="d",
    effect_size_label="Effect size d = (mu1 - mu2) / sigma",
    two_group=True,
    df_fn=lambda s, e: float(s.n1 + s.n2 - 2),
    ncp_fn=lambda s, d, e: d * math.sqrt(s.n1 * s.n2 / float(s.n1 + s.n2)),
    min_sample_fn=lambda e: Sample(2, 2),
    es_bounds=(1e-9, 100.0),
    spec_refs=("F-01", "F-02", "F-05", "F-06"),
    notes=(
        "Noncentrality uses the harmonic-style term sqrt(n1*n2/(n1+n2)); "
        "with n1 = n2 = n this reduces to d*sqrt(n/2)."
    ),
)

# --------------------------------------------------------------------------
# 2) Means: Difference between two dependent means (matched pairs)
# --------------------------------------------------------------------------
_PAIRED = Procedure(
    key="ttest-paired-means",
    title="Means: Difference between two dependent means (matched pairs)",
    aliases=("paired", "matched-pairs", "dependent-means"),
    effect_size_name="dz",
    effect_size_label="Effect size dz = mu_diff / sigma_diff",
    df_fn=lambda s, e: float(s.total - 1),
    ncp_fn=lambda s, dz, e: dz * math.sqrt(s.total),
    min_sample_fn=lambda e: Sample(2),
    es_bounds=(1e-9, 100.0),
    spec_refs=("F-01", "F-02", "F-03"),
    notes="N is the number of pairs, not the number of observations.",
)

# --------------------------------------------------------------------------
# 3) Means: Difference from constant (one sample case)
# --------------------------------------------------------------------------
_ONE_SAMPLE = Procedure(
    key="ttest-one-sample",
    title="Means: Difference from constant (one sample case)",
    aliases=("one-sample", "onesample", "ttest1"),
    effect_size_name="d",
    effect_size_label="Effect size d = (mu - mu0) / sigma",
    df_fn=lambda s, e: float(s.total - 1),
    ncp_fn=lambda s, d, e: d * math.sqrt(s.total),
    min_sample_fn=lambda e: Sample(2),
    es_bounds=(1e-9, 100.0),
    spec_refs=("F-01", "F-02", "F-03"),
    notes=(
        "Algebraically identical to the matched-pairs case; G*Power keeps "
        "them as separate menu entries because the effect-size drawers differ."
    ),
)

# --------------------------------------------------------------------------
# 4) Correlation: Point biserial model
# --------------------------------------------------------------------------
_POINT_BISERIAL = Procedure(
    key="ttest-point-biserial",
    title="Correlation: Point biserial model",
    aliases=("point-biserial", "pointbiserial", "rpb"),
    effect_size_name="r",
    effect_size_label="Point biserial correlation |r|",
    df_fn=lambda s, e: float(s.total - 2),
    ncp_fn=lambda s, r, e: r * math.sqrt(s.total / (1.0 - r * r)),
    min_sample_fn=lambda e: Sample(3),
    es_bounds=(1e-9, 1.0 - 1e-9),
    es_check=lambda r: 0.0 < abs(r) < 1.0,
    spec_refs=("F-01", "F-02", "F-04"),
    notes=(
        "Consistency check: with a balanced dichotomy the two-group d maps to "
        "d = 2r/sqrt(1-r^2), and d*sqrt(N/4) reproduces r*sqrt(N/(1-r^2))."
    ),
)

# --------------------------------------------------------------------------
# 5) Linear multiple regression: single regression coefficient
# --------------------------------------------------------------------------
_REGRESSION = Procedure(
    key="ttest-regression-coef",
    title="Linear multiple regression: Fixed model, single regression coefficient",
    aliases=("regression-coef", "mrc-single", "lmr-coef"),
    effect_size_name="f2",
    effect_size_label="Effect size f² (partial, for the tested predictor)",
    df_fn=lambda s, e: float(s.total - int(e["predictors"]) - 1),
    ncp_fn=lambda s, f2, e: math.sqrt(f2 * s.total),
    min_sample_fn=lambda e: Sample(int(e["predictors"]) + 2),
    extra=(
        ExtraParam(
            name="predictors",
            label="Number of predictors in the model",
            kind="int",
            default=1,
            minimum=1,
        ),
    ),
    es_bounds=(1e-12, 1e6),
    spec_refs=("F-01", "F-02", "F-07"),
    notes=(
        "Reduction check: with predictors=1 and f2 = r^2/(1-r^2) this collapses "
        "exactly onto the point-biserial / simple-correlation t test."
    ),
)

# --------------------------------------------------------------------------
# 6) Generic t test
# --------------------------------------------------------------------------
def _generic_df(sample: Sample, extra: Mapping) -> float:
    return float(extra["df"])


def _generic_ncp(sample: Sample, es: float, extra: Mapping) -> float:
    return float(es)


_GENERIC = Procedure(
    key="ttest-generic",
    title="Generic t test",
    aliases=("generic", "generic-t"),
    effect_size_name="ncp",
    effect_size_label="Noncentrality parameter delta",
    df_fn=_generic_df,
    ncp_fn=_generic_ncp,
    min_sample_fn=lambda e: Sample(0),
    extra=(
        ExtraParam(
            name="df",
            label="Degrees of freedom",
            kind="float",
            required=True,
            minimum=1e-6,
        ),
    ),
    es_bounds=(1e-9, 1e6),
    supports_solve=("power", "alpha", "effect-size", "compromise"),
    spec_refs=("F-01", "F-02"),
    notes=(
        "df and delta are supplied directly, so N has no meaning here; a "
        "priori (solve for N) is therefore not offered, exactly as in the GUI."
    ),
)


PROCEDURES: dict[str, Procedure] = {
    p.key: p
    for p in (
        _INDEP,
        _PAIRED,
        _ONE_SAMPLE,
        _POINT_BISERIAL,
        _REGRESSION,
        _GENERIC,
    )
}

_ALIAS_INDEX: dict[str, str] = {}
for _p in PROCEDURES.values():
    _ALIAS_INDEX[_p.key.lower()] = _p.key
    for _a in _p.aliases:
        _ALIAS_INDEX[_a.lower()] = _p.key


def _norm_token(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


_NORM_INDEX = {_norm_token(k): v for k, v in _ALIAS_INDEX.items()}


def resolve(name: str) -> Procedure:
    """Resolve a test key, alias, or loose spelling to a Procedure."""
    if not name:
        raise ValidationError("no test specified (use --test; see `gpower list`)")
    key = _ALIAS_INDEX.get(str(name).strip().lower())
    if key is None:
        key = _NORM_INDEX.get(_norm_token(str(name)))
    if key is None:
        raise ValidationError(
            f"unknown test {name!r}; known tests: "
            + ", ".join(sorted(PROCEDURES))
        )
    return PROCEDURES[key]


def list_keys() -> Sequence[str]:
    return tuple(PROCEDURES)
