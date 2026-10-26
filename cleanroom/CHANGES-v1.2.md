# CHANGES-v1.2.md: gpower_cleanroom 1.0.0 → 1.2.0 (SPEC.md v1.1 → v1.2)

| # | change | file(s) | SPEC finding |
|---|---|---|---|
| 1 | New allocation rule `"even-total"`. The grid is `N = 4, 6, 8, …`. The stopping test uses the unrounded split `m₁ = N/(1+R)`, `m₂ = NR/(1+R)` with `ν = N−2`. The reported split is `n₁ = round_half_up(N/(1+R))`, `n₂ = N − n₁`. It is now the **default** of `required_sample_size(allocation_rule=…)`. `"n1-grid"` and `"total-grid"` stay selectable. `ALLOCATION_RULES` now lists all three. | `_designs.py`, `_analyses.py` | F-09 (REFUTED → CORRECTED), F-05 |
| 2 | Actual power is recomputed at the reported integer split and returned as is, even when it is below the target. The design is not repaired. The selfcheck "actual ≥ target" now applies only at `R = 1`. | `_analyses.py`, `selfcheck.py` | F-06 (corrected clause) |
| 3 | Sign rule. All five analyses compute probabilities from `\|δ\|`. `ncp` is reported as `sign(ES)·\|δ\|`. `critical_t` is reported as `sign(ES)·t_crit` in a priori, post hoc and compromise, and **unsigned** in criterion. `effect_size` echoes the signed input. A negative ES (generic `δ` included) adds a `warnings[]` entry. Previously, post hoc used the signed `δ` (power < α) and compromise used the signed `δ`. | `_analyses.py` | F-08 (REFUTED → CORRECTED), F-13 items 1, 3, 6 |
| 4 | Point biserial: `0 < r ≤ 0.999999` in every analysis. A negative or zero `r` is refused, with a message that names the range. The sensitivity bracket is now `[1e-12, 0.999999]`. | `_designs.py` | F-08, F-15, F-13 item 4 |
| 5 | `f²`: refused when `< 0` or `≥ 20`. | `_designs.py` | F-15, F-13 item 2 |
| 6 | A priori: refuses `\|ES\| < 0.00001` (replaces the "non-zero" check). | `_analyses.py` | F-15, F-13 item 8 |
| 7 | A priori and sensitivity: refuse `power < α`; `power = α` is accepted. | `_analyses.py` | F-15 |
| 8 | Compromise: `β/α` must lie in `[0.01, 100]`. | `_analyses.py` | F-15 |
| 9 | Explicit designs (post hoc, criterion, sensitivity, compromise): total `N ≥ 3` (so one sample / matched pairs `N = 2` is refused), regression `N ≥ p+2`, two groups `n₁, n₂ ≥ 1` (so `n₁ = 1, n₂ = 2` is accepted). The a-priori grid still starts at `ν = 1` (matched pairs `d = 20` → `N = 2`). | `_designs.py` | F-15, F-03, F-05 |
| 10 | Inapplicable parameters are rejected instead of silently ignored: `predictors` on non-regression tests, `df` on non-generic tests, `n` on the two-group test, sizes on the generic test, and non-default `allocation_ratio` / `allocation_rule` on single-group a priori. | `_designs.py`, `_analyses.py` | F-13 item 11 |
| 11 | The a-priori search limit is now `N ≤ 2⁶³ − 2` (was 10,000,000 grid points). The `RuntimeError` message names the cap. | `_designs.py`, `_analyses.py` | §3, F-15 (see SPEC-GAPS G2-01) |
| 12 | `warnings[]` entry when a criterion or compromise result has `α < 1e-9`, or an a-priori result has `N > 1e7`. | `_analyses.py` | F-14 |
| 13 | Large-df critical value: for `ν ≥ 1e5` and `ν ≥ 1000 z²`, `student_t_isf` returns the four-term Cornish–Fisher series (A&S 26.7.5, new `cornish_fisher_t`) with no refinement. | `_numerics.py` | §4 item 7 |
| 14 | `__version__` set to 1.2.0 and the docstring updated. | `__init__.py` | — |
| 15 | `selfcheck.py`: dropped the v1.1 F-08 checks (power < α, signed post hoc). Fixed `N = 2` / `n₁ = 1` / 10,000,000-cap cases to the v1.2 domain. Selected the v1.1 rules explicitly where checks test them. Added 28 v1.2 checks (plus 2 more §3 cap checks, one per rule, in the error-handling section): P-08-a, N-01, N-03, N-05, S-019, the `.946` sweep row, A-022, D-23, D-31, D-43, D-44, the F-15 domain table (35 cases), F-13 item 11, F-14 warnings, the §3 cap, and §4 item 7. Total: 82 checks. | `selfcheck.py` | all of the above |

Unchanged: `_power.py`, `effectsize.py`, `report.py`.

---

## v1.3: gpower_cleanroom 1.2.0 → 1.3.0 (SPEC.md v1.3, F-16)

| # | change | file(s) | SPEC finding |
|---|---|---|---|
| 1 | Even-total no longer skips grid points with a group below 2 (D-28 / X-G2-04: `R = 3`, `d = 8` and `d = 20` now give `1 / 3`). The v1.1 rules `n1-grid` and `total-grid` keep their skip. | `_designs.py` | F-16 G2-04, F-09 |
| 2 | Point biserial `r = 0` is admissible (post hoc returns `α`). The domain is now `0 ≤ r ≤ 0.999999` and the error message reads `[0, 0.999999]`. | `_designs.py` | F-15, F-16 G2-06 |
| 3 | The a-priori floor `\|ES\| ≥ 1e-5` applies to `d`, `dz`, `f²` and **not** to `r` (`r = 5e-6` now gives `N ≈ 3.1e11`). A zero ES is still refused in a priori. | `_designs.py`, `_analyses.py` | F-15, F-16 G2-08, §3 |
| 4 | Allocation ratio domain `[0.01, 100]`, for all three rules (was: any finite `R > 0`). | `_analyses.py` | F-15, F-16 G2-11 |
| 5 | `actual_allocation_ratio` is `inf` when even-total reports an empty first group (see SPEC-GAPS-v1.3.md G3-01). | `_analyses.py` | F-16 G2-04 |
| 6 | The `RuntimeError` message for the search cap now cites the corrected INTERFACE.md / F-16 G2-01 (cap on the total). | `_analyses.py` | F-16 G2-01 |
| 7 | `__version__` 1.3.0, docstrings updated. | `__init__.py` | — |
| 8 | `selfcheck.py`: the "r = 0 refused" case is now accepted. Removed the minimum-group condition from the even-total minimality check. The cap test now uses point biserial `r = 1e-12`, the only way to exhaust the cap inside the v1.3 domain. Added F-15 v1.3 rows (r = 0, r and f² at 5e-6, R ends, n₁ = 0, p = 0) and a v1.3 section with one check per observed F-16 row (G2-04/D-28, the v1.1 skip, G2-05, G2-06, G2-07, G2-08, G2-09, G2-14, G2-18/19) plus the version. Total: 90 checks. | `selfcheck.py` | F-15, F-16 |

Already conformant in 1.2.0 and unchanged: G2-01, 02, 03, 05, 07, 09, 10, 12, 13, 14, 15, 16, 17, 18, 19.
