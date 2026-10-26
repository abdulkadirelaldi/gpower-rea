# SPEC.md — Behavioural specification of the G\*Power 3.1 *t tests* family

**Specification version:** v1.1
**Target of analysis:** G\*Power 3.1.9.x, test family **`t tests`** (all six
statistical tests in that menu)
**Status:** v1.0 was frozen and handed to an independent implementation
session as its only input (see
[docs/CLEANROOM-PROTOCOL.md](docs/CLEANROOM-PROTOCOL.md)). That session
reported twelve points the text did not determine, and on five of them the two
implementations demonstrably behaved differently. **v1.1 is v1.0 plus
[F-13](#f-13--points-the-specification-left-undetermined-now-specified),
which closes all twelve.** F-01…F-12 are unchanged apart from the measured
frequencies added to F-05 and F-09.

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
| `[SPEC-CLOSURE]` | Not a claim about G\*Power at all: a point where *this document* was too weak to determine an implementation, now specified so that two implementations of it cannot drift apart. Only F-13. |

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

### F-13 — Points the specification left undetermined, now specified
`[SPEC-CLOSURE]` · evidence [E-013](docs/EVIDENCE/E-013-cleanroom-divergence.md)

This finding is of a different kind from F-01…F-12: it is not a claim about
G\*Power, it is a record of **where this specification was not strong enough
to determine an implementation**, and what it now says instead.

It exists because the clean-room pass worked. An independent implementation
built from v1.0 of this document reported twelve points it could not resolve
from the text; on five of them the two implementations then demonstrably
behaved differently. Those five were specification defects, invisible to any
amount of testing one implementation against itself.

| # | undetermined in v1.0 | v1.1 says | diverged? |
|---|---|---|---|
| 1 | which sign rule the **compromise** analysis follows — F-08 named only three solving analyses | compromise is a solving analysis: it uses `\|δ\|` and emits the F-08 warning | **yes** — `α = 0.133` vs `0.867` |
| 2 | whether a negative `f²` is admissible | **no**: `f²` is a squared quantity and `δ = √(f²·N)` has no real value; reject it | no (both refused) |
| 3 | which effect size the result reports once `\|ES\|` is substituted | the **input as supplied**, signed; the value actually used is recoverable from `noncentrality`, and `warnings[]` flags the substitution. For the sensitivity analysis the field carries the answer, since there is no input to echo | **yes** |
| 4 | the numerical endpoints of the sensitivity bisection | closed brackets: `d`, `dz` on `[1e-12, 100]`; `r` on `[1e-12, 1-1e-12]`; `f²` and generic `δ` on `[1e-12, 1e6]` | **yes** — `1e-9` vs `1e-12` |
| 5 | the `α` bracket of the criterion analysis | bisect on **`log α`** over `[1e-300, 1-1e-15]`, and report the solution however small | **yes** — `1e-12` vs `4.2e-60` |
| 6 | which number "critical t" holds for two tails | the single quantile that appears in F-02 (`t_{1-α/2,ν}`), signed — so it is negative for one tail with `α > 0.5` | no |
| 7 | grid points violating F-05's minimum group sizes | skipped, not fatal: the search effectively starts at the first admissible index | no |
| 8 | a zero effect size in a solving analysis | a validation error. With `δ = 0` the power equals `α` for every design, so no target above `α` is attainable and exhausting the search would be misleading | no (both refused) |
| 9 | the **mode** of F-12's display rounding | half-to-even, i.e. the language default. It applies only to rendered text and never enters a search, so it cannot move an integer sample size | not observable |
| 10 | a name for the F-09 / F-11 behaviour the interface did not expose | implementation-defined; this engine uses `allocation_rule=` and a separate effect-size module | no |
| 11 | an inapplicable design parameter (`predictors` on a one-sample test) | **rejected**, not ignored — a silently ignored parameter is a typo that changes nothing and is never noticed | **yes** |
| 12 | the admissible `ν` domain of the generic t test | any `ν > 0`, including `ν < 1` | no |

Rows 1, 3, 4, 5 and 11 are the ones where two independent readers of v1.0
actually diverged. Reproduce the whole table with

```console
$ python tools/probe_spec_gaps.py
```

**How to read this finding.** It is not evidence about G\*Power and claims
nothing about it. Items 1, 3, 4, 5, 9, 10, 11 and 12 are *this engine's*
documented conventions, chosen so that two implementations of this document
cannot drift apart again; only a GUI probe could say whether G\*Power shares
them. Items 2, 6, 7 and 8 follow from F-02 and F-05 and are not free choices.

---

## 3. Analysis types

All five are functions of `(ν, δ, α, k)` and the chosen solve target.

| Type | Given | Solve for | Method |
|---|---|---|---|
| a priori | `α`, `1-β`, ES (+ ratio) | `N` | smallest grid point with `power ≥ target` (F-05, F-06, F-09) |
| post hoc | `α`, ES, design | `1-β` | direct evaluation of F-02 |
| criterion | `1-β`, ES, design | `α` | bisection on **`log α`** over `[1e-300, 1-1e-15]`; power is increasing in `α` (F-13 item 5) |
| sensitivity | `α`, `1-β`, design | ES | bisection on ES over the closed domain below |
| compromise | `q = β/α`, ES, design | `α`, `1-β` | bisection on the critical value (F-10); uses `\|δ\|` (F-13 item 1) |

Closed effect-size brackets for the sensitivity bisection (F-13 item 4):
`d`, `dz` on `[1e-12, 100]`; `r` on `[1e-12, 1-1e-12]`; `f²` and generic `δ`
on `[1e-12, 1e6]`. If the target power is unattainable at the upper end, the
analysis fails rather than returning the endpoint; if it is already attained at
the lower end, the lower end is returned.

A **zero** effect size is a validation error for the a-priori, criterion and
compromise analyses, and admissible for post hoc (which returns exactly `α`)
and for sensitivity (F-13 item 8). An **inapplicable** design parameter —
`predictors` on a one-sample test, `df` on anything but the generic test — is
rejected, not ignored (F-13 item 11).

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
| critical value `t_{1-α,ν}` | 1e-10 relative | 1.0e-14 |
| `T(x; ν, δ)`, `ν ≥ 1` | 1e-10 absolute | 1.5e-14 |
| `T(x; ν, δ)`, `0 < ν < 1` | 1e-8 absolute | 6.7e-16 |
| size of a two-sided test at `δ = 0` | 1e-9 **relative**, down to `α = 1e-12` | 1.8e-13 |
| quadrature mass closure, `ν ∈ [0.01, 1e6]` | 1e-10 | 9.0e-15 |

Five things decide whether an implementation reaches that table. Each one was
found the hard way, and four of them are **cancellation**: the arithmetic is
textbook, and the error comes entirely from *which algebraically equivalent
form* you evaluate.

1. **Evaluate the noncentral *t* CDF as a mixture, not a series.** With
   `Z ~ N(0,1)` independent of `V ~ χ²_ν` and `T = (Z + δ)/√(V/ν)`,

   ```
   T(x; ν, δ) = E_S[ Φ(x·S - δ) ],   S = sqrt(V/ν)
   ```

   The classical series (AS 243) degrades for large `|δ|`, which is exactly
   where a-priori analyses live.

2. **Integrate in `y = log s`, not in `s`.** With `a = ν/2` the mixing density
   becomes

   ```
   log h(y) = L0 - a·(expm1(2y) - 2y)
   ```

   which puts the mode at `y = 0` for **every** `ν > 0`, turns the `s^(ν-1)`
   endpoint singularity into an entire function, and leaves every term in the
   exponent `O(1)`. In `s` space the singularity is integrable but
   unresolvable by Gauss-Legendre below `ν = 1`: the measured two-sided size
   came out `0.252` where `α` was `0.100`. Not a tolerance failure — a wrong
   answer.

3. **Give `Φ`'s turn its own panel edges.** The integrand is `Φ(x·e^y - δ)`
   times a smooth density. `Φ` is flat outside roughly `±8` and turns sharply
   inside it, and for a large critical value that turn sits far out in the
   density's left tail. If it falls inside one wide panel, Gauss-Legendre
   cannot see it: this alone accounted for `2.8e-4` of error at `ν = 0.05`.
   Add breakpoints where `x·e^y - δ` crosses `0, ±1, ±2, ±4, ±8`.

4. **Compute the survival function directly, never as `1 - CDF`.**
   `P(T > x) = E_S[Φ(δ - x·S)]` is a sum of positive terms. Power *is* this
   quantity (F-02), and it is genuinely small in places the engine reaches —
   a one-tailed test pointed the wrong way has power `7.7e-06`. Subtracting
   from 1 keeps absolute accuracy and throws away relative accuracy: the
   measured size at `α = 1e-12` was off by `6e-04` **relative** that way, and
   by `1.8e-13` this way.

5. **Take the critical value from the tail probability.**
   `t_{1-α/2,ν}` must be obtained as the upper `α/2` quantile, not as the
   `1-α/2` quantile: forming `1 - α/2` destroys every significant digit of a
   small `α` and rounds to exactly `1.0` below about `1e-16`. The criterion
   analysis of §3 reaches `α ~ 1e-60` routinely. Relatedly, the survival
   function must not square its argument when `|t| > 1e120` — it overflows,
   after which everything downstream is silently garbage, and the quantile
   search returns a plausible wrong number instead of failing.

And the one that is not about distributions at all:

6. **Beware cancellation in `log Γ` differences.** `lgamma(a+b) - lgamma(a)`
   subtracts two numbers of size `a·ln a`; at `ν = 5000` that injects `~2e-12`
   of error into an exponent and hence into the result. Rewrite the Stirling
   series so every term is `O(1)`. Likewise never recover `1 - x` by
   subtraction when `x = ν/(ν+t²)` approaches 1 — pass the complement
   `t²/(ν+t²)` explicitly.

---

## 5. Conformance

A conforming implementation must, for the 401 vectors in
`src/gpower_rea/data/public_vectors.csv`:

* reproduce `expected_N` **exactly** (integers), and
* reproduce `expected_power` to `5e-7`.

`gpower selftest` performs exactly this check and exits non-zero on any
disagreement. `gpower batch --expect <column> --min-match <fraction>` performs
it against an arbitrary external vector file — including hidden ones.
