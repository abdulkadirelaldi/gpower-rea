# LEDGER.md — evidence ledger, t2-indep and the t tests family

Each line is one claim, one label, and where its evidence is.

| label | meaning in this ledger |
|---|---|
| `[DOK]` | stated in the G\*Power manual or in Faul, Erdfelder, Lang & Buchner (2007, 2009) |
| `[REA]` | proven from the binary, by function address or string reference |
| `[GÖZLEM]` | proven by a recorded G\*Power 3.1.9.6 GUI reading: an `oracle/` or `probes/observations/` row, re-checked by `tests/test_gpower_observed.py` on every build |
| `[AJAN]` | the agent's inference; no evidence. Stays here until a test settles it |

> **On `[REA]`.** This work established G\*Power's behaviour by differential
> testing against the running program (black box), not by static analysis of
> the executable. **The ledger therefore has no `[REA]` line.** Every behaviour
> claim below is `[GÖZLEM]`: settled by the program's own output, with the
> exact input and the exact printed value on record. The executable analysed
> by the course, `GPowerNT.exe` 3.1.9.7 (SHA-256
> `c63e6a133eb6372932f810c08cc33dc35a06d1ddb658f897bd6c34a754efc812`), is
> identified in the README; the readings come from the macOS build 3.1.9.6.

---

## 1. Documented background — `[DOK]`

| # | claim | label | source |
|---|---|---|---|
| L-01 | the t tests family computes power from the noncentral *t* distribution | `[DOK]` | G\*Power 3.1 manual; Faul et al. 2007 |
| L-02 | two independent means: effect size `d = (μ₁ − μ₂)/σ`, `df = n₁ + n₂ − 2` | `[DOK]` | manual, "Means: Difference between two independent means" |
| L-03 | the five analysis types (a priori, compromise, criterion, post hoc, sensitivity) | `[DOK]` | manual; the GUI's own menu |
| L-04 | "Allocation ratio N2/N1" is an input of the a-priori analysis | `[DOK]` | manual; GUI label |
| L-05 | a priori reports *Actual power* | `[DOK]` | GUI label (its computation is L-13) |

## 2. Behaviour not in the documentation — `[GÖZLEM]`

| # | claim | label | evidence (probe ids → `oracle/`, `probes/observations/`) | test |
|---|---|---|---|---|
| L-10 | `δ = d·√(n₁n₂/(n₁+n₂))`; the canonical example prints `3.6228442 / 1.9714347 / 208 / 210 / 0.9501287` | `[GÖZLEM]` | `P-01-a` | `tests/test_gherkin_spec.py` |
| L-11 | two-sided power **keeps the wrong-side tail**: at `δ = 0`, power = `α` exactly (`0.2000000`, not `0.1000000`) | `[GÖZLEM]` | `P-02-a…c`, `D-06` | `test_gpower_observed.py` |
| L-12 | balanced a priori never reports an odd total, even when the odd split suffices (`352`, not `351`) | `[GÖZLEM]` | `P-05-a,b` | `test_gherkin_spec.py` |
| L-13 | *Actual power* is recomputed at the reported design (`0.9501287`, not `0.95`) — and can be **below** the target (`0.9494095` for target `0.9495`) | `[GÖZLEM]` | `P-06-a`, `S-019` | `test_gherkin_spec.py` |
| L-14 | **rounding / unequal ratio:** the search runs over **even totals** at every ratio; the stopping test uses the **unrounded** split `N/(1+R)`, `N·R/(1+R)`; the reported split is `n₁ = round_half_up(N/(1+R))`, `n₂ = N − n₁` | `[GÖZLEM]` | 119 rows (`A-*`, `S-*`, `P-09-*`, …); every alternative rule fails ≥ 23 of them | `tools/fit_allocation.py`, `test_clone_cli.py` |
| L-15 | **stopping condition:** `power ≥ target` with no epsilon (`0.8000014` accepted) | `[GÖZLEM]` | `P-12-a` | `test_gpower_observed.py` |
| L-16 | the split is computed in **binary double**: `66/8.8 = 7.4999…` → `7 / 59`, not the decimal `8 / 58` | `[GÖZLEM]` | `X-G2-14` | `test_spec_f16.py` |
| L-17 | half-away-from-zero rounding of the split (`42.5 → 43`) | `[GÖZLEM]` | `A-022` | `test_gherkin_spec.py` |
| L-18 | a priori may report an **empty group**: `d = 20`, `R = 100` → `0 / 6`, power `0.05` | `[GÖZLEM]` | `X-G3-01a,b` | `test_spec_f16.py` |
| L-19 | a negative `d` is a direction: power from `\|δ\|`; `δ` and the critical *t* carry the sign (criterion excepted) | `[GÖZLEM]` | `P-08-a…c`, `N-01…N-12` | `test_spec_f13.py` |
| L-20 | **invalid input:** allocation ratio outside `[0.01, 100]` → *"The allocation ratio falls outside the admissible range (0.01, 100)."* | `[GÖZLEM]` | `X-G2-11a,b` (accepted: `X-G2-11c,d`) | `test_clone_cli.py` |
| L-21 | **invalid input:** `power < α` → *"Power must be greater than or equal to alpha."*; `power = α` accepted | `[GÖZLEM]` | `D-13`, `D-32` | `test_gherkin_spec.py` |
| L-22 | **invalid input:** a-priori `\|d\| < 0.00001` → *"In an a priori analysis, the absolute value of the effect size be greater than 0.00001."* | `[GÖZLEM]` | `D-05`, `D-40` (accepted: `D-31`) | `test_gherkin_spec.py` |
| L-23 | **invalid input:** a group of 0 → *"Sample size must be greater than or equal to 1."*; total below 3 → *"…outside the admissible range (3, 9223372036854775806)"* | `[GÖZLEM]` | `X-G2-02`, `D-17` (accepted: `D-24`) | `test_gherkin_spec.py` |
| L-24 | very small effects return huge N (up to `2⁶³ − 2`): `d = 0.001`, `R = 2` → `35 319 874` | `[GÖZLEM]` | `D-44` | `test_gpower_observed.py` |
| L-25 | above `N ≈ 1e7` G\*Power's own N is inexact (`D-44`: exact power at its design `0.79999999764 < 0.8`); below `α ≈ 1e-9` it prints *"Internal Math Error!"* | `[GÖZLEM]` + 50-digit `mpmath` | `D-43`, `D-44`, `G-014`, `G-091` | `test_gpower_observed.py` (tolerated region) |
| L-26 | fractional-N libraries are not G\*Power: ceiling `statsmodels`' `n₁` reproduces G\*Power's total in only **51–62 %** of 900 vectors, although power agrees in 900/900 | `[GÖZLEM]` | `oracle/statsmodels_t2_indep.csv` | `tools/statsmodels_oracle.py` |

## 3. Inferences without evidence — `[AJAN]`

| # | claim | label | what would settle it |
|---|---|---|---|
| L-30 | the Windows build 3.1.9.7 behaves identically to the macOS build 3.1.9.6 on every line above | `[AJAN]` | entering a few `oracle/` vectors on Windows |
| L-31 | F-14's inexactness comes from G\*Power's far-tail central-*t* quantile (its printed `t` does not match its own printed `α`) | `[AJAN]` | the arithmetic is observed; *where* in the program it arises is not |
| L-32 | the effect-size calculator's "n1 = n2" option uses `√((σ₁² + σ₂²)/2)` (SPEC F-11) | `[AJAN]` | three readings in the "Determine" panel, which the GUI driver cannot reach |

Former `[AJAN]` lines that a test then **refuted** are recorded in
[HALLUCINATIONS.md](HALLUCINATIONS.md) (H-1 … H-10).
