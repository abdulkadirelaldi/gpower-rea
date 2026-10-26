# SPEC-GAPS.md

Points on which SPEC.md v1.0 (together with INTERFACE.md) does not determine
the behaviour of the engine.  For each: what is undetermined, what this
implementation does instead, and what a reader would have to add to SPEC.md to
close it.

Nothing here was filled from background knowledge about G\*Power or about power
analysis conventions; every resolution is either forced by another part of
SPEC.md or is an arbitrary, documented choice.

---

## G-01 — Which effect-size sign rule the *compromise* analysis follows

**Undetermined.** F-08 splits the analyses into two groups: post hoc uses the
**signed** `δ`, and "the three *solving* analyses (a priori, criterion,
sensitivity)" use `|δ|`.  Compromise is the fifth analysis type (§3, F-10) and
appears in neither list.  F-10's formulas are written in terms of `δ` as
supplied, which suggests signed; §3 describes compromise as solving for `α`
and `1-β`, which suggests it belongs to the `|δ|` group.

**What this implementation does.** Compromise uses the **signed** `δ`, on the
grounds that F-08 enumerates exactly three analyses and compromise is not one
of them, and that F-10 writes `β(c) = T(c; ν, δ)` with no absolute value.  No
sign warning is emitted for compromise.

**Observability.** Only for `k = 1`.  For `k = 2` both the power expression of
F-02 and the `β` expression of F-10 are even in `δ`, so the choice is
invisible.  For `k = 1` with a negative effect size the signed rule returns a
critical value far to the left, hence `α` close to 1 and power below `α`.

**To close.** Add one clause to F-08 naming compromise explicitly, e.g.
"compromise, like post hoc, is computed from the signed `δ`" (or "like the
three solving analyses, from `|δ|`").

---

## G-02 — A negative `f²` for the regression coefficient test

**Undetermined.** F-08 states that a negative effect size is a direction, not
an error.  F-07 defines `δ = sqrt(f²·N)`, which has no real value for
`f² < 0`, and `f²` is by construction a squared quantity.  SPEC.md does not say
whether a negative `f²` is rejected, clamped, or read as
`δ = -sqrt(|f²|·N)`.

**What this implementation does.** `ValueError` for `f² < 0`
(`"f2 is a squared effect size and must be >= 0"`).  The F-08 sign rule is
therefore applied to `d`, `dz`, `r` and the generic `δ`, but not to `f²`.

**To close.** Add a sentence to F-07 or F-08 stating the domain of `f²` and, if
negative values are admitted, the `δ` they map to.

---

## G-03 — Which effect size the result reports once `|δ|` has been substituted

**Undetermined.** F-08 says the solving analyses use `|δ|` and that the engine
"records this in `warnings[]`".  INTERFACE.md requires an `effect_size` key but
does not say whether, for a solving analysis given a negative effect size, that
key carries the signed input or the absolute value actually used.

**What this implementation does.** `result["effect_size"]` carries the value
**actually used** (so that `ncp` is reproducible from `effect_size` plus the
design, and the dict is internally consistent), and the signed input is echoed
separately as `result["effect_size_input"]`.  `warnings[]` names F-08.

**To close.** State which of the two numbers the `effect_size` field holds.

---

## G-04 — Numerical endpoints of the sensitivity bisection domains

**Undetermined.** §3 gives the admissible domains as `d`, `dz` in `(0, 100]`,
`r` in `(0, 1)`, `f²` in `(0, 1e6]`, generic `δ` in `(0, 1e6]`.  Those are open
at `0` (and `r` also at `1`), so there is no representable lower endpoint to
bisect from, and SPEC.md does not say how close to an open endpoint the search
may go, nor what to report when the solution lies outside the domain.

**What this implementation does.** Bisects over `[1e-12, hi]`, with
`hi = 100`, `1 - 1e-12`, `1e6`, `1e6` respectively.  If the power at `hi` is
still below the target, `RuntimeError`.  If the power at `1e-12` already meets
the target, `1e-12` is returned.

**To close.** State the closed interval the bisection runs on, and the
behaviour when the answer is not inside it.

---

## G-05 — The `α` bracket of the criterion analysis

**Undetermined.** §3 says only "bisection; power is increasing in `α`".  It
does not bound `α`, and INTERFACE.md only requires `α ∈ (0,1)` on *input*.
Whether an answer of, say, `α = 2e-68` should be returned, refused, or capped
(at `0.5`, or at some display floor) is not stated.

**What this implementation does.** Bisects `log α` over
`[log(1e-300), log(1 - 1e-15)]` — giving relative accuracy in `α` — and returns
whatever `α` solves the equation, however small.  `RuntimeError` only if even
`α = 1 - 1e-15` falls short of the target power.

**To close.** State the `α` search interval and whether tiny solutions are
reported or refused.

---

## G-06 — Which number the reported "critical t" is for a two-tailed test

**Undetermined.** F-02 uses the single quantile `t_{1-α/2, ν}`, and F-12 says
"critical `t`" is a reported quantity rounded to 7 decimals.  Since a
two-tailed test has two critical values (`±t_{1-α/2, ν}`), SPEC.md does not say
whether the field holds the positive one, the negative one, or a pair.  It is
also silent on `k = 1` with `α > 0.5`, where `t_{1-α, ν}` is negative.

**What this implementation does.** `critical_t` is always the single quantile
that appears in F-02 — `t_{1-α, ν}` for `k = 1` and `t_{1-α/2, ν}` for
`k = 2` — reported signed, so it can come out negative for `k = 1` with
`α > 0.5`.  For compromise it is the solved `c` of F-10, again signed.

**To close. ** Say which number the field holds (and whether it is ever
negative).

---

## G-07 — Inadmissible grid points of the `total-grid` rule

**Undetermined.** F-09 gives the `total-grid` as `N = 4, 5, 6, …` with
`n₁ = round_half_up(N/(1+R))`, `n₂ = N - n₁`, while F-05 requires `n₁ ≥ 2` and
`n₂ ≥ 2`.  For `R` far from 1 the leading grid points violate that: with
`R = 20`, `N = 4` gives `n₁ = 0`.  SPEC.md does not say whether such points are
skipped (and the enumeration continues) or whether the analysis fails.  The
same question arises for `n1-grid` with `R < 1`, where small `n₁` give
`n₂ < 2`.

**What this implementation does.** Inadmissible grid points are skipped: they
are treated as never reaching the target, so the effective search starts at the
smallest index for which both groups have at least 2 members.  (Admissibility
is an up-set in the grid index on both grids, so this is equivalent to
enumerating from the first admissible point.)

**To close.** Add a clause to F-09 stating that grid points violating F-05's
minimum group sizes are skipped rather than fatal.

---

## G-08 — Zero effect size in a solving analysis

**Undetermined.** SPEC.md's minimum-design statements bound `N`, and F-04
bounds `|r|`, but nothing says what an a-priori / criterion analysis with
`effect_size = 0` should do.  With `δ = 0` the power of F-02 equals `α` for
every `N`, so no finite design reaches a target power above `α` and no `α < 1`
reaches a target power above `α` either.

**What this implementation does.** `ValueError` for a zero effect size in the
a-priori, criterion and compromise analyses (post hoc and the sensitivity
analysis are well defined and are allowed: post hoc returns exactly `α`).

**To close.** State whether a zero effect size is a domain error or is expected
to exhaust the search and raise the bounded-search error.

---

## G-09 — The rounding **mode** of the display rounding

**Undetermined.** F-09 is emphatic that *allocation* rounding is
half-away-from-zero and explicitly not half-to-even.  F-12 then says `δ`,
critical `t` and power are "rounded for display" to 7 decimals but does not say
in which mode — and after F-09 the reader cannot assume the language default.

**What this implementation does.** Display rounding uses Python's `round`
(round-half-to-even), in `gpower_cleanroom.report`.  The distinction can only
show up in the 7th decimal of a displayed number and never enters a search, so
it cannot change an integer sample size.

**To close.** Say which rounding mode F-12's display rounding uses.

---

## G-10 — No Python name is specified for F-09's or F-11's behaviour

**Undetermined.** INTERFACE.md fixes `TESTS` plus exactly five function names
and says internal structure is otherwise free.  But SPEC.md requires behaviour
that no named function can reach:

* F-09 says the engine implements **both** candidate grids and that "the CLI
  exposes both via `--allocation-rule`" — yet `required_sample_size`'s signature
  in INTERFACE.md has no such parameter, and there is no CLI in scope.
* F-11 says the effect-size drawer offers **two** pooled SDs and that an
  implementation offering only one is defective — yet INTERFACE.md names no
  effect-size function at all.

**What this implementation does.** Adds, and documents as additions:

* a keyword-only `allocation_rule: str = "n1-grid"` parameter on
  `required_sample_size` (default as F-09 requires), plus the module-level
  `ALLOCATION_RULES`;
* module-level `cohen_d_from_means`, `pooled_sd_equal_n`,
  `pooled_sd_unequal_n` and `POOLING_OPTIONS` in
  `gpower_cleanroom.effectsize`, re-exported from the package root.

All five INTERFACE.md functions keep exactly the specified names and signatures
(the new parameter is keyword-only with a default, so every call written
against INTERFACE.md behaves identically).

**To close.** INTERFACE.md should name the allocation-rule parameter and the
effect-size entry points, or state that they are implementation-defined.

---

## G-11 — Argument validation for irrelevant arguments

**Undetermined.** INTERFACE.md gives every analysis the union of all design
arguments (`n`, `n1`, `n2`, `predictors`, `df`).  It says `df` is
"`ttest-generic` only" and `predictors` is "`ttest-regression-coef` only" and
`allocation_ratio` is "two-group test only", but it does not say whether
supplying one where it does not apply is an error or is ignored.

**What this implementation does.** Irrelevant design arguments are ignored
(no error).  For single-group tests, `n1` is accepted as a synonym for `n` when
`n` is absent.  Missing *required* arguments are `ValueError`
(`df` for `ttest-generic`, `predictors` for `ttest-regression-coef`, `n1` and
`n2` for `ttest-indep-means`, `n` for the single-group tests).

**To close.** State whether an inapplicable argument is ignored or rejected.

---

## G-12 — Minimum admissible design is stated for five tests but not for the generic one

**Undetermined.** F-03, F-04, F-05 and F-07 each state a minimum admissible
design.  The *Generic t test* has no `N`, and SPEC.md gives no lower bound on
its `ν` beyond INTERFACE.md's "degrees of freedom would be `<= 0`" error.  In
particular, whether `0 < ν < 1` is admissible is not stated.

**What this implementation does.** Any `ν > 0` is accepted, including
`ν < 1`.  (The quadrature integrates in `y = log s`, where the mixing measure
is entire for every `ν > 0`; mass closure is verified down to `ν = 0.05` in
`selfcheck.py`.)

**To close.** State the admissible `ν` domain of the generic t test.
