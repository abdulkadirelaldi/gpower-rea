# E-010 — Compromise analysis solves for the critical value, not for `α`

| | |
|---|---|
| **Finding** | [F-10](../../SPEC.md#f-10--compromise-analysis-is-defined-on-the-critical-value) |
| **Status** | `REA-DERIVED` (probe specified for confirmation) |
| **Method** | Structural probing + consistency with F-02 |
| **Target** | G\*Power 3.1.9.x, `t tests`, `Type of power analysis = Compromise` |
| **Probe id** | `P-10` |

## Claim

Given a fixed design (`ν`, `δ`) and a desired error ratio `q = β/α`, the
analysis solves for the **critical value** `c`:

```
k = 1 :   α(c) = 1 - T(c; ν)          β(c) = T(c; ν, δ)
k = 2 :   α(c) = 2·(1 - T(c; ν))      β(c) = T(c; ν, δ) - T(-c; ν, δ)

solve  β(c)/α(c) = q   for c, then report α(c) and 1 - β(c)
```

`β(c)/α(c)` is strictly increasing in `c`, so the root is unique.

## Why this is not in the manual

The manual describes compromise analysis in words ("you specify the ratio of
β to α and the tool finds the corresponding error levels") and does not state
the parameterisation. The natural reimplementation is a bisection on `α`
directly: pick `α`, compute `β` from the power formula, check the ratio. That
converges to the same root *only if* `β` is the exact complement of the
two-tailed power expression including the far-tail term (F-02). An
implementation that drops that term gets a visibly different `α` here — which
makes compromise analysis the one analysis type where the F-02 choice is
*always* material, not just at small effect sizes.

Compromise analysis is also the least-used of the five types and therefore the
least likely to be covered by a reimplementation's test suite at all.

## Discriminating probe `P-10`

### Click path

`Test family = t tests` → `Statistical test = Means: Difference between two
independent means (two groups)` → `Type of power analysis = Compromise` →
`Tail(s) = Two`, `Effect size d = 0.5`, `β/α ratio = …`,
`Sample size group 1 = 40`, `Sample size group 2 = 40` → **Calculate**.

### Rows

| row | `q = β/α` | predicted `α err prob` | predicted `β err prob` | predicted power | predicted `Critical t` |
|---|---|---|---|---|---|
| `P-10-a` | 1 | `0.1846853` | `0.1846853` | `0.8153147` | `1.3383050` |
| `P-10-b` | 2 | `0.1239699` | `0.2479399` | `0.7520601` | `1.5551029` |
| `P-10-c` | 4 | `0.0802483` | `0.3209934` | `0.6790066` | `1.7723075` |

Three independent checks live in each row: the ratio `β/α` must equal `q` to
printed precision, `α + ...` is not constrained (so it is a real solve, not a
normalisation), and `power = 1 - β` exactly.

Row `P-10-a` is the most informative single observation: at `q = 1` the
balanced-error solution must have `α = β` to all seven decimals. An
implementation that drops the F-02 far-tail term reports a different pair here
while still satisfying `α = β`, so compare the *values*, not just their
equality.

### Observation

`probes/REA-RESULTS.md`, rows `P-10-a` … `P-10-c`.

## Engine output

```console
$ gpower solve -t indep -s compromise -e 0.5 --n1 40 --n2 40 --q 1 --json
  "alpha": 0.18468527...,
  "power": 0.81531472...,
  "critical_t": 1.33830497...,
  "target": { "beta_alpha_ratio": 1.0, "beta": 0.18468527... }
```

and the ratio invariant is enforced for every `q` tested:

```python
# tests/test_engine_invariants.py
def test_compromise_honours_the_requested_ratio():
    for q in (0.5, 1.0, 2.0, 4.0):
        res = solve("ttest-indep-means", "compromise", effect_size=0.5, tails=2,
                    n1=40, n2=40, beta_alpha_ratio=q)
        beta = res.target["beta"]
        assert beta / res.alpha == pytest.approx(q, rel=1e-7)
        assert res.power == pytest.approx(1.0 - beta, abs=1e-12)
```

## Note on the reported critical value

For the four other analysis types the engine reports `t_{1-α/2, ν}` (or
`t_{1-α, ν}`) in the `critical_t` field. For compromise analysis the field
carries the solved `c`, which is the same quantity by construction: `α(c)` was
*defined* so that `c` is the critical value at that `α`. The two readings
agree, and the round trip is worth checking as a fifth observation per row:
feeding the reported `α` back through a post-hoc analysis must reproduce the
reported power.

```console
$ gpower solve -t indep -s power -e 0.5 --n1 40 --n2 40 -a 0.1846853 --json
  "power": 0.8153147...,  "critical_t": 1.3383050...
```

## Verdict

Derivation holds, is enforced by the ratio test, and the round trip through
post-hoc analysis closes. Probe rows above give seven-decimal discriminators.

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k compromise -q
```
