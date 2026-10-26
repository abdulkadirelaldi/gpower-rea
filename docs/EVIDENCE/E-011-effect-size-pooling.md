# E-011 — The equal-*n* pooling option is a root-mean-square, not a pooled SD

| | |
|---|---|
| **Finding** | [F-11](../../SPEC.md#f-11--the-effect-size-drawer-offers-two-pooled-sds-and-the-equal-n-one-is-an-rms) |
| **Status** | `REA-OPEN` |
| **Method** | Probing the "Determine =>" drawer with deliberately unequal SDs |
| **Target** | G\*Power 3.1.9.x, `t tests` → *Means: Difference between two independent means (two groups)* → **Determine =>** |
| **Probe id** | `P-11` |

## Claim

The effect-size drawer offers two radio options, which compute **different**
standard deviations:

```
"n1 = n2"   :  σ = sqrt( (σ₁² + σ₂²) / 2 )                          <- RMS of the two SDs
"n1 != n2"  :  σ = sqrt( ((n₁-1)σ₁² + (n₂-1)σ₂²) / (n₁+n₂-2) )      <- pooled variance
```

and then `d = (μ₁ - μ₂)/σ`. The first is *not* the textbook pooled SD; it is
the quadratic mean, i.e. the `n₁ = n₂` specialisation of the second formula.

## Why this matters, and why it is not in the manual

The manual labels the two options by sample-size condition, not by formula, and
prints neither expression. A reimplementation naturally offers one pooled SD —
the weighted one — and then disagrees with every user who left the drawer on
its default. Worse, the two options are not a rounding apart:

| | |
|---|---|
| inputs | `μ₁ = 10`, `μ₂ = 8`, `σ₁ = 2`, `σ₂ = 6`, `n₁ = 10`, `n₂ = 40` |
| `"n1 = n2"` (RMS) | `σ = 4.4721360` → `d = 0.4472136` |
| `"n1 != n2"` (pooled) | `σ = 5.4772256` → `d = 0.3651484` |
| required `N` at `α = .05`, power `.80`, two tails | **160** vs **238** |

A 49 % difference in the number of participants recruited, from a radio button
whose formula is undocumented. This is the most consequential finding in the
family for an applied user.

The two options coincide exactly when `σ₁ = σ₂`, or when `n₁ = n₂`. Every
textbook example satisfies one of those, which is why the divergence is rarely
noticed.

## Discriminating probe `P-11`

### Click path

`Test family = t tests` → `Statistical test = Means: Difference between two
independent means (two groups)` → **Determine =>** → in the drawer choose the
`n1 = n2` option → enter `Mean group 1 = 10`, `Mean group 2 = 8`,
`SD σ group 1 = 2`, `SD σ group 2 = 6` → **Calculate** → read `Effect size d`.
Then select the `n1 != n2` option, additionally enter
`Size group 1 = 10`, `Size group 2 = 40`, and **Calculate** again.

### Rows

| row | drawer option | predicted `d` under claim | predicted `d` if both options pooled | predicted `d` if both options RMS |
|---|---|---|---|---|
| `P-11-a` | `n1 = n2` | `0.4472136` | `0.3651484` | `0.4472136` |
| `P-11-b` | `n1 != n2`, `n₁=10`, `n₂=40` | `0.3651484` | `0.3651484` | `0.4472136` |

The claim is the only one of the three candidates under which the two rows
*differ*. So a single pair of observations settles it, and the direction of
the difference identifies which option is which.

Control row (the options must agree when the SDs are equal):

| row | inputs | predicted `d`, both options |
|---|---|---|
| `P-11-c` | `μ₁=5`, `μ₂=3`, `σ₁=σ₂=4`, `n₁=17`, `n₂=31` | `0.5000000` |

### Observation

`probes/REA-RESULTS.md`, rows `P-11-a` … `P-11-c`.

## Engine output

```console
$ gpower effect-size -c d-two-independent-means \
      --param mean1=10 --param mean2=8 --param sd1=2 --param sd2=6
d = 0.4472135955
formula: sigma = sqrt((sd1^2 + sd2^2) / 2)   [G*Power 'n1 = n2' option]
use with: --test ttest-indep-means --effect-size 0.4472135955

$ gpower effect-size -c d-two-independent-means \
      --param mean1=10 --param mean2=8 --param sd1=2 --param sd2=6 \
      --param equal_n=false --param n1=10 --param n2=40
d = 0.3651483717
formula: sigma = sqrt(((n1-1)sd1^2 + (n2-1)sd2^2) / (n1+n2-2))   [G*Power 'n1 != n2' option]
```

Every calculator echoes the formula it used, so the choice is never implicit in
a saved result. Locked by:

```python
# tests/test_effectsize.py
def test_equal_n_option_uses_rms_not_pooled():
    out = es.d_two_independent_means(10.0, 8.0, sd1=2.0, sd2=6.0, equal_n=True)
    assert out["pooled_sd"] == pytest.approx(math.sqrt((4.0 + 36.0) / 2.0))

def test_equal_sds_make_both_options_agree(): ...
def test_the_two_pooling_options_differ(): ...
```

## Related: the matched-pairs drawer

The same drawer concept applies to the dependent-means test, where `dz` is
built from the two marginal SDs and the pre-post correlation:

```
σ_diff = sqrt( σ₁² + σ₂² - 2·ρ·σ₁·σ₂ )        dz = (μ₁ - μ₂)/σ_diff
```

The correlation enters **only here**, never in the power formula (E-003) —
applying it twice is the companion error to this one, and
`tests/test_effectsize.py::test_higher_correlation_gives_larger_dz` pins the
monotone direction.

## Verdict

`REA-OPEN`, but with the strongest practical consequence of any finding here.
Both options are implemented, each labels itself in the output, and the
`P-11-a`/`P-11-b` pair is a two-observation discriminator.

## Re-run

```console
$ python -m pytest tests/test_effectsize.py -q
```
