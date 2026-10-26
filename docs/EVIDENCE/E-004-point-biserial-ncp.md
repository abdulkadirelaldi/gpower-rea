# E-004 — Point biserial: the noncentrality uses `√N`, the statistic uses `√(N-2)`

| | |
|---|---|
| **Finding** | [F-04](../../SPEC.md#f-04--point-biserial-ν--n---2-δ--r√n1-r²) |
| **Status** | `REA-DERIVED` (probe specified for confirmation) |
| **Method** | Cross-entry algebraic reduction |
| **Target** | G\*Power 3.1.9.x, `t tests` |
| **Probe id** | `P-04` |

## Claim

```
ν = N - 2
δ = r · sqrt( N / (1 - r²) )
```

The radicand of `δ` is `N`. The *test statistic* for the same hypothesis is
`t = r·√(N-2)/√(1-r²)`, so the obvious guess — reuse the statistic's form for
the noncentrality — is wrong.

## Why this is not in the manual

The manual prints the effect-size metric (`|r|`) and says the test is a
*t* test on `N-2` degrees of freedom. It does not print the noncentrality
expression. Both `√N` and `√(N-2)` give a correct-looking noncentral *t*
computation, both agree asymptotically, and they differ by one or two
participants for `N < 40` — exactly the range a correlation power analysis is
usually run in. The discrepancy is invisible in any example with `N > 200`.

## Derivation (this is the decisive argument)

Treat the point-biserial correlation as a two-group mean difference with a
balanced dichotomy. Then

```
d  = 2r / sqrt(1 - r²)                      (standard conversion, p = 1/2)
δ  = d · sqrt(n₁·n₂/(n₁+n₂))                (F-05, with n₁ = n₂ = N/2)
   = d · sqrt(N/4)
   = (2r / sqrt(1-r²)) · (sqrt(N)/2)
   = r · sqrt( N / (1-r²) )                 ← the claimed form
```

and the degrees of freedom match as well: `n₁+n₂-2 = N-2`.

The `√(N-2)` candidate does **not** reproduce the two-group result. Since
F-01 requires two menu entries that describe the same hypothesis to agree, the
`√N` form is forced.

Enforced in code:

```python
# tests/test_engine_invariants.py
def test_point_biserial_matches_balanced_two_group():
    for r in (0.2, 0.3, 0.4):
        d = 2.0 * r / math.sqrt(1.0 - r * r)
        a = solve("ttest-point-biserial", "power", alpha=0.05,
                  effect_size=r, tails=2, n=80)
        b = solve("ttest-indep-means", "power", alpha=0.05,
                  effect_size=d, tails=2, n1=40, n2=40)
        assert a.noncentrality == pytest.approx(b.noncentrality, rel=1e-12)
        assert a.power == pytest.approx(b.power, abs=1e-12)
```

## Discriminating probe `P-04`

Choose a small `N` so the two candidates separate.

### Click path

`Test family = t tests` → `Statistical test = Correlation: Point biserial
model` → `Post hoc` → `Tail(s) = Two`, `Effect size |r| = 0.5`,
`α err prob = 0.05`, `Total sample size = 20` → **Calculate**, and read
`Noncentrality parameter δ`.

### Predictions

| row | `N` | `r` | candidate `√N` (claimed) | candidate `√(N-2)` |
|---|---|---|---|---|
| `P-04-a` | 20 | 0.5 | `δ = 2.5819889` | `δ = 2.4494897` |
| `P-04-b` | 10 | 0.6 | `δ = 2.3717082` | `δ = 2.1213203` |
| `P-04-c` | 12 | 0.3 | `δ = 1.0894096` | `δ = 0.9944903` |

`δ` is printed to seven decimals, so a single row settles it.

Corresponding a-priori rows, where the difference shows up as a different `N`:

| row | inputs | claimed `N` | `√(N-2)` candidate |
|---|---|---|---|
| `P-04-d` | `r = 0.5`, `α = .05`, power `.80`, two tails | 26 | 28 |
| `P-04-e` | `r = 0.7`, `α = .05`, power `.80`, two tails | 11 | 13 |

### Observation

`probes/REA-RESULTS.md`, rows `P-04-a` … `P-04-e`.

## Engine output

```console
$ gpower solve -t point-biserial -s power -a 0.05 -e 0.5 -n 20 --json
  "noncentrality": 2.581988897471611, "df": 18.0
$ gpower solve -t point-biserial -a 0.05 -p 0.8 -e 0.5 --json
  "sample_size": {"n": 26, "total": 26}
```

## Verdict

Derivation holds and is enforced; GUI probe specified with a seven-decimal
discriminator.

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k point_biserial -q
```
