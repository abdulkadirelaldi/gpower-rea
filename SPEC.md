# SPEC.md — Behavioural specification of the G\*Power 3.1 *t tests* family

**Specification version:** v1.3
**Target of analysis:** G\*Power **3.1.9.6** for macOS (notarised build,
`GPowerMac_3.1.9.6.zip`, SHA-256 `841390e0…b3964`), test family **`t tests`**
(all six statistical tests in that menu)
**Status:** v1.2 is the first version written **from observations**. Every
finding below is labelled **`[GÖZLEM]`** and cites the G\*Power readings that
settle it: **373 GUI runs** recorded by `tools/rea_campaign.py`
([`probes/observations/`](probes/observations/)), re-scored against the
engine by `tools/rea_report.py` ([`probes/REA-OBSERVED.md`](probes/REA-OBSERVED.md)).

The observations **refuted** three statements of v1.1, and v1.2 corrects them:

| finding | v1.1 said | G\*Power 3.1.9.6 does |
|---|---|---|
| F-08 | a negative `d` in a one-tailed post-hoc test gives power `< α` | power is computed from `\|δ\|`; the sign only flips `δ` and the critical *t* |
| F-09 | one of two grids (`n1-grid` / `total-grid`) | **neither** — even totals, stopping test on the unrounded split |
| F-06 | "actual power ≥ target" | false for `R ≠ 1`: actual power can be **below** the target |

v1.0 was handed to an independent implementation session; v1.1 added F-13
from that pass ([docs/CLEANROOM-PROTOCOL.md](docs/CLEANROOM-PROTOCOL.md)).
v1.2 added F-14 and F-15 (both observed) and was handed to a second clean-room
session in turn; it reported 19 points v1.2 did not determine. **v1.3 is v1.2
plus [F-16](#f-16--points-spec-v12-left-undetermined-closed-by-observation-where-possible)**,
which closes all 19 — twelve of them by asking G\*Power rather than by choosing.

---

## 0. How to read this document

Each numbered **finding** (`F-nn`) states one piece of observable behaviour,
precisely enough to implement, and links to an **evidence file**
(`docs/EVIDENCE/E-nnn-*.md`) that records how it was established and how to
re-establish it.

Evidence labels follow the course's ledger taxonomy
([LEDGER.md](LEDGER.md)), plus one label for the kind of evidence this
project actually has:

| Label | Meaning |
|---|---|
| `[DOK]` | stated in the G\*Power manual or the papers (Faul et al. 2007, 2009) — §1 only, no credit claimed |
| `[REA]` | proven from the binary (function address or string reference). **This repository contains no `[REA]` row**: no static analysis of the executable was performed in this work |
| `[GÖZLEM]` | proven by a recorded G\*Power 3.1.9.6 GUI reading (black box): the evidence file names the probe rows, the raw readings are in `probes/observations/` and `oracle/`, and `tests/test_gpower_observed.py` fails if the engine stops reproducing them |
| `[TÜRETİLMİŞ + GÖZLEM]` | forced by internal consistency (two menu entries must agree numerically) **and** confirmed by a reading |
| `[GÖZLEM: ÇÜRÜTÜLDÜ → DÜZELTİLDİ]` | an earlier version stated a rule; G\*Power was observed to do something else; the finding states the observed rule and keeps the refuted one |
| `[AJAN]` | the agent's inference, no evidence — used only in [HALLUCINATIONS.md](HALLUCINATIONS.md) and LEDGER.md, never as a finding |
| `[SPEC-CLOSURE]` | not a claim about G\*Power: a point where this document was too weak to determine an implementation (F-13, F-16) |

> **Why "not in the manual" matters.** Everything in §2 labelled
> `[GÖZLEM]` describes behaviour the G\*Power documentation
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
`[TÜRETİLMİŞ + GÖZLEM]` · evidence [E-001](docs/EVIDENCE/E-001-common-noncentral-t-model.md) · probe `P-01-a` + 373 runs

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
`[GÖZLEM]` · evidence [E-002](docs/EVIDENCE/E-002-two-sided-far-tail.md) · probes `P-02-a…d`

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
`[TÜRETİLMİŞ + GÖZLEM]` · evidence [E-003](docs/EVIDENCE/E-003-paired-and-one-sample.md) · probes `P-03-a,b`

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
`[TÜRETİLMİŞ + GÖZLEM]` · evidence [E-004](docs/EVIDENCE/E-004-point-biserial-ncp.md) · probes `P-04-a…e`

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
`[GÖZLEM]` · evidence [E-005](docs/EVIDENCE/E-005-balanced-search-grid.md) · probes `P-05-a…d`, sweep `S-*`

For *Means: Difference between two independent means (two groups)*:

```
ν = n₁ + n₂ - 2
δ = ES · sqrt( n₁·n₂ / (n₁ + n₂) )
```

With an allocation ratio of 1, the a-priori search enumerates
`n₁ = 2, 3, 4, …` and sets `n₂ = n₁` — equivalently, it enumerates **even**
totals only. It does **not** try an odd total. Observable consequence:

> **A balanced a-priori two-group t test never reports an odd total sample
> size**, even where an odd split `(n, n+1)` already reaches the target.

Observed: `P-05-a` reports `N = 352` where `(175, 176)` already has power
`0.80026 ≥ 0.80`; `P-05-b` reports `242` where `(120, 121)` has `0.90095`.
All 119 observed a-priori two-group results have an even total.

**This is the `R = 1` case of a more general rule** — F-09 shows that G\*Power
searches even totals at *every* allocation ratio.

**How often it matters.** Over a 474-setting sweep (`d ∈ [0.100, 1.200]` ×
power `{.80, .90, .95}`) the odd split already suffices in **50.2 %** of
settings, so an implementation that searches total `N` is off by one about
half the time (measured with `statsmodels`, without this engine's search; see
E-005).

Pinned by `tests/test_engine_invariants.py::test_balanced_a_priori_never_returns_an_odd_total`
and by every `P-05-*` row in `tests/test_gpower_observed.py`.

Minimum admissible design: `n₁ ≥ 2` and `n₂ ≥ 2`.

### F-06 — Minimality, and "Actual power" is recomputed
`[GÖZLEM]`, one clause `REFUTED → CORRECTED` · evidence [E-006](docs/EVIDENCE/E-006-minimality-and-actual-power.md) · probes `P-06-a,b`, `S-019`

An a-priori analysis returns the **first** design on the search grid of
F-05/F-09 whose stopping test passes — the comparison is `≥`, not `>`.

The reported power is then **recomputed at the integer design actually
reported** and printed as *Actual power*; it is not the requested value echoed
back (`P-06-a`: target `0.95`, printed `0.9501287`).

**Refuted clause of v1.1.** v1.1 said actual power therefore exceeds the
target. That holds for `R = 1` only. For `R ≠ 1` the stopping test is made on
the *unrounded* split (F-09) and the reported design is the *rounded* one, so
the printed actual power can be **below the requested power**:

```
two independent means, d = 0.5, α = 0.05, two tails, R = 1.5, power = 0.9495
  ->  n₁ = 87, n₂ = 131, N = 218,  Actual power = 0.9494095  (< 0.9495)      [S-019]
```

A conforming implementation reports the integer design and its recomputed
power, even when that power is below target; it must not "repair" the design.

Worked instance (`P-01-a`, `P-06-a`, all seven printed decimals identical):

```
two independent means, d = 0.5, α = 0.05, power = 0.95, two tails, ratio = 1
  ->  n₁ = n₂ = 105,  N = 210,  ν = 208,  δ = 3.6228442,  actual power = 0.9501287
```

### F-07 — Regression coefficient: `ν = N - p - 1`, `δ = √(f²·N)`
`[TÜRETİLMİŞ + GÖZLEM]` · evidence [E-007](docs/EVIDENCE/E-007-regression-coefficient.md) · probes `P-07-a…d`

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
`[GÖZLEM: ÇÜRÜTÜLDÜ → DÜZELTİLDİ]` · evidence [E-008](docs/EVIDENCE/E-008-effect-size-sign.md) · probes `P-08-a…c`, `N-01…N-12`

**Observed rule.** The sign of the effect size is the *direction* of the
alternative. G\*Power computes every probability from `|δ|`, and prints `δ`
and the critical *t* with the sign of the effect:

```
power(ES)      = power(|ES|)                        all five analyses
δ printed      = sign(ES) · |δ|
critical t     = sign(ES) · t_crit                  a priori, post hoc, compromise
critical t     =          + t_crit                  criterion  (sign NOT applied)
```

| probe | input | G\*Power printed | v1.1 predicted |
|---|---|---|---|
| `P-08-a` | one sample, `d = -0.5`, `N = 30`, one tail, post hoc | `δ = -2.7386128`, `t = -1.6991270`, power **`0.8482542`** | power `7.733e-06` |
| `N-05` | generic, `δ = -2.5`, `ν = 30`, one tail | `t = -1.6972609`, power `0.7876008` | `2.15e-05` |
| `N-01` | one sample, criterion, `d = -0.5` | `δ = -2.7386128`, `t = +1.8880297` | — |
| `N-03` | compromise, `d = -0.5` | `δ = -2.2360680`, `t = -1.1216208` | — |

The criterion analysis is the one place the sign does not reach the critical
value — an internal inconsistency of G\*Power, reproduced deliberately.

**Point biserial is the exception.** Its effect-size field is labelled `|ρ|`
and the label is enforced: a negative `r` is refused with *"Effect size r is
outside the admissible range (0, 0.999999)"* (`N-07`). `f²` is a squared
quantity and is likewise never negative (F-13 item 2).

The engine records `warnings[]` whenever a negative effect size was supplied.

### F-09 — Allocation-ratio rounding
`[GÖZLEM: ÇÜRÜTÜLDÜ → DÜZELTİLDİ]` · evidence [E-009](docs/EVIDENCE/E-009-allocation-rounding.md) · probes `P-09-a…d`, `A-000…A-047`, `S-000…S-040`

With allocation ratio `R = N₂/N₁`, the a-priori search is:

```
for N = 4, 6, 8, …                       (even totals only, at every R)
    m₁ = N / (1+R),  m₂ = N·R / (1+R)     (unrounded group sizes)
    ν  = N - 2
    δ  = ES · sqrt(m₁·m₂ / N)
    stop at the first N with power(ν, δ) ≥ target

report  n₁ = round_half_up(N / (1+R)),  n₂ = N - n₁
        Actual power recomputed at (n₁, n₂)                (F-06)
```

This rule is called **`even-total`** and is the engine default. It reproduces
**all 119** recorded a-priori two-group results of G\*Power (108 of them
unbalanced) in `n₁`, `n₂` **and** *Actual power* to seven decimals; across all
six tests, **225/225** a-priori totals with `N ≤ 1e7` are exact.

**How it was found.** v1.1 offered two candidates. Observation refuted both:

| probe | `R` | G\*Power | `n1-grid` | `total-grid` |
|---|---|---|---|---|
| `P-09-b` | 1.5 | `88 / 132` (220) | `88 / 132` ✔ | `88 / 131` ✘ |
| `P-09-c` | 2.0 | `79 / 157` (236) | `79 / 158` ✘ | `79 / 157` ✔ |
| `P-09-d` | 3.0 | `70 / 210` (280) | `70 / 210` ✔ | `70 / 208` ✘ |

Over the 48-row ratio sweep `A-*`, `n1-grid` matched 19 and `total-grid` 21.
Every displayed split was the total-grid split of its own total, so the
question became *which N*. A fine power sweep at `R = 1.5` (`S-000…S-040`)
answered it: the reported totals run `208, 210, 212, …, 232` — **always even**
— and at target `0.946` G\*Power reports `N = 216` although the rounded split
of `214`, `(86, 128)`, already has power `0.94628`. The stopping test is
therefore not made on the reported split; on the unrounded split it is, for all
119 rows. Six alternative rules (each group rounded/floored/ceiled separately,
continuous total, rounded check on even totals, …) were scored against the same
rows; the best of them fits 96 of 119 (`tools/fit_allocation.py`, E-009).

Rounding of the reported split is **half-away-from-zero**: `A-022`
(`R = 3`, `N = 170`, `N/(1+R) = 42.5`) prints `n₁ = 43`.

The refuted rules remain available as `--allocation-rule n1-grid` and
`--allocation-rule total-grid`, for reproducing v1.1 output only.

### F-10 — Compromise analysis is defined on the critical value
`[TÜRETİLMİŞ + GÖZLEM]` · evidence [E-010](docs/EVIDENCE/E-010-compromise-analysis.md) · probes `P-10-a…c`, `N-03,04`

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
`[AÇIK]` · evidence [E-011](docs/EVIDENCE/E-011-effect-size-pooling.md) · probes `P-11-a…c`

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
`[GÖZLEM]` · evidence [E-012](docs/EVIDENCE/E-012-boundary-and-precision.md) · probe `P-12-a`

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
| 1 | which sign rule the **compromise** analysis follows — F-08 named only three solving analyses | it uses `\|δ\|` and emits the F-08 warning. **v1.2: observed** (`N-03`, `N-04`): G\*Power prints `α = 0.1327324` for `d = -0.5`, the `\|δ\|` answer | **yes** — `α = 0.133` vs `0.867` |
| 2 | whether a negative `f²` is admissible | **no**: `f²` is a squared quantity and `δ = √(f²·N)` has no real value; reject it | no (both refused) |
| 3 | which effect size the result reports once `\|ES\|` is substituted | the **input as supplied**, signed; the value actually used is recoverable from `noncentrality`, and `warnings[]` flags the substitution. For the sensitivity analysis the field carries the answer, since there is no input to echo | **yes** |
| 4 | the numerical endpoints of the sensitivity bisection | closed brackets: `d`, `dz` on `[1e-12, 100]`; `r` on `[1e-12, 1-1e-12]` (**v1.2:** `[1e-12, 0.999999]`, the GUI's bound, F-15); `f²` and generic `δ` on `[1e-12, 1e6]` | **yes** — `1e-9` vs `1e-12` |
| 5 | the `α` bracket of the criterion analysis | bisect on **`log α`** over `[1e-300, 1-1e-15]`, and report the solution however small | **yes** — `1e-12` vs `4.2e-60` |
| 6 | which number "critical t" holds for two tails | the single quantile that appears in F-02 (`t_{1-α/2,ν}`), signed — so it is negative for one tail with `α > 0.5`. **v1.2:** multiplied by `sign(ES)` except in the criterion analysis (F-08, observed) | no |
| 7 | grid points violating F-05's minimum group sizes | skipped, not fatal: the search effectively starts at the first admissible index | no |
| 8 | a zero effect size in a solving analysis | a validation error (**v1.2:** for a priori, anything below `\|ES\| = 1e-5`, as observed — F-15). With `δ = 0` the power equals `α` for every design, so no target above `α` is attainable and exhausting the search would be misleading | no (both refused) |
| 9 | the **mode** of F-12's display rounding | half-to-even, i.e. the language default. It applies only to rendered text and never enters a search, so it cannot move an integer sample size | not observable |
| 10 | a name for the F-09 / F-11 behaviour the interface did not expose | implementation-defined; this engine uses `allocation_rule=` and a separate effect-size module | no |
| 11 | an inapplicable design parameter (`predictors` on a one-sample test) | **rejected**, not ignored — a silently ignored parameter is a typo that changes nothing and is never noticed | **yes** |
| 12 | the admissible `ν` domain of the generic t test | any `ν > 0`, including `ν < 1` | no |

Rows 1, 3, 4, 5 and 11 are the ones where two independent readers of v1.0
actually diverged. Reproduce the whole table with

```console
$ python tools/probe_spec_gaps.py
```

**How to read this finding.** It is not evidence about G\*Power. Items 3, 4,
9, 10 and 11 are *this engine's* documented conventions, chosen so that two
implementations of this document cannot drift apart again. Items 1 and 6 have
since been **observed** (v1.2); item 5's tiny answers are where G\*Power itself
becomes inexact (F-14); item 8 and the point-biserial domain are settled by
F-15. Items 2 and 7 follow from F-02 and F-05 and are not free choices.

### F-14 — G\*Power's own answers become inexact below `α ≈ 1e-9` and above `N ≈ 1e7`
`[GÖZLEM]` · evidence [E-014](docs/EVIDENCE/E-014-far-tail-precision.md) · grid rows `G-003`, `G-007`, `G-014`, `G-168`, `G-187`, `G-205`, `G-230`

In the criterion and compromise analyses the answer `α` can be astronomically
small (F-13 item 5). There G\*Power 3.1.9.6 stops being exact:

| row | analysis | G\*Power prints | exact (50-digit `mpmath`) | engine |
|---|---|---|---|---|
| `G-003` | criterion | `α = 1.32816e-12`, `t = 8.1198649` | `α = 1.328116e-12`, `t = 8.1198547` | exact |
| `G-007` | criterion | `α = 1.385003e-13`, `t = 8.0263534` | `α = 1.384721e-13`, `t = 8.0263188` | exact |
| `G-014` | criterion | **"Internal Math Error! GPower was not able to compute the results."** | `α = 6.54e-19` | exact |

At G\*Power's own `α` the power is `0.8000017` (G-003) and `0.8000093`
(G-007), not the requested `0.8`, and its printed critical *t* does not match
its own `α` either — the error is in its far-tail central-*t* quantile, not in
the root finding. Between `1e-9` and `1e-11` the disagreement is in the 7th
significant digit (`G-168`, `G-187`, `G-205`, `G-230`).

**The same happens at huge `N`.** For a very small effect the a-priori `N`
runs into the billions (F-15), where power moves by less than `1e-8` per
participant. G\*Power's answer there is not the exact one either:

| row | input | G\*Power `N` | exact `N` (40-digit `mpmath`) | engine |
|---|---|---|---|---|
| `D-44` | two groups, `d = 0.001`, `R = 2`, power `.8` | `35 319 874` — exact power there `0.79999999764`, **below target** | `35 319 876` | `35 319 876` |
| `D-43` | one sample, `d = 1e-4`, power `.95` | `1 299 470 953` | `1 299 470 912` | `1 299 470 911` |
| `D-31` | one sample, `d = 1e-5`, power `.8` | `78 488 272 181`, printed actual power `0.8000265` | — | `78 488 605 095` |

**Requirement.** An implementation reports the exact answer as nearly as it
can and flags the region: the engine adds a `warnings[]` entry whenever a
criterion or compromise result has `α < 1e-9`, or an a-priori result has
`N > 1e7`. It does not imitate the error. Outside these two regions every
observed answer is reproduced in every printed digit.

### F-15 — The input domain G\*Power accepts
`[GÖZLEM]` · evidence [E-015](docs/EVIDENCE/E-015-input-domain.md) · probes `D-01…D-46`, `N-07`

The manual gives no admissible ranges. G\*Power 3.1.9.6 enforces these, each
with an *"Input error!"* dialog quoted in E-015:

| input | admissible | observed edge |
|---|---|---|
| point biserial `r` | `0 ≤ r ≤ 0.999999` | `0.999999` accepted, `0.9999995` refused (`D-01`, `D-02`); negative refused (`N-07`); **`r = 0` accepted** despite the message's "(0, …" (`X-G2-06`) |
| `f²` | `(-20, 20)` by the range check; a negative value then fails with *"Internal Math Error"*, so only `0 ≤ f² < 20` yields a result | `19.99` accepted, `50` refused (`D-39`, `D-30`, `D-37`) |
| a-priori effect size | `\|ES\| ≥ 0.00001` for `d`, `dz`, `f²`; for `r` the floor is `1e-6` (F-16) | `1e-5` accepted, `9e-6` refused (`D-31`, `D-40`); `f² = 5e-6` refused (`X-G2-08b`); `r = 5e-6` accepted, `N = 3.1e11` (`X-G2-08a`) |
| allocation ratio `N₂/N₁` | `[0.01, 100]` | both ends accepted, `0.001` and `1000` refused (`X-G2-11*`) |
| target power (a priori, sensitivity) | `power ≥ α` | `power = α` accepted (`D-32`), `power < α` refused (`D-13`, `D-20`) |
| `β/α` ratio | `[0.01, 100]` | both ends accepted (`D-33`, `D-34`), `1e-4` refused (`D-19`) |
| explicit design (post hoc, criterion, sensitivity, compromise) | total `N ≥ 3`, each group `≥ 1`; regression `N ≥ p + 2`, `p ≥ 1` | `N = 2` refused for one sample and matched pairs although `ν = 1` (`D-08`, `D-41`); `n₁ = 1, n₂ = 2` accepted (`D-24`); `n₁ = 0` refused (`X-G2-02`); `p = 0` refused (`X-G2-17`) |
| a-priori result | as small as `ν = 1` | matched pairs `d = 20` returns **`N = 2`** (`D-23`) — a design G\*Power refuses as input |
| generic `ν` | any `ν > 0` | `ν = 0.5` computed (`D-10`) |
| a-priori `N` | up to `2⁶³ - 2` | `N = 78 488 272 181` returned (`D-31`) |

Two of these are internal inconsistencies of G\*Power worth knowing: the
a-priori analysis can return a design (`N = 2`) that the post-hoc analysis
then refuses, and the `f²` range admits values the computation cannot handle.

**Requirement.** Refuse exactly what G\*Power refuses, with a message that
names the rule; accept everything it accepts.

### F-16 — Points SPEC v1.2 left undetermined, closed by observation where possible
`[SPEC-CLOSURE]`, twelve rows `[GÖZLEM]` · evidence [E-016](docs/EVIDENCE/E-016-cleanroom-v12-gaps.md) · probes `X-G2-*`, `D-*`

The second clean-room session implemented v1.2 from this document alone and
reported 19 gaps ([cleanroom/SPEC-GAPS-v1.2.md](cleanroom/SPEC-GAPS-v1.2.md)).
Unlike F-13, most of them are questions about G\*Power, so they were put to
G\*Power:

| gap | v1.2 did not determine | v1.3 says | settled by |
|---|---|---|---|
| G2-01 | search cap: INTERFACE's `1e7` vs §3's `2⁶³ − 2` | `2⁶³ − 2` on the total; INTERFACE.md corrected | **observed** (`D-31`, `N = 7.8e10`) |
| G2-02 | smallest explicit two-group design | each group `≥ 1`, total `≥ 3` (F-05's `≥ 2` is not a limit at all) | **observed** (`D-24`, `X-G2-02`) |
| G2-03 | F-03's "`N ≥ 2`" vs F-15 | explicit designs `N ≥ 3`; the a-priori search may return `N = 2` | **observed** (`D-08`, `D-23`) |
| G2-04 | does even-total skip a split with a group of 1? | **no** — `R = 3`, `d = 8` reports `1 / 3`; F-13 item 7's skip does not apply to even-total | **observed** (`X-G2-04`, `D-28`) |
| G2-05 | which `δ` an unbalanced a priori prints | the one at the **reported** split (`S-019`: `3.6152392`) | **observed** (all `S-*`, `A-*`) |
| G2-06 | point biserial `r = 0` | admissible; post hoc returns `α` | **observed** (`X-G2-06`) |
| G2-07 | sensitivity answer above the `f²` input bound | allowed: the bracket stays `[1e-12, 1e6]` | **observed** (`X-G2-07`: `f² = 672256.1`) |
| G2-08 | does `\|ES\| ≥ 1e-5` cover `r` and `f²`? | `f²` yes, `r` no | **observed** (`X-G2-08a,b`) |
| G2-09 | the sign of a zero effect | `+`: the critical value prints positive | **observed** (`D-06`, `N-11`) |
| G2-10 | F-14's `N > 1e7`: total or per group? | total | convention (warning only) |
| G2-11 | allocation-ratio domain | `[0.01, 100]` | **observed** (`X-G2-11a–d`) |
| G2-12 | allocation parameters on a single-group test | rejected when not the default (F-13 item 11) | convention |
| G2-13 | size-parameter spellings per test | implementation-defined (INTERFACE.md) | convention |
| G2-14 | `N/(1+R)` in binary or decimal arithmetic | **binary double** — `d = 1.11`, `R = 7.8`: `66/8.8` evaluates to `7.4999…`, G\*Power prints `7 / 59` | **observed** (`X-G2-14`) |
| G2-15 | resolution of the search beyond `2⁵³` | doubles; the F-14 warning applies | convention |
| G2-16 | "four-term" Cornish–Fisher; which `z` | `z + g₁/ν + … + g₄/ν⁴`, `z` of the tail actually inverted (`α/2` for two tails); §4's list is renumbered | convention (no observable effect) |
| G2-17 | `predictors = 0` | refused; `p ≥ 1` | **observed** (`X-G2-17`) |
| G2-18 | a negative generic `δ` and the F-08 warning | warned, like any negative effect | convention |
| G2-19 | shape of `warnings` | always a list of strings, one per condition | convention |

Session B then implemented v1.3 and reported four more points
([cleanroom/SPEC-GAPS-v1.3.md](cleanroom/SPEC-GAPS-v1.3.md)); the two that are
questions about G\*Power were probed:

| gap | question | G\*Power 3.1.9.6 | settled by |
|---|---|---|---|
| G3-01 | can even-total report an **empty** group? | **yes** — `d = 20`, `R = 100` prints `n₁ = 0`, `n₂ = 6`, `δ = 0`, *Actual power* **`0.0500000`** (= `α`, below the `0.8` asked for); `R = 0.01` prints `6 / 0`. A G\*Power defect, reproduced rather than repaired | **observed** (`X-G3-01a,b`) |
| G3-03 | point biserial, a priori, `r = 0` | refused: *"admissible range (1e-06, 0.999999)"* — the a-priori floor for `r` is `1e-6`, not F-15's `1e-5` | **observed** (`X-G3-03`) |
| G3-02 | minimum group size of the refuted v1.1 rules | unchanged (`≥ 2`); they exist only to reproduce v1.1 output | convention |
| G3-04 | stale wording in F-03/F-04/F-05/F-08 | F-15 and F-16 take precedence where they differ | editorial |

G3-01 is the second time the clean room was right where the shipped engine was
not: the engine clamped each group to at least 1 and printed `1 / 5` with
power `1.0`, which is not what G\*Power does.

Two implementations of v1.2 disagreed on one recorded G\*Power result, `D-28`
(`d = 20`, `R = 3`: G\*Power `1 / 3`, the clean room `2 / 4`). That was G2-04:
the text allowed both readings. The observation decides it.


---

## 3. Analysis types

All five are functions of `(ν, δ, α, k)` and the chosen solve target.

| Type | Given | Solve for | Method |
|---|---|---|---|
| a priori | `α`, `1-β`, ES (+ ratio) | `N` | first grid point whose stopping test passes (F-05, F-06, F-09); searched up to `2⁶³ - 2` |
| post hoc | `α`, ES, design | `1-β` | direct evaluation of F-02 |
| criterion | `1-β`, ES, design | `α` | bisection on **`log α`** over `[1e-300, 1-1e-15]`; power is increasing in `α` (F-13 item 5) |
| sensitivity | `α`, `1-β`, design | ES | bisection on ES over the closed domain below |
| compromise | `q = β/α`, ES, design | `α`, `1-β` | bisection on the critical value (F-10); uses `\|δ\|` (F-13 item 1) |

Closed effect-size brackets for the sensitivity bisection (F-13 item 4):
`d`, `dz` on `[1e-12, 100]`; `r` on `[1e-12, 0.999999]` (v1.2: the GUI's own
bound, F-15); `f²` and generic `δ` on `[1e-12, 1e6]`. If the target power is unattainable at the upper end, the
analysis fails rather than returning the endpoint; if it is already attained at
the lower end, the lower end is returned.

A **zero** effect size is a validation error for the a-priori, criterion and
compromise analyses, and admissible for post hoc (which returns exactly `α`)
and for sensitivity (F-13 item 8). The full observed input domain — including
`|ES| ≥ 1e-5` for a priori, `power ≥ α`, `q ∈ [0.01, 100]` and `N ≥ 3` for an
explicit design — is F-15. An **inapplicable** design parameter —
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
| critical value `t_{1-α,ν}`, `ν ≤ 1e5` | 1e-10 relative | 1.0e-14 |
| critical value `t_{1-α,ν}`, `1e5 < ν ≤ 1e11` | 1e-12 relative | 4e-16 |
| `T(x; ν, δ)`, `ν ≥ 1` | 1e-10 absolute | 1.5e-14 |
| `T(x; ν, δ)`, `0 < ν < 1` | 1e-8 absolute | 6.7e-16 |
| size of a two-sided test at `δ = 0` | 1e-9 **relative**, down to `α = 1e-12` | 1.8e-13 |
| quadrature mass closure, `ν ∈ [0.01, 1e6]` | 1e-10 | 9.0e-15 |

Six things decide whether an implementation reaches that table. Each one was
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

6. **For a very large `ν`, stop refining the quantile.** An a-priori search
   for `d = 1e-5` reaches `N = 7.8e10` (F-15). There `x = ν/(ν+t²)` is within
   `1e-11` of 1 and the incomplete beta behind `T(x; ν)` loses `log₁₀ ν`
   digits; a Newton refinement on it drags the critical value `2.7e-6`
   relative off at `ν = 1e11`. The four-term Cornish–Fisher series
   (Abramowitz & Stegun 26.7.5) is exact to rounding once `ν ≥ 1e5` and
   `ν ≥ 1000 z²`, and should be returned as is.

And the one that is not about distributions at all:

7. **Beware cancellation in `log Γ` differences.** `lgamma(a+b) - lgamma(a)`
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

Against the real program, the reference implementation is held to more:
every number G\*Power 3.1.9.6 printed for every recorded input in
`probes/observations/`, at G\*Power's own printed precision, outside the two
regions of F-14 (`tests/test_gpower_observed.py`).

`gpower selftest` performs exactly this check and exits non-zero on any
disagreement. `gpower batch --expect <column> --min-match <fraction>` performs
it against an arbitrary external vector file — including hidden ones.

---

## 6. Acceptance criteria (Gherkin) — `t2-indep`

Executable: `tests/test_gherkin_spec.py` parses every `Examples:` table below
and runs it through `gpower-clone`. Every expected value is a G\*Power 3.1.9.6
reading from [`oracle/gpower_t2_indep.csv`](oracle/gpower_t2_indep.csv), not an
engine output. Integers must match exactly; `actual_power`, `critical` and
`ncp` to the 4 decimals of the CLI contract.

```gherkin
Feature: t2-indep sample size and power, as G*Power 3.1.9.6 computes them

  Background:
    Given the command "gpower-clone --test t2-indep"
    And every answer is one line of JSON on stdout

  # F-05, F-06, F-09: even totals, unrounded stopping test, rounded split
  Scenario Outline: a priori sample size
    When I run "--mode a-priori --tails <tails> --d <d> --alpha <alpha> --power <power> --ratio <ratio>"
    Then the exit code is 0
    And "n1" is <n1> and "n2" is <n2> and "n_total" is <n_total> exactly
    And "actual_power" is <actual_power> and "critical" is <critical> and "df" is <df> and "ncp" is <ncp>

    Examples:
      | id | tails | d | alpha | power | ratio | n1 | n2 | n_total | actual_power | critical | df | ncp |
      | P-01-a | 2 | 0.5 | 0.05 | 0.95 | 1 | 105 | 105 | 210 | 0.9501 | 1.9714 | 208 | 3.6228 |
      | P-05-a | 2 | 0.3 | 0.05 | 0.8 | 1 | 176 | 176 | 352 | 0.8014 | 1.9668 | 350 | 2.8142 |
      | P-05-b | 2 | 0.42 | 0.05 | 0.9 | 1 | 121 | 121 | 242 | 0.9021 | 1.9699 | 240 | 3.2668 |
      | P-05-d | 2 | 0.62 | 0.05 | 0.85 | 1 | 48 | 48 | 96 | 0.8523 | 1.9855 | 94 | 3.0374 |
      | P-09-a | 2 | 0.5 | 0.05 | 0.95 | 0.5 | 157 | 79 | 236 | 0.9505 | 1.9702 | 234 | 3.6247 |
      | P-09-b | 2 | 0.5 | 0.05 | 0.95 | 1.5 | 88 | 132 | 220 | 0.9513 | 1.9709 | 218 | 3.6332 |
      | P-09-c | 2 | 0.5 | 0.05 | 0.95 | 2.0 | 79 | 157 | 236 | 0.9505 | 1.9702 | 234 | 3.6247 |
      | P-09-d | 2 | 0.5 | 0.05 | 0.95 | 3.0 | 70 | 210 | 280 | 0.9506 | 1.9685 | 278 | 3.6228 |
      | A-002 | 2 | 0.3 | 0.05 | 0.8 | 1.25 | 158 | 198 | 356 | 0.8009 | 1.9667 | 354 | 2.8123 |
      | A-007 | 2 | 0.3 | 0.05 | 0.8 | 4 | 110 | 438 | 548 | 0.8018 | 1.9643 | 546 | 2.8130 |
      | A-022 | 2 | 0.5 | 0.05 | 0.8 | 3 | 43 | 127 | 170 | 0.8045 | 1.9742 | 168 | 2.8339 |
      | A-033 | 2 | 0.8 | 0.05 | 0.8 | 0.5 | 39 | 19 | 58 | 0.8024 | 2.0032 | 56 | 2.8595 |
      | S-019 | 2 | 0.5 | 0.05 | 0.9495 | 1.5 | 87 | 131 | 218 | 0.9494 | 1.9710 | 216 | 3.6152 |
      | N-10 | 1 | -0.5 | 0.05 | 0.8 | 2 | 38 | 76 | 114 | 0.8041 | -1.6586 | 112 | -2.5166 |
      | D-14 | 2 | 0.8 | 0.05 | 0.8 | 0.05 | 261 | 13 | 274 | 0.8010 | 1.9687 | 272 | 2.8152 |
      | D-15 | 2 | 0.8 | 0.05 | 0.8 | 20 | 13 | 261 | 274 | 0.8010 | 1.9687 | 272 | 2.8152 |
      | D-22 | 1 | 0.5 | 0.05 | 0.8 | 1.5 | 42 | 64 | 106 | 0.8042 | 1.6596 | 104 | 2.5179 |
      | D-27 | 2 | 20 | 0.05 | 0.8 | 1 | 2 | 2 | 4 | 1.0000 | 4.3027 | 2 | 20.0000 |
      | D-28 | 2 | 20 | 0.05 | 0.8 | 3 | 1 | 3 | 4 | 1.0000 | 4.3027 | 2 | 17.3205 |
      | X-G2-04 | 2 | 8 | 0.05 | 0.8 | 3 | 1 | 3 | 4 | 0.9085 | 4.3027 | 2 | 6.9282 |
      | X-G2-14 | 2 | 1.11 | 0.05 | 0.8 | 7.8 | 7 | 59 | 66 | 0.7808 | 1.9977 | 64 | 2.7767 |
      | X-G3-01a | 2 | 20 | 0.05 | 0.8 | 100 | 0 | 6 | 6 | 0.0500 | 2.7764 | 4 | 0.0000 |
      | X-G3-01b | 2 | 20 | 0.05 | 0.8 | 0.01 | 6 | 0 | 6 | 0.0500 | 2.7764 | 4 | 0.0000 |

  # F-02 (far tail kept), F-08 (sign is a direction)
  Scenario Outline: post hoc power
    When I run "--mode post-hoc --tails <tails> --d <d> --alpha <alpha> --n1 <n1> --n2 <n2>"
    Then the exit code is 0
    And "actual_power" is <actual_power> and "critical" is <critical> and "df" is <df> and "ncp" is <ncp>

    Examples:
      | id | tails | d | alpha | n1 | n2 | actual_power | critical | df | ncp |
      | D-06 | 2 | 0 | 0.05 | 20 | 20 | 0.0500 | 2.0244 | 38 | 0.0000 |
      | D-24 | 2 | 0.5 | 0.05 | 1 | 2 | 0.0541 | 12.7062 | 1 | 0.4082 |
      | G-108 | 1 | 0.41 | 0.05 | 103 | 13 | 0.3974 | 1.6583 | 114 | 1.3930 |
      | G-144 | 1 | 0.21 | 0.025 | 12 | 16 | 0.0763 | 2.0555 | 26 | 0.5499 |
      | G-150 | 2 | 0.2 | 0.05 | 114 | 45 | 0.2040 | 1.9752 | 157 | 1.1360 |
      | G-180 | 1 | 0.49 | 0.025 | 98 | 124 | 0.9505 | 1.9708 | 220 | 3.6253 |
      | G-192 | 1 | 0.58 | 0.1 | 25 | 25 | 0.7738 | 1.2994 | 48 | 2.0506 |
      | G-204 | 2 | 0.22 | 0.1 | 26 | 96 | 0.2603 | 1.6577 | 120 | 0.9951 |

  # F-15, F-16: refuse exactly what G*Power refuses
  Scenario Outline: invalid input
    When I run "<args>"
    Then the exit code is not 0
    And the output is {"error": "<some text>"}

    Examples:
      | case | args |
      | ratio below 0.01 (X-G2-11a) | --mode a-priori --tails 2 --d 0.5 --alpha 0.05 --power 0.8 --ratio 0.001 |
      | ratio above 100 (X-G2-11b) | --mode a-priori --tails 2 --d 0.5 --alpha 0.05 --power 0.8 --ratio 1000 |
      | power below alpha (D-13) | --mode a-priori --tails 2 --d 0.5 --alpha 0.05 --power 0.04 --ratio 1 |
      | effect below 1e-5 a priori (D-40) | --mode a-priori --tails 2 --d 0.000009 --alpha 0.05 --power 0.8 --ratio 1 |
      | empty group post hoc (X-G2-02) | --mode post-hoc --tails 2 --d 0.5 --alpha 0.05 --n1 0 --n2 3 |
      | total below 3 post hoc (D-17) | --mode post-hoc --tails 2 --d 0.5 --alpha 0.05 --n1 1 --n2 1 |
      | tails not 1 or 2 | --mode a-priori --tails 3 --d 0.5 --alpha 0.05 --power 0.8 --ratio 1 |
      | unknown mode | --mode sideways --tails 2 --d 0.5 --alpha 0.05 --power 0.8 |

  # F-06: the reported design is never "repaired"
  Scenario: actual power may be below the requested power
    When I run "--mode a-priori --tails 2 --d 0.5 --alpha 0.05 --power 0.9495 --ratio 1.5"
    Then "n1" is 87 and "n2" is 131
    And "actual_power" is 0.9494 which is below 0.9495

  Scenario: a priori may report an empty group, like G*Power (X-G3-01a)
    When I run "--mode a-priori --tails 2 --d 20 --alpha 0.05 --power 0.8 --ratio 100"
    Then "n1" is 0 and "n2" is 6 and "actual_power" is 0.05
```
