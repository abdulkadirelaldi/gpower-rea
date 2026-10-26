# INTERFACE.md — the public surface your implementation must expose

This file carries **naming only**. All behaviour is specified in `SPEC.md`,
which is in this same directory and is the only other file you may read.

Write a package at `src/gpower_cleanroom/` (this directory, `src/` already
exists). Python 3.10+, **no third-party imports at all** — standard library
only (`math` has `erfc`, `lgamma`, `log1p`, `erf`).

---

## Test keys

Five solvable tests plus one that cannot solve for `N`. Use exactly these
strings; map each to the G\*Power menu title named in `SPEC.md`:

| key | SPEC.md menu title |
|---|---|
| `ttest-indep-means` | Means: Difference between two independent means (two groups) |
| `ttest-paired-means` | Means: Difference between two dependent means (matched pairs) |
| `ttest-one-sample` | Means: Difference from constant (one sample case) |
| `ttest-point-biserial` | Correlation: Point biserial model |
| `ttest-regression-coef` | Linear multiple regression: Fixed model, single regression coefficient |
| `ttest-generic` | Generic t test |

```python
TESTS: tuple[str, ...]   # the six keys above, in that order
```

---

## Functions

All five are module-level in `gpower_cleanroom` (i.e. importable as
`from gpower_cleanroom import required_sample_size`). All take the test key as
their first positional argument and everything else keyword-only.

Each returns a plain `dict` with **at least** these keys:

```python
{
    "n1": int,        # group 1 size; for a single-group test, the total
    "n2": int,        # group 2 size; 0 for a single-group test
    "total": int,     # total sample size; 0 for ttest-generic
    "power": float,   # achieved power at the returned design
    "alpha": float,   # the alpha in force
    "effect_size": float,
    "df": float,
    "ncp": float,     # noncentrality parameter
    "critical_t": float,
}
```

### 1. `required_sample_size` — a priori

```python
required_sample_size(
    test: str, *,
    alpha: float,
    power: float,                      # the TARGET power
    effect_size: float,
    tails: int = 2,
    allocation_ratio: float = 1.0,     # N2/N1, two-group test only
    allocation_rule: str = "even-total",   # SPEC F-09; also "n1-grid", "total-grid"
    predictors: int | None = None,     # ttest-regression-coef only
) -> dict
```

`result["power"]` is the power achieved at the returned design, not the target.
Not available for `ttest-generic` — raise `ValueError`.

### 2. `achieved_power` — post hoc

```python
achieved_power(
    test: str, *,
    alpha: float,
    effect_size: float,
    tails: int = 2,
    n: int | None = None,              # single-group tests
    n1: int | None = None,             # two-group test
    n2: int | None = None,
    predictors: int | None = None,
    df: float | None = None,           # ttest-generic only
) -> dict
```

For `ttest-generic`, `effect_size` **is** the noncentrality parameter and `df`
is supplied directly.

### 3. `required_alpha` — criterion

```python
required_alpha(test: str, *, power: float, effect_size: float, tails: int = 2,
               n=None, n1=None, n2=None, predictors=None, df=None) -> dict
```

### 4. `detectable_effect_size` — sensitivity

```python
detectable_effect_size(test: str, *, alpha: float, power: float, tails: int = 2,
                       n=None, n1=None, n2=None, predictors=None, df=None) -> dict
```

`result["effect_size"]` carries the answer.

### 5. `compromise`

```python
compromise(test: str, *, effect_size: float, beta_alpha_ratio: float,
           tails: int = 2, n=None, n1=None, n2=None, predictors=None,
           df=None) -> dict
```

Additionally returns `"beta": float` in the dict.

---

## Error handling

Raise `ValueError` for input outside a documented domain: unknown test key,
`alpha` or `power` not in `(0,1)`, `tails` not in `{1,2}`, an effect size
outside the domain `SPEC.md` gives for the test (F-08, F-13, F-15), a design whose degrees of freedom would be `<= 0`, or an
analysis a test does not support.

Raise `RuntimeError` if a requested quantity is unattainable within a bounded
search (cap the sample-size search at `2**63 - 2` on the total, SPEC §3, and say so in the message).

---

## What you are being judged on

Only the behaviour specified in `SPEC.md`, reached through the functions above.
Internal structure, file layout inside the package, naming of private helpers,
and algorithm choice are entirely yours.

Your implementation will be run against a conformance vector set you have not
seen, with the tolerances stated in `SPEC.md` §5: **exact** equality on integer
sample sizes, `5e-7` on power.
