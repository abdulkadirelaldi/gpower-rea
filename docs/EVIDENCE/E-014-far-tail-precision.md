# E-014 — Below α ≈ 1e-9 and above N ≈ 1e7, G\*Power's own answer is inexact

| | |
|---|---|
| **Finding** | [F-14](../../SPEC.md#f-14--gpowers-own-answers-become-inexact-below-α--1e-9-and-above-n--1e7) |
| **Status** | `[GÖZLEM]` — found by the conformance grid, arbitrated by a 50-digit computation |
| **Method** | Seeded random grid (`G-*`), then exact arbitration with `mpmath` at 50 digits |
| **Target** | G\*Power 3.1.9.6 (macOS), `t tests`, *Criterion* and *Compromise* analyses; *A priori* at very small effects |
| **Rows** | `G-003`, `G-007`, `G-014`, `G-049`, `G-091`, `G-115`, `G-168`, `G-187`, `G-205`, `G-230`; `D-31`, `D-43`, `D-44` |

## [GÖZLEM] Claim

When the answer `α` of a criterion or compromise analysis is below roughly
`1e-9`, G\*Power 3.1.9.6 prints an `α` and a critical *t* that are not the exact
solution, and further out it gives up with *"Internal Math Error! GPower was
not able to compute the results. Please try less extreme input parameters!"*.
The manual mentions neither.

## How it was found

Not by looking for it. The 240-row seeded grid
(`tools/rea_campaign.py --set grid`) was scored field by field against the
engine. Every disagreement it produced had the same shape: a criterion or
compromise analysis whose answer `α` was tiny.

## [GÖZLEM] Observation and arbitration

| row | input | G\*Power printed | engine | exact (`mpmath`, 50 digits) |
|---|---|---|---|---|
| `G-003` | point biserial, criterion, 2 tails, `N = 101`, `r = 0.67`, power `.8` | `α = 1.32816e-12`, `t = 8.1198649` | `α = 1.328116e-12`, `t = 8.1198547` | `t(α_engine) = 8.119854696`, power at `α_engine` = **`0.8000000`**; power at `α_G*Power` = `0.8000017` |
| `G-007` | matched pairs, criterion, 1 tail, `N = 150`, `dz = 0.73`, power `.8` | `α = 1.385003e-13`, `t = 8.0263534` | `α = 1.384721e-13`, `t = 8.0263188` | `t(α_engine) = 8.026318782`, power at `α_engine` = **`0.8000000`**; at `α_G*Power` = `0.8000093` |
| `G-014` | one sample, criterion, 1 tail, `N = 209`, `d = 0.75`, power `.85` | *Internal Math Error!* | `α = 6.54e-19`, `t = 9.7065409` | — |
| `G-091` | matched pairs, criterion, 2 tails, `N = 172`, `dz = 1.01`, power `.95` | *Internal Math Error!* | answers | — |
| `G-049`, `G-115`, `G-168`, `G-187`, `G-205`, `G-230` | criterion / compromise with `α` between `3.5e-10` and `4.8e-12` | differ from the engine from the 6th–7th significant digit | | |

Two things the arbitration shows:

* The engine's answer is exact: at its `α` the power is the requested value to
  all printed digits.
* G\*Power's printed critical *t* does not even correspond to G\*Power's own
  printed `α` (`8.1198649` vs the exact `t(1.32816e-12/2; 99) = 8.1198480`). The
  inaccuracy is in its far-tail central-*t* quantile, not only in the stopping
  tolerance of its root finder.

Above `α = 1e-9`, every recorded criterion and compromise result is
reproduced in every printed digit.

## The same at huge N

A tiny effect size drives the a-priori `N` into the billions (F-15). Power then
moves by about `1e-10` per participant, and G\*Power's `N` is not the exact
first design reaching the target:

| row | input | G\*Power | exact (40-digit `mpmath`) | engine |
|---|---|---|---|---|
| `D-44` | two groups, `d = 0.001`, `R = 2`, power `.8` | `N = 35 319 874`; exact power of its stopping split `0.799999997638` — **below target** | `35 319 876` (`0.800000019845`) | `35 319 876` |
| `D-43` | one sample, `d = 1e-4`, power `.95` | `N = 1 299 470 953` (`0.95000000595`) | `1 299 470 912` (`1 299 470 911` gives `0.94999999994`) | `1 299 470 911` — one short, power error `6e-11` |
| `D-31` | one sample, `d = 1e-5`, power `.8` | `N = 78 488 272 181`, *Actual power* `0.8000265` | not computed | `78 488 605 095` |

Finding these also exposed an engine defect: at `ν ≈ 1e11` the engine's
critical value was `2.7e-6` relative off (the incomplete beta loses
`log₁₀ ν` digits as `ν/(ν+t²) → 1`). It now returns the four-term
Cornish–Fisher quantile there, exact to `4e-16` (SPEC §4 item 6).

## Decision

The engine does **not** imitate the error. It reports the exact value and adds
a `warnings[]` entry whenever a criterion or compromise result has
`α < 1e-9` (`engine.GPOWER_ALPHA_FLOOR`), or an a-priori result has
`N > 1e7` (`engine.LARGE_N_WARNING`), saying that G\*Power prints a different
value there. `tests/test_gpower_observed.py` tolerates
a disagreement **only** in this region, and fails on any other.

## Verdict

**[GÖZLEM] F-14 — observed.** A documented, bounded region where the reference
program itself is inexact; outside it, agreement is exact.

## Re-run

```console
$ python tools/rea_campaign.py --set grid --only G-003 G-007 G-014
$ python tools/rea_report.py
```
