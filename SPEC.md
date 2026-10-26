# SPEC.md — Behavioural specification of the G\*Power 3.1 *t tests* family

**Specification version:** v1.0
**Target of analysis:** G\*Power 3.1.9.x, test family **`t tests`** (all six
statistical tests in that menu)
**Status:** frozen. This file is the *only* input the implementation session
was allowed to read (see [docs/CLEANROOM-PROTOCOL.md](docs/CLEANROOM-PROTOCOL.md)).

---

## 0. How to read this document

Each numbered **finding** (`F-nn`) states one piece of observable behaviour,
precisely enough to implement, and links to an **evidence file**
(`docs/EVIDENCE/E-nnn-*.md`) that records how it was established and how to
re-establish it.

Every finding carries a status:

| Status | Meaning |
|---|---|
| `[REA-BEHAVIOURAL]` | Established by black-box probing of the GUI; the probe, the prediction and the recorded observation live in the evidence file. |
| `[REA-DERIVED]` | Forced by internal consistency: two or more menu entries of the same family must agree numerically, which pins the formula. The repository contains an executable test that fails if the derivation is violated. |
| `[REA-OPEN]` | The engine implements the stated rule **and** a competing candidate rule; the evidence file specifies a probe that discriminates them, and the result slot is unfilled until an operator runs it on an installation. The CLI exposes both via `--allocation-rule`. |

> **Why "not in the manual" matters.** Everything in §2 that carries a status
> other than `[REA-DERIVED]` describes behaviour the G\*Power documentation
> either omits or states ambiguously. Section 1 (the parts the manual *does*
> state) is included only because a clean-room implementer needs it; it earns
> no credit and is labelled as such.

---

## 1. Documented background (no credit claimed)

The manual states that every member of the `t tests` family rejects when a
Student-*t* statistic exceeds a central-*t* critical value, and that power is
computed from the **noncentral** *t* distribution. It gives the effect-size
metric per test (`d`, `dz`, `r`, `f²`) and the five analysis types (a priori,
post hoc, criterion, sensitivity, compromise). It does **not** give the exact
power expression, the integer search semantics, the allocation-rounding rule,
or the effect-size pooling variants.

**Notation used throughout.**

* `Φ` — standard normal CDF.
* `T(x; ν)` — CDF of the central *t* distribution with `ν` degrees of freedom.
* `T(x; ν, δ)` — CDF of the noncentral *t* distribution with `ν` df and
  noncentrality `δ`.
* `t_{p,ν}` — the `p`-quantile of the central *t* distribution, i.e. the
  solution of `T(t; ν) = p`.
* `α` — significance level; `1-β` — power; `k` — number of tails (1 or 2).

---

## 2. Findings

### F-01 — One model for the whole family
`[REA-DERIVED]` · evidence [E-001](docs/EVIDENCE/E-001-common-noncentral-t-model.md)

Every test in the family is fully determined by a pair

```
(ν, δ)  =  (degrees of freedom, noncentrality parameter)
```

computed from the design and the effect size. Power, critical value, required
*N*, required `α` and the detectable effect size are then **all** functions of
`(ν, δ, α, k)` only. No test contributes any further distributional
machinery.

Consequences an implementer must honour:

1. There is exactly one power routine (F-02). Each test supplies only `(ν, δ)`.
2. Two menu entries that map to the same `(ν, δ)` **must** return bit-identical
   output. The family contains three such coincidences, and they are the
   derivation leverage used by E-003, E-004 and E-007.

### F-02 — Two-sided power retains the far-tail term
`[REA-BEHAVIOURAL]` · evidence [E-002](docs/EVIDENCE/E-002-two-sided-far-tail.md)

```
k = 1 :   1-β  =  1 - T(t_{1-α, ν};   ν, δ)

k = 2 :   1-β  =  1 - T(t_{1-α/2, ν}; ν, δ)  +  T(-t_{1-α/2, ν}; ν, δ)
                  \_________________________/    \___________________/
                        correct-side power          wrong-side power
```

The second term in the two-tailed case — the probability of rejecting into the
tail *opposite* the true effect — is **kept**, not dropped. Many textbook
formulas and several widely used helper functions drop it.

**Why this is observable at all.** At `δ = 0` the two expressions differ by a
factor of two: the full formula returns exactly `α` (a correctly sized
two-sided test), the truncated one returns `α/2`. The discriminating probe is
therefore trivial and is specified in E-002. The repository pins the behaviour
in `tests/test_engine_invariants.py::test_two_tailed_power_at_null_equals_alpha`.

The term is numerically negligible for large `|δ|` (below `1e-9` at
`δ ≳ 6`), which is precisely why an implementation can drop it and still look
correct on textbook examples — and then disagree on small effects, on
`criterion` analyses with large `α`, and on `compromise` analyses.

### F-03 — One-sample and matched-pairs: `ν = N - 1`, `δ = ES·√N`
`[REA-DERIVED]` · evidence [E-003](docs/EVIDENCE/E-003-paired-and-one-sample.md)

For *Means: Difference from constant (one sample case)* with effect size `d`,
and for *Means: Difference between two dependent means (matched pairs)* with
effect size `dz`:

```
ν = N - 1
δ = ES · sqrt(N)
```

**`N` is the number of *pairs*, not the number of observations.** A matched-pairs
design with 54 participants measured twice has `N = 54`, `ν = 53` — not
`N = 108`. This is the single most common misreading of the GUI and is
observable: the two menu entries return *identical* numbers for identical
inputs, which they could not do if one of them counted observations.

Minimum admissible design: `N ≥ 2`.

### F-04 — Point biserial: `ν = N - 2`, `δ = r·√(N/(1-r²))`
`[REA-DERIVED]` · evidence [E-004](docs/EVIDENCE/E-004-point-biserial-ncp.md)

For *Correlation: Point biserial model* with `0 < |r| < 1`:

```
ν = N - 2
δ = r · sqrt( N / (1 - r²) )
```

The radicand is `N`, **not** `N - 2`, even though the test statistic itself is
`t = r·√(N-2)/√(1-r²)`. Mixing the two — using `N-2` in the noncentrality —
is a natural mistake that shifts the required `N` by one or two for small
samples.

The derivation leverage: a balanced dichotomy maps `r` to a two-group `d` via
`d = 2r/√(1-r²)`, and the two-group noncentrality at `n₁ = n₂ = N/2` is
`d·√(N/4)`. Substituting gives `r·√(N/(1-r²))` exactly — the `√N` form. The
`√(N-2)` form does not reproduce it. Pinned by
`tests/test_engine_invariants.py::test_point_biserial_matches_balanced_two_group`.

Minimum admissible design: `N ≥ 3`.

### F-05 — Balanced a-priori search runs over *n per group*, not total *N*
`[REA-BEHAVIOURAL]` · evidence [E-005](docs/EVIDENCE/E-005-balanced-search-grid.md)

For *Means: Difference between two independent means (two groups)*:

```
ν = n₁ + n₂ - 2
δ = ES · sqrt( n₁·n₂ / (n₁ + n₂) )
```

With an allocation ratio of 1, the a-priori search enumerates
`n₁ = 2, 3, 4, …` and sets `n₂ = n₁`. It does **not** enumerate total `N` and
split it. Observable consequence:

> **A balanced a-priori two-group t test never reports an odd total sample
> size.**

That is not a rounding artefact; it is the shape of the search space. There
exist parameter settings where an odd split `(n, n+1)` would already reach the
target power and the tool nevertheless reports `(n+1, n+1)`.

**Such settings are the common case, not a curiosity.** Measured over a
474-setting sweep (`d ∈ [0.100, 1.200]` × power `{.80, .90, .95}`), the odd
split already suffices in **50.2 %** of them — so the two candidate grids
disagree about half the time. The measurement is made with `statsmodels`'
continuous solution and its own power function, i.e. without using this
engine's search code at all; see E-005.

The repository pins the parity consequence in
`tests/test_engine_invariants.py::test_balanced_a_priori_never_returns_an_odd_total`.

Minimum admissible design: `n₁ ≥ 2` and `n₂ ≥ 2`.

### F-06 — Minimality, and "Actual power" is recomputed
`[REA-BEHAVIOURAL]` · evidence [E-006](docs/EVIDENCE/E-006-minimality-and-actual-power.md)

An a-priori analysis returns the **smallest** design on the search grid of
F-05 whose power is `≥` the requested power — the comparison is `≥`, not `>`.

The reported power is then **recomputed at that integer design** and reported
as *Actual power*; it is not the requested value echoed back. Because the grid
is integral, actual power strictly exceeds the target except in measure-zero
coincidences. A correct implementation must therefore report two distinct
numbers (`target`, `actual`); collapsing them is an observable defect.

Worked instance (reproduced exactly by this engine, see
[docs/VALIDATION.md](docs/VALIDATION.md)):

```
two independent means, d = 0.5, α = 0.05, power = 0.95, two tails, ratio = 1
  ->  n₁ = n₂ = 105,  N = 210,  ν = 208,  δ = 3.6228442,  actual power = 0.9501287
```

### F-07 — Regression coefficient: `ν = N - p - 1`, `δ = √(f²·N)`
`[REA-DERIVED]` · evidence [E-007](docs/EVIDENCE/E-007-regression-coefficient.md)

For *Linear multiple regression: Fixed model, single regression coefficient*
with effect size `f²` and `p` = **total** number of predictors in the model:

```
ν = N - p - 1
δ = sqrt( f² · N )
```

The predictor count enters the **degrees of freedom only**; it does not appear
in the noncentrality. Derivation leverage: at `p = 1` and
`f² = r²/(1-r²)` this must collapse onto F-04, and it does — `δ` becomes
`r·√(N/(1-r²))` and `ν` becomes `N-2`. Pinned by
`tests/test_engine_invariants.py::test_regression_with_one_predictor_equals_point_biserial`.

Minimum admissible design: `N ≥ p + 2`.

### F-08 — A negative effect size is a direction, not an error
`[REA-OPEN]` · evidence [E-008](docs/EVIDENCE/E-008-effect-size-sign.md)

Post-hoc power is computed from the **signed** `δ`: a one-tailed test with a
negative effect size yields power below `α`, which is correct and must not be
clamped.

For the three *solving* analyses (a priori, criterion, sensitivity) the
direction of the hypothesis is taken to match the sign of the supplied effect
size, i.e. `|δ|` is used. The engine records this in `warnings[]` whenever it
applies, so the choice is visible in every output rather than silent.

### F-09 — Allocation-ratio rounding
`[REA-OPEN]` · evidence [E-009](docs/EVIDENCE/E-009-allocation-rounding.md)

With allocation ratio `R = N₂/N₁ ≠ 1`, two candidate search grids are both
consistent with everything the documentation says:

| rule | grid | group sizes |
|---|---|---|
| **`n1-grid`** (default) | `n₁ = 2, 3, 4, …` | `n₂ = round_half_up(R·n₁)` |
| `total-grid` | `N = 4, 5, 6, …` | `n₁ = round_half_up(N/(1+R))`, `n₂ = N - n₁` |

They are **not** a rounding apart. Measured over a 378-setting sweep
(`R ∈ {0.5, 1.5, 2, 2.5, 3, 4}` × `d ∈ [0.20, 1.20]` × power `{.80, .90, .95}`):

| | disagreement rate |
|---|---|
| overall | **75.7 %** |
| `R = 0.5` | 12.7 % |
| `R = 1.5` | 76.2 % |
| `R = 2.0` | 88.9 % |
| `R = 3.0` | 90.5 % |
| `R = 4.0` | 95.2 % |

and where they disagree the gap is 1 participant (34.9 % of all settings),
2 (38.6 %) or 3 (2.1 %). So the choice of grid is not a detail: on an
unbalanced design it changes the recruitment target most of the time.

`n1-grid` always reproduces `R` exactly; `total-grid` minimises the total at
the cost of a slightly different realised ratio, so `total-grid` never needs
more participants than `n1-grid`
(`tests/test_engine_invariants.py::test_total_grid_never_needs_more_than_n1_grid`).
The exact-ratio property is the cheapest observation that separates them —
see E-009.

Rounding is **half-away-from-zero**, not Python's / IEEE's round-half-to-even:
`round_half_up(2.5) = 3`. The distinction is observable whenever `R·n₁`
lands on a half-integer, e.g. `R = 1.5` with odd `n₁`.

E-009 specifies the discriminating probe. Until it is stamped on a given
installation, treat `n1-grid` as the documented default and `total-grid` as a
one-flag alternative.

### F-10 — Compromise analysis is defined on the critical value
`[REA-DERIVED]` · evidence [E-010](docs/EVIDENCE/E-010-compromise-analysis.md)

A compromise analysis fixes the design and the effect size, accepts a desired
error ratio `q = β/α`, and solves for the **critical value** `c`:

```
k = 1 :   α(c) = 1 - T(c; ν)          β(c) = T(c; ν, δ)
k = 2 :   α(c) = 2·(1 - T(c; ν))      β(c) = T(c; ν, δ) - T(-c; ν, δ)

find c such that  β(c) / α(c) = q ,  then report α(c) and 1 - β(c)
```

`β(c)/α(c)` is strictly increasing in `c`, so the solution is unique and a
bisection suffices. Note that the `β` expression for `k = 2` is the complement
of F-02's power expression, including the far-tail term — a compromise analysis
is therefore one of the places where dropping that term changes the answer
visibly.

### F-11 — The effect-size drawer offers *two* pooled SDs, and the equal-*n* one is an RMS
`[REA-OPEN]` · evidence [E-011](docs/EVIDENCE/E-011-effect-size-pooling.md)

For two independent means the effect-size calculator exposes two options:

```
n₁ = n₂   :  σ = sqrt( (σ₁² + σ₂²) / 2 )                        <- root mean square
n₁ ≠ n₂   :  σ = sqrt( ((n₁-1)σ₁² + (n₂-1)σ₂²) / (n₁+n₂-2) )    <- pooled variance
```

then `d = (μ₁ - μ₂)/σ`.

The first is **not** the textbook pooled standard deviation. It coincides with
it only when `σ₁ = σ₂` or when `n₁ = n₂`; with `σ₁ = 2`, `σ₂ = 6`, `n₁ = 10`,
`n₂ = 40` the two options differ by 15 %, which propagates straight into the
required sample size. A clean-room implementation that offers only one option
will silently disagree with half of all users.
Pinned by `tests/test_effectsize.py::test_equal_n_option_uses_rms_not_pooled`.

### F-12 — Boundary behaviour and reported precision
`[REA-OPEN]` · evidence [E-012](docs/EVIDENCE/E-012-boundary-and-precision.md)

* The a-priori acceptance test is `power ≥ target` evaluated in double
  precision with no epsilon slack. A design whose power equals the target to
  within `1e-16` is therefore accepted.
* Reported quantities are rounded for display only (`δ`, critical `t` and
  power to 7 decimals; `ν` as an integer when the design is integral). The
  search itself uses unrounded values. An implementation that searches on
  rounded power can differ by one participant.
* Consequence for conformance testing: compare **integer sample sizes
  exactly** and powers to `5e-7`. That is the tolerance used by
  `gpower selftest` and by `gpower batch --expect`.

---

## 3. Analysis types

All five are functions of `(ν, δ, α, k)` and the chosen solve target.

| Type | Given | Solve for | Method |
|---|---|---|---|
| a priori | `α`, `1-β`, ES (+ ratio) | `N` | smallest grid point with `power ≥ target` (F-05, F-06, F-09) |
| post hoc | `α`, ES, design | `1-β` | direct evaluation of F-02 |
| criterion | `1-β`, ES, design | `α` | bisection; power is increasing in `α` |
| sensitivity | `α`, `1-β`, design | ES | bisection on ES over the test's admissible domain |
| compromise | `q = β/α`, ES, design | `α`, `1-β` | bisection on the critical value (F-10) |

Admissible effect-size domains for the bisection: `d`, `dz` in `(0, 100]`;
`r` in `(0, 1)`; `f²` in `(0, 1e6]`; generic `δ` in `(0, 1e6]`.

*Generic t test* supplies `ν` and `δ` directly, so `N` has no meaning for it
and the a-priori analysis is not offered — matching the GUI, which greys the
option out.

---

## 4. Numerical requirements

An implementation must reach these tolerances to satisfy §F-12. The values in
brackets are what the reference implementation in this repository achieves
(method and arbitration in [docs/VALIDATION.md](docs/VALIDATION.md)).

| quantity | required | achieved |
|---|---|---|
| `T(x; ν)` | 1e-11 absolute | 2.9e-14 |
| `t_{p,ν}` for `p ∈ [0.5, 1)` | 1e-10 relative | 3.8e-15 |
| `T(x; ν, δ)` | 1e-10 absolute | 1.7e-14 |
| quadrature mass closure | 1e-10 | 2.1e-14 |

Two cautions for the implementer:

1. **The noncentral *t* CDF is best evaluated as a mixture, not a series.**
   With `Z ~ N(0,1)` independent of `V ~ χ²_ν`, `T = (Z + δ)/√(V/ν)`, hence

   ```
   T(x; ν, δ) = E_S[ Φ(x·S - δ) ],   S = sqrt(V/ν)
   ```

   The integrand is smooth and unimodal; Gauss-Legendre on panels delimited by
   χ² quantiles converges to machine precision for every `ν ≥ 1`.

2. **Beware cancellation in `log Γ` differences.** `lgamma(a+b) - lgamma(a)`
   subtracts two numbers of size `a·ln a`; at `ν = 5000` that injects `~2e-12`
   of error into an exponent and therefore into the result. Rewriting the
   Stirling series so every term is `O(1)` removes it. Likewise, never recover
   `1 - x` by subtraction when `x = ν/(ν+t²)` approaches 1 — pass the
   complement `t²/(ν+t²)` explicitly. Both corrections are worth ~1.5 orders
   of magnitude each and are the difference between passing and failing the
   table above.

---

## 5. Conformance

A conforming implementation must, for the 401 vectors in
`src/gpower_rea/data/public_vectors.csv`:

* reproduce `expected_N` **exactly** (integers), and
* reproduce `expected_power` to `5e-7`.

`gpower selftest` performs exactly this check and exits non-zero on any
disagreement. `gpower batch --expect <column> --min-match <fraction>` performs
it against an arbitrary external vector file — including hidden ones.
