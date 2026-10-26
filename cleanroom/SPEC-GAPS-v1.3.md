# SPEC-GAPS-v1.3.md: where SPEC.md v1.3 did not determine this implementation

Session B, third pass. Written from SPEC.md v1.3 (SHA-256 `342fdb44…a259`) and
the corrected INTERFACE.md only. The format is that of SPEC-GAPS-v1.2.md. F-16
closes all 19 v1.2 gaps, and this implementation follows every one of its rows.
What remains is one real behavioural gap (G3-01), one ambiguity in scope
(G3-02), one tension between §3 and F-15 (G3-03), and stale text left over from
v1.2 (G3-04). Every number below was computed with `gpower_cleanroom` 1.3.0.
Defaults: α = 0.05, two tails, power .8.

---

### G3-01: Even-total can report an **empty** group at the edges of the ratio domain
* **Section:** F-09 (no skip), F-16 G2-04 ("F-13 item 7's skip does not apply to even-total"), F-15 (allocation ratio `[0.01, 100]`; explicit designs need each group `≥ 1`; "a-priori result as small as `ν = 1`").
* **Undetermined:** With no skip and a stopping test on the unrounded split, a large `d` at `R = 100` (or `R = 0.01`) stops at a total `N` whose rounded split is `round_half_up(N/101) = 0`. G2-04 was observed with a group of **1**. Nothing says what G\*Power reports when the rounded split has a group of **0**. Candidates: print it as is, skip it, clamp the group to 1, or refuse.
* **Chosen:** The literal F-09 / F-16 reading. Report the split as is and recompute actual power there. `δ = 0` at an empty group, so actual power is exactly `α`. `actual_allocation_ratio` is `inf`. Post hoc refuses that design as input (F-15), which is the same kind of a-priori/post-hoc inconsistency F-15 already records for `N = 2`.
* **Divergent input:** `ttest-indep-means`, `d = 20`, `R = 100`. This engine returns `0 / 6`, `ncp = 0`, power `0.0500000`. Clamping a group to 1 gives `1 / 5` with power `≈ 1.0000000`. Skipping index points with an empty group returns a later total. `R = 0.01` gives the mirror case, `6 / 0`.

### G3-02: Which minimum the retained v1.1 rules skip
* **Section:** F-05 (still reads "Minimum admissible design: `n₁ ≥ 2` and `n₂ ≥ 2`"), F-13 item 7 (skip below F-05's minimum), F-16 G2-02 ("F-05's `≥ 2` is not a limit at all"), F-16 G2-04 (the skip "does not apply to even-total", which implies it still applies to the other rules).
* **Contradiction:** If F-05's `≥ 2` is no limit, then F-13 item 7 has nothing to skip, for any rule. Yet G2-04 limits the non-application to even-total.
* **Chosen:** `n1-grid` and `total-grid` keep the v1.1 behaviour exactly (skip any group `< 2`, start `n1-grid` at `n₁ = 2`), because F-09 keeps them "for reproducing v1.1 output only".
* **Divergent input:** `d = 8`, `R = 3`, `allocation_rule="total-grid"`. This engine returns `2 / 4`. A "minimum 1" reading gives `1 / 3`. With `"n1-grid"` this engine returns `2 / 6`, and starting the grid at `n₁ = 1` would allow `1 / 3`.

### G3-03: A-priori point biserial at `r = 0`
* **Section:** F-15 (point biserial `0 ≤ r ≤ 0.999999`, "`r = 0` accepted"; the a-priori `1e-5` floor "not applied to `r`") vs §3 / F-13 item 8 ("A zero effect size is a validation error for the a-priori, criterion and compromise analyses").
* **Undetermined:** X-G2-06 is quoted for post hoc ("post hoc returns `α`"). F-15's input domain does not name an analysis, and with no floor for `r`, `r = 0` passes every a-priori input check. Only §3's zero rule excludes it.
* **Chosen:** §3's rule. `r = 0` raises `ValueError` in a priori, criterion and compromise, and is accepted in post hoc. The smallest positive `r` is accepted, and a search that cannot reach the target raises `RuntimeError` at the cap (`r = 1e-12`).
* **Divergent input:** `required_sample_size("ttest-point-biserial", alpha=.05, power=.8, effect_size=0)` raises `ValueError` here. Under the F-15-only reading it searches to `2⁶³ − 2` and raises `RuntimeError` instead.

### G3-04: Stale text that contradicts F-15/F-16 (editorial; behaviour determined)
* **Sections and statements:**
  * F-03: "Minimum admissible design: `N ≥ 2`".
  * F-04: "with `0 < |r| < 1`".
  * F-05: "`n₁ ≥ 2` and `n₂ ≥ 2`".
  * F-08: quotes the message "(0, 0.999999)" as the enforced range.
  * §3: "`|ES| ≥ 1e-5` for a priori", without the `r` exception.
  * The Status line still says "v1.2 is the first version written from observations".
* **Chosen:** F-15 and F-16 win wherever they are more specific. The point-biserial error message says `[0, 0.999999]`.
* **Divergent input:** Wherever a reader follows the stale sentence. Examples: `achieved_power("ttest-point-biserial", alpha=.05, effect_size=0, n=10)` returns `0.05` here, and raises under F-04's `0 < |r|`. `required_sample_size("ttest-point-biserial", alpha=.05, power=.8, effect_size=5e-6)` returns `N ≈ 3.14e11` here, and raises under §3's unqualified floor.

---

**Count:** 4 (G3-01 … G3-04). Only G3-01 is a behavioural question about G\*Power that v1.3 leaves open. G3-02 and G3-03 are questions of scope. G3-04 is editorial.
