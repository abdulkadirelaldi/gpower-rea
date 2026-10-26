# oracle/ — the reference values

The oracle is G\*Power itself. Nothing in this folder is engine output except
the `engine_*` columns of the statsmodels file, which exist to be compared.

| file | rows | what it is |
|---|---|---|
| [gpower_t2_indep.csv](gpower_t2_indep.csv) | **141** | every t2-indep run of G\*Power 3.1.9.6 (a priori 128, post hoc 13; 4 of them refused inputs, with G\*Power's message verbatim). Read off the GUI by `tools/gpower_ax.py`; generated from `probes/observations/` |
| [statsmodels_t2_indep.csv](statsmodels_t2_indep.csv) | **900** | the scale oracle: `statsmodels.TTestIndPower` for 10 `d` × 3 power × 3 `α` × 5 ratios × 2 tails, with its fractional `n₁`, three naive integerisations, and the engine's (= G\*Power's) integer answer |
| `screenshots/` | — | one PNG of the G\*Power window per vector, made by `tools/oracle_screenshots.py` (needs macOS Screen Recording permission) |

**The finding in the second file.** `statsmodels` returns a fractional `n₁`.
Rounding it up — per group, or the total — reproduces G\*Power's total in only
**51–62 %** of the 900 vectors, although the *power* at G\*Power's design agrees
in **900 / 900**. The difference is not a rounding detail: G\*Power searches
even totals and tests the unrounded split (SPEC F-09, LEDGER L-14).

```console
$ python tools/statsmodels_oracle.py
900 vectors -> oracle/statsmodels_t2_indep.csv
  ceil_total             gives G*Power's N in 462/900 (51.3%)
  ceil_each_group        gives G*Power's N in 554/900 (61.6%)
  ceil_n1_times_1plusR   gives G*Power's N in 491/900 (54.6%)
  power at the engine's design agrees with statsmodels (1e-4): 900/900
```

Boundary values required by the brief (d very small / very large, power = α
and < α, unequal ratios, invalid inputs) are rows `D-*`, `X-*`, `A-*` and
`S-*` of the first file.
