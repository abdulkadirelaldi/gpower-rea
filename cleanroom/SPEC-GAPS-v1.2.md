# SPEC-GAPS-v1.2.md: where SPEC.md v1.2 did not determine this implementation

Session B, second pass. Written from SPEC.md v1.2 and INTERFACE.md only. Each
entry gives the SPEC section, what was left undetermined or contradictory,
what `gpower_cleanroom` 1.2.0 does, and an input where another reasonable
reading gives a different output. Every number below was computed with this
package.

Defaults throughout: α = 0.05, two tails, unless stated otherwise.

---

### G2-01: Search cap: INTERFACE.md says 10,000,000, SPEC.md says 2⁶³ − 2
* **Section:** INTERFACE.md "Error handling" vs SPEC §3 (a priori row), F-15 ("a-priori `N` up to `2⁶³ - 2`"), F-14 (which requires warnings for results with `N > 1e7`).
* **Contradiction:** INTERFACE.md tells the implementation to cap the sample-size search at 10,000,000 and raise `RuntimeError`. SPEC.md v1.2 searches up to `2⁶³ − 2` and quotes returned answers up to `N = 7.8e10`. The F-14 warning for `N > 1e7` could never fire under the INTERFACE cap.
* **Chosen:** SPEC.md. The cap is `N ≤ 2⁶³ − 2` on the **total** N, for all three allocation rules. The `RuntimeError` message gives the cap (`2**63 - 2 = 9223372036854775806`) and says that it replaces the 10,000,000 cap.
* **Divergent input:** D-44, `ttest-indep-means`, `d = 0.001`, `R = 2`, power `.8`. This engine returns `N = 35 319 876`. Under the INTERFACE reading it raises `RuntimeError`.

### G2-02: Smallest explicit two-group design: F-05 vs F-15
* **Section:** F-05 ("Minimum admissible design: `n₁ ≥ 2` and `n₂ ≥ 2`") vs F-15 ("explicit design … total `N ≥ 3` … `n₁ = 1, n₂ = 2` accepted (D-24)").
* **Contradiction / undetermined:** The two statements contradict each other for `n₁ = 1`. F-15 also does not say whether an empty group (`n₁ = 0`, `n₂ ≥ 3`) passes "total `N ≥ 3`".
* **Chosen:** For explicit designs (post hoc, criterion, sensitivity, compromise), F-15 applies: `n₁ ≥ 1`, `n₂ ≥ 1`, `n₁ + n₂ ≥ 3`. An empty group is refused. F-05's `≥ 2` is kept only for the a-priori grid (see G2-04).
* **Divergent input:** `achieved_power("ttest-indep-means", alpha=.05, effect_size=.5, n1=1, n2=2)` returns a power here but raises `ValueError` under F-05. With `n1=0, n2=3`, this engine raises `ValueError`. A literal "total ≥ 3" reading would compute `δ = 0`, `ν = 1` and return power `0.05`.

### G2-03: One sample / matched pairs minimum: F-03 "N ≥ 2" vs F-15 "N = 2 refused"
* **Section:** F-03 ("Minimum admissible design: `N ≥ 2`") vs F-15 (D-08, D-41 refuse `N = 2`; D-23 returns `N = 2` from an a-priori analysis).
* **Contradiction:** F-03 still states `N ≥ 2` without qualification.
* **Chosen:** `N ≥ 3` for every explicit design. The a-priori grid still starts at `N = 2` (`ν = 1`), so D-23 (matched pairs, `d = 20`) returns `N = 2`, as F-15 records.
* **Divergent input:** `achieved_power("ttest-one-sample", alpha=.05, effect_size=.5, n=2)` raises `ValueError` here. Under F-03 it returns a power.

### G2-04: Which grid points even-total skips, and on which split
* **Section:** F-09 pseudo-code (no skip at all, stopping test on the unrounded `m₁, m₂`) vs F-13 item 7 ("grid points violating F-05's minimum group sizes are skipped") vs F-15 (explicit designs may have `n₁ = 1`).
* **Undetermined:** Whether even-total skips anything. If it does, whether the test uses the rounded reported split or the unrounded one, and whether the threshold is F-05's 2 or F-15's 1.
* **Chosen:** Skip index `N` when the **rounded** split `round_half_up(N/(1+R))`, `N − n₁` has a group below 2 (F-13 item 7, literally F-05's minimum). The stopping test itself still uses the unrounded split.
* **Divergent input:** `d = 8`, `R = 3`, power `.8`. At `N = 4` the unrounded split (1, 3) has power `0.9085 ≥ 0.8`, but the rounded split has `n₁ = 1`. This engine skips it and returns `2 / 4` (`N = 6`). The no-skip pseudo-code reading returns `1 / 3` (`N = 4`).

### G2-05: Which δ is reported by even-total a priori
* **Section:** F-09 ("Actual power recomputed at `(n₁, n₂)`"), F-06.
* **Undetermined:** Only power is said to be recomputed at the rounded design. The printed noncentrality could be the one from the stopping test (unrounded split) or the one at the reported split. (`ν = N − 2` and the critical t are the same either way.)
* **Chosen:** `ncp` at the reported integer split, which is the same design as the reported power.
* **Divergent input:** S-019 (`d = .5`, `R = 1.5`, power `.9495`, `87 / 131`). This engine reports `ncp = 3.6152392`. The unrounded split gives `3.6166283`.

### G2-06: Point biserial `r = 0`
* **Section:** F-15 (`0 < r ≤ 0.999999`; N-07 message "(0, 0.999999)") vs §3 and F-13 item 8 ("A zero effect size is … admissible for post hoc … and for sensitivity").
* **Contradiction:** For point biserial, F-15 excludes `r = 0` and §3 admits it.
* **Chosen:** F-15, the more specific and observed rule: `r = 0` is refused in every analysis. Because 0.999999 is accepted (D-01), the message says `(0, 0.999999]` and not the quoted open interval.
* **Divergent input:** `achieved_power("ttest-point-biserial", alpha=.05, effect_size=0, n=10)` raises `ValueError` here. Under §3 it returns power `0.05`.

### G2-07: Upper end of the `f²` sensitivity bracket (1e6) vs the `f²` input domain (< 20)
* **Section:** §3 / F-13 item 4 (`f²` bracket `[1e-12, 1e6]`) vs F-15 (`f²` input admissible only for `0 ≤ f² < 20`).
* **Undetermined:** Whether a sensitivity answer may exceed a value G\*Power would refuse as input.
* **Chosen:** §3's bracket, as written. F-15 restricts inputs and a sensitivity answer is an output.
* **Divergent input:** `detectable_effect_size("ttest-regression-coef", alpha=.001, power=.99, n=4, predictors=2)` returns `f² = 672256.13`. A bracket capped below 20 raises `RuntimeError` (unattainable).

### G2-08: Which effect sizes the a-priori threshold `|ES| ≥ 0.00001` covers
* **Section:** F-15 ("a-priori effect size `|ES| ≥ 0.00001`", observed on one-sample `d`, D-31 and D-40).
* **Undetermined:** Whether the threshold also applies to `r` and to `f²`. `f²` is a squared quantity, so 1e-5 on `f²` is a different scale from 1e-5 on `d`.
* **Chosen:** Literal: applied to every a-priori effect size (`d`, `dz`, `r`, `f²`).
* **Divergent input:** `required_sample_size("ttest-regression-coef", alpha=.05, power=.8, effect_size=5e-6, predictors=1)` raises `ValueError` here. Without the threshold for `f²` it returns `N ≈ 1.57e6` (`f² = 1e-5` gives `N = 784 888`).

### G2-09: The sign of a zero effect size
* **Section:** F-08 (`δ printed = sign(ES)·|δ|`, `critical t = sign(ES)·t_crit`).
* **Undetermined:** `sign(0)`, and the sign of `-0.0`. A post-hoc or sensitivity analysis can have `ES = 0` (§3).
* **Chosen:** `+1` for both `0` and `-0.0`. Neither produces a negative-ES warning.
* **Divergent input:** `achieved_power("ttest-one-sample", alpha=.05, effect_size=0, n=10)` returns `critical_t = +2.2621572`. A literal `sign(0) = 0` gives `critical_t = 0`. Treating `-0.0` as negative gives `-2.2621572` and a warning.

### G2-10: What "N" means in F-14's `N > 1e7` warning for two groups
* **Section:** F-14 Requirement ("an a-priori result has `N > 1e7`").
* **Undetermined:** Total N or group size.
* **Chosen:** The total N (the F-14 table quotes totals, e.g. D-44).
* **Divergent input:** `ttest-indep-means`, `d = 0.0016`, `R = 1`, power `.8` gives total `12 263 848` (6.1e6 per group). This engine warns. A per-group reading does not.

### G2-11: Domain of the allocation ratio `R`
* **Section:** F-15 (no row for `R`), F-09.
* **Undetermined:** Which `R` values G\*Power refuses.
* **Chosen:** Any finite `R > 0`.
* **Divergent input:** `R = 1e-12`, `d = 1e-5`, `α = 1e-6`, power `.99`. This engine searches to the cap and raises `RuntimeError`. Any range check on `R` (for example the `[0.01, 100]` used for `q`) raises `ValueError` instead.

### G2-12: Allocation parameters on a single-group a-priori analysis
* **Section:** F-13 item 11 / §3 ("an inapplicable design parameter … is rejected, not ignored"). The examples given are `predictors` and `df` only.
* **Undetermined:** Whether `allocation_ratio` and `allocation_rule` count as design parameters, given that both have defaults.
* **Chosen:** Rejected when they differ from their defaults (`1.0`, `"even-total"`). The default values are accepted because they cannot be told apart from omission.
* **Divergent input:** `required_sample_size("ttest-one-sample", alpha=.05, power=.8, effect_size=.3, allocation_ratio=2)` raises `ValueError` here. An "ignore it" reading returns `N = 90`.

### G2-13: How sample sizes are spelled per test
* **Section:** INTERFACE.md (`n` for single-group tests, `n1`/`n2` for the two-group test, `df` for generic), F-13 item 11.
* **Undetermined:** Whether `n1` is accepted for a single-group test, given that the result dict reports the single-group total as `n1`, and whether `n2 = 0` or `n = 0` count as absent.
* **Chosen:** For single-group tests `n1` is an alias for `n` (both must agree if both are given). `n2` must be `None` or `0`. For the generic test `n`/`n1`/`n2` must be `None` or `0`. `n` on the two-group test is rejected.
* **Divergent input:** `achieved_power("ttest-one-sample", alpha=.05, effect_size=.5, n1=30)` returns power `0.7539…` here. A strict reading raises `ValueError`.

### G2-14: Arithmetic of the F-09 split `round_half_up(N/(1+R))`
* **Section:** F-09 ("half-away-from-zero", A-022).
* **Undetermined:** Whether `N/(1+R)` is evaluated in binary floating point or exactly, with `R` as the decimal the user typed. The two differ whenever the exact quotient is `k + ½` and `1+R` is not a dyadic rational.
* **Chosen:** IEEE double, the most literal reading of the formula, with the tie broken half-away-from-zero on the computed double.
* **Divergent input:** `d = 1.11`, `R = 7.8`, power `.8` stops at `N = 66`. `66/8.8` is exactly `7.5` but evaluates to `7.4999…` in double, so this engine reports `7 / 59` with actual power `0.7807817`. Exact decimal arithmetic reports `8 / 58` with actual power `0.8260675`. (`R = 7.8` is the only tenth in `0.1…9.9` that produces such a tie for `N < 5000`.)

### G2-15: The search range beyond 2⁵³
* **Section:** §3 / F-15 ("searched up to `2⁶³ − 2`"), §4.
* **Undetermined:** Doubles cannot represent every integer above `2⁵³ ≈ 9.0e15`. SPEC.md does not say whether the stopping test there has to resolve single steps of N.
* **Chosen:** Integer bookkeeping in Python ints, with `ν` and `δ` computed in double. Above `2⁵³`, neighbouring totals can have identical computed power. The bisection then returns the first index at which the computed power passes, and the F-14 warning is attached.
* **Divergent input:** `ttest-indep-means`, `d = 1e-5`, `R = 1e-6`, power `.8` gives `N = 78 488 762 070 551 210`. An implementation in exact or extended precision may return a different total in that region. One that refused to go past `2⁵³` would raise instead.

### G2-16: The "four-term" Cornish–Fisher series of §4 item 7, and its switch condition
* **Section:** §4 item 7. (§4 also numbers its items 1–5, 7, 6 and says "five things" while listing seven. That is editorial and has no effect on behaviour.)
* **Undetermined:** Whether "four-term" means `z + g₁/ν + g₂/ν² + g₃/ν³` or the four corrections `g₁…g₄` of A&S 26.7.5. Also which `z` enters `ν ≥ 1000 z²` (that of `α`, or that of `α/2` for two tails).
* **Chosen:** `z + g₁/ν + … + g₄/ν⁴`, with `z` the normal quantile of the tail probability actually being inverted (`α/2` for two tails).
* **Divergent input:** None found at the §5 tolerances. On the switch region (`ν ≥ 1e5`, `ν ≥ 1000 z²`) the `g₄` term is at most about `1e-15` relative (e.g. `ν = 1e5`, `p = 1e-10`). The `z` choice only moves the switch point, and the quantile is continuous across it to `< 1e-9` absolute (selfcheck S4.7).

### G2-17: Domain of `predictors`
* **Section:** F-07, F-15 (no row for `p`).
* **Undetermined:** Whether `p = 0` (or a non-integer `p`) is admissible.
* **Chosen:** Integer `p ≥ 1`.
* **Divergent input:** `achieved_power("ttest-regression-coef", alpha=.05, effect_size=.15, n=20, predictors=0)` raises `ValueError` here. A `p ≥ 0` reading computes `ν = 19`, `δ = √3`.

### G2-18: Does a negative generic `δ` count as a "negative effect size"?
* **Section:** F-08 ("The engine records `warnings[]` whenever a negative effect size was supplied"). INTERFACE.md: for `ttest-generic`, `effect_size` *is* the noncentrality.
* **Undetermined:** Whether the F-08 warning covers the generic test's `δ`.
* **Chosen:** Yes. N-05 shows that the generic test follows the same sign rule, so it gets the same warning.
* **Divergent input:** `achieved_power("ttest-generic", alpha=.05, effect_size=-2.5, tails=1, df=30)` returns one warning here and none under the other reading. Numbers are identical either way.

### G2-19: Shape and content of `warnings`
* **Section:** F-08, F-14 ("adds a `warnings[]` entry"). The task text: the result dict *may* carry a `"warnings"` list.
* **Undetermined:** Whether the key is always present, and what an entry looks like.
* **Chosen:** Every result has `"warnings": list[str]`, empty when nothing applies. Each entry is a sentence that names its finding (`"SPEC.md F-08"`, `"SPEC.md F-14"`). One entry per condition, so a negative ES with a tiny criterion `α` gives two.
* **Divergent input:** `required_alpha("ttest-one-sample", power=.8, effect_size=-1.5, n=40)` returns two entries. A single-flag or key-only-when-non-empty design differs in structure. The numbers are unaffected.

---

**Count:** 19 gaps (G2-01 … G2-19). G2-01, G2-02, G2-03 and G2-06 are self-contradictions between sections of SPEC.md v1.2, or between SPEC.md and INTERFACE.md. G2-04 and G2-07 are tensions between an older finding and a new one. The rest are points the text does not determine.
