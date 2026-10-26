# E-007 — The predictor count enters `ν` only, never `δ`

| | |
|---|---|
| **Finding** | [F-07](../../SPEC.md#f-07--regression-coefficient-ν--n---p---1-δ--f²n) |
| **Status** | `[REA] DERIVED + OBSERVED` — observed on G\*Power 3.1.9.6 (macOS) |
| **Method** | Reduction to a known family member + single-variable isolation |
| **Target** | G\*Power 3.1.9.x, `t tests` → *Linear multiple regression: Fixed model, single regression coefficient* |
| **Probe id** | `P-07` |

## Claim

```
ν = N - p - 1
δ = sqrt( f² · N )
```

where `p` is the **total** number of predictors in the model (not the number
being tested — that is always one for this entry).

## Why this is not in the manual

The manual lists the inputs (`Effect size f²`, `Number of predictors`,
`α`, `power`) and the output fields, but not the noncentrality. The plausible
competing conventions are `δ = √(f²·N)`, `δ = √(f²·(N-p-1))` and
`δ = √(f²·(N-p))`. All three are dimensionally fine and agree asymptotically;
they differ by one to three participants in the `N < 100` range where
regression power analyses are typically run.

Separately, the role of `p` is genuinely ambiguous from the UI: it could
reasonably enter either the degrees of freedom, the noncentrality, or both.

## Derivation

Set `p = 1` and `f² = r²/(1-r²)`. The entry then tests the single slope of a
simple regression, which is the same hypothesis as the correlation *t* test of
E-004. Under the claim:

```
ν = N - 1 - 1 = N - 2                       ✓ matches E-004
δ = sqrt( (r²/(1-r²)) · N ) = r·sqrt(N/(1-r²))   ✓ matches E-004
```

Neither competing convention reproduces E-004: `√(f²·(N-2))` gives
`r·√((N-2)/(1-r²))`, which is the candidate E-004 already rules out.

Enforced in code:

```python
# tests/test_engine_invariants.py
def test_regression_with_one_predictor_equals_point_biserial():
    for r in (0.15, 0.3, 0.45):
        f2 = r * r / (1.0 - r * r)
        a = solve("ttest-point-biserial",  "n", alpha=0.05, power_target=0.9,
                  effect_size=r,  tails=2)
        b = solve("ttest-regression-coef", "n", alpha=0.05, power_target=0.9,
                  effect_size=f2, tails=2, extra={"predictors": 1})
        assert a.sample_size["total"] == b.sample_size["total"]
        assert a.df == b.df
        assert a.noncentrality == pytest.approx(b.noncentrality, rel=1e-12)
```

Measured at `r = 0.3` (`f² = 0.0989010989`): both entries return `N = 109`,
`ν = 107`, `δ = 3.2833245`.

## Discriminating probe `P-07` — isolating the role of `p`

Hold `N` and `f²` fixed and vary **only** the predictor count. Under the
claim, `δ` is unchanged and `Df` moves one-for-one with `p`; power changes only
through `ν`, i.e. in the fourth decimal.

### Click path

`Test family = t tests` → `Statistical test = Linear multiple regression:
Fixed model, single regression coefficient` → `Post hoc` → `Tail(s) = Two`,
`Effect size f² = 0.15`, `α err prob = 0.05`, `Total sample size = 100`,
`Number of predictors = …` → **Calculate**.

### Rows

| row | `p` | predicted `δ` | predicted `Df` | predicted power |
|---|---|---|---|---|
| `P-07-a` | 1 | `3.8729833` | `98` | `0.9695895` |
| `P-07-b` | 5 | `3.8729833` | `94` | `0.9694766` |

Two things are being tested at once: `δ` must be **identical** across the two
rows (so `p` does not enter the noncentrality), and `Df` must drop by exactly
4 (so `p` enters `ν` with coefficient 1).

A-priori control rows, where the `N` requirement is dominated by `δ` and so
barely moves with `p`:

| row | `p` | `f²` | target power | predicted `N` | predicted `Df` |
|---|---|---|---|---|---|
| `P-07-c` | 1 | 0.15 | 0.80 | `55` | `53` |
| `P-07-d` | 5 | 0.15 | 0.80 | `55` | `49` |

That `N` is the same for `p = 1` and `p = 5` here is itself informative: it is
what you expect when `p` touches only `ν`, and it would be surprising if `p`
appeared inside `δ`.

### Observation

`probes/REA-RESULTS.md`, rows `P-07-a` … `P-07-d`.

## Domain note

`N ≥ p + 2` is required for `ν ≥ 1`. The engine raises a validation error
rather than returning a power value for an infeasible design:

```console
$ gpower solve -t regression-coef -s power -a 0.05 -e 0.15 -n 4 --predictors 10
gpower: invalid input: ttest-regression-coef: sample size too small,
        degrees of freedom = -7
```

## [REA] Observation — G\*Power 3.1.9.6

Read off the GUI's *Output parameters* panel by `tools/rea_campaign.py`
(raw records in [`probes/observations/`](../../probes/observations/)). The
predictions were registered in `probes/probe_worksheet.csv` before any
observation was made, and are shown unchanged.

| probe | read | G\*Power printed | pre-registered engine prediction | competing prediction | verdict |
|---|---|---|---|---|---|
| `P-07-a` | delta / Df / Power | `3.8729833 / 98 / 0.9695895` | `3.8729833 / 98 / 0.9695895` | `delta would move with p if p entered the noncentrality` | **SUPPORTS** |
| `P-07-b` | delta / Df / Power | `3.8729833 / 94 / 0.9694766` | `3.8729833 / 94 / 0.9694766` | `delta would move with p if p entered the noncentrality` | **SUPPORTS** |
| `P-07-c` | N / Df | `55 / 53` | `55 / 53` | `-` | **SUPPORTS** |
| `P-07-d` | N / Df | `55 / 49` | `55 / 49` | `-` | **SUPPORTS** |

Every other field G\*Power printed for these rows also matches the current
engine — `tests/test_gpower_observed.py` checks each one.

## Verdict

**[REA] F-07 — observed.** `δ` is identical for `p = 1` and `p = 5` while `Df` drops by four: the predictor count enters `ν` only.

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k regression_with_one_predictor -q
```
