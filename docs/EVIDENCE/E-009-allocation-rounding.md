# E-009 — Unbalanced allocation: G\*Power searches even totals and tests the unrounded split

| | |
|---|---|
| **Finding** | [F-09](../../SPEC.md#f-09--allocation-ratio-rounding) |
| **Status** | `[REA] REFUTED → CORRECTED` — both v1.1 candidates refuted; the observed rule reproduces every row |
| **Method** | Pre-registered discriminating probes, then a ratio sweep, then a fine power sweep to expose the stopping test |
| **Target** | G\*Power 3.1.9.6 (macOS), `t tests` → *Means: Difference between two independent means (two groups)*, *A priori* |
| **Probe ids** | `P-09-a…d` (pre-registered), `A-000…A-047` (ratio sweep), `S-000…S-040` (power sweep), plus every `indep` a-priori row of the grid `G-*` |

## [REA] Claim

```
for N = 4, 6, 8, …                       even totals only, at every ratio R
    m₁ = N/(1+R),  m₂ = N·R/(1+R)         unrounded
    stop at the first N with power(ν = N-2, δ = d·sqrt(m₁·m₂/N)) ≥ target

report  n₁ = round_half_up(N/(1+R)),  n₂ = N - n₁
        Actual power recomputed at (n₁, n₂)  — may be below the target
```

None of this is in the manual. It introduces the *Allocation ratio N2/N1* field
and says nothing about how a ratio that does not divide `N` is resolved, in
which order the search runs, or on which design the stopping test is made.

## Step 1 — the pre-registered probes refuted both candidates

SPEC v1.1 offered `n1-grid` (default) and `total-grid`, with these predictions,
committed before any observation:

| probe | `R` | G\*Power printed `n₁ / n₂ / N / Actual power` | `n1-grid` predicted | `total-grid` predicted |
|---|---|---|---|---|
| `P-09-a` | 0.5 | `157 / 79 / 236 / 0.9505146` | `157 / 79 / 236` ✔ | `157 / 79 / 236` ✔ |
| `P-09-b` | 1.5 | `88 / 132 / 220 / 0.9512569` | `88 / 132 / 220` ✔ | `88 / 131 / 219` ✘ |
| `P-09-c` | 2.0 | `79 / 157 / 236 / 0.9505146` | `79 / 158 / 237` ✘ | `79 / 157 / 236` ✔ |
| `P-09-d` | 3.0 | `70 / 210 / 280 / 0.9505630` | `70 / 210 / 280` ✔ | `70 / 208 / 278` ✘ |

`harvest.py` stamps F-09 *NEITHER CANDIDATE*: each rule is contradicted by a
row the other gets right ([`probes/REA-RESULTS.md`](../../probes/REA-RESULTS.md)).

## Step 2 — the displayed split is always the total-grid split of its own total

The 48-row ratio sweep `A-*` (`d ∈ {0.3, 0.5, 0.8}`, power `{0.80, 0.95}`,
`R ∈ {0.3, 0.5, 1.25, 1.5, 2, 2.5, 3, 4}`) showed one regularity without
exception: **`n₁ = round_half_up(N/(1+R))`, `n₂ = N − n₁`** for the `N`
G\*Power printed. `A-022` (`R = 3`, `N = 170`, `N/(1+R) = 42.5`) prints
`n₁ = 43`, so the rounding is half-away-from-zero. The open question became:
*how is N chosen?* In about half of the rows `N` was one larger than the
smallest total whose split already reaches the target.

## Step 3 — a fine power sweep exposes the stopping test

Holding `d = 0.5`, `α = 0.05`, two tails, `R = 1.5` and stepping the target
power by `0.0005` from `0.940` to `0.960` (`S-000…S-040`) gives a staircase:

| target | G\*Power `n₁ / n₂` | `N` | Actual power |
|---|---|---|---|
| 0.9400 | 83 / 125 | 208 | 0.9400041 |
| 0.9405 – 0.9420 | 84 / 126 | 210 | 0.9421692 |
| 0.9425 – 0.9440 | 85 / 127 | 212 | 0.9442602 |
| 0.9445 – 0.9455 | 86 / 128 | 214 | 0.9462795 |
| **0.9460** – 0.9475 | **86 / 130** | **216** | 0.9474957 |
| 0.9480 – **0.9495** | 87 / 131 | 218 | **0.9494095** |
| 0.9500 – 0.9510 | 88 / 132 | 220 | 0.9512569 |
| … | … | 222, 224, 226, 228, 230, 232 | … |

Two facts settle it:

1. **Every total is even**, whatever the ratio. The search runs over even
   totals — exactly as F-05 found for `R = 1`, which is now seen to be a special
   case rather than a separate rule.
2. At target `0.9460` G\*Power reports `N = 216`, although the rounded split of
   `214`, `(86, 128)`, has power `0.9462795 ≥ 0.9460`. The stopping test cannot
   be on the reported split. On the **unrounded** split `(85.6, 128.4)` the
   power is below `0.9460`, and at `216` it is above — the stopping test is made
   there.

The same sweep shows the consequence F-06 had wrong: at target `0.9495` the
reported design `87 / 131` has *Actual power* **`0.9494095`, below the target**.

## Step 4 — the rule against every row, and against the alternatives

`python tools/fit_allocation.py` replays every a-priori two-group observation
under seven candidate rules. A rule scores a row only if `n₁`, `n₂` **and** the
seven-decimal *Actual power* all match.

| rule | all 119 rows | 108 rows with `R ≠ 1` | 48-row sweep `A-*` |
|---|---|---|---|
| **even-total (SPEC v1.2)** | **119** | **108** | **48** |
| even `N`, rounded-split check | 96 | 85 | 35 |
| ceil each group of the continuous solution | 68 | 57 | 23 |
| every `N`, unrounded check | 67 | 59 | 28 |
| every `N`, `n₁` floored | 63 | 55 | 24 |
| `total-grid` (v1.1 alternative) | 56 | 48 | 21 |
| `n1-grid` (v1.1 default) | 55 | 44 | 19 |

(Refused inputs and the `N > 1e7` rows of F-14 are excluded. See also
[VALIDATION §0](../VALIDATION.md#0-against-the-real-gpower--435-recorded-runs).)

## How much it matters

The v1.1 default disagreed with G\*Power on more than half of all unbalanced
designs, always by one or two participants. On hidden test vectors with
`R ≠ 1` that alone would have cost the exact-`N` gate.

## Implementation

`gpower_rea.engine._alloc_even_total` (reported split) and
`_even_total_check` (stopping-test split). The refuted rules remain selectable
as `--allocation-rule n1-grid` / `total-grid`, only to reproduce v1.1 output.

## Verdict

**[REA] F-09 — observed.** The even-total rule reproduces every recorded
a-priori two-group result of G\*Power 3.1.9.6, in every printed field; both
rules of v1.1 are refuted.

## Re-run

```console
$ python tools/rea_campaign.py --set alloc      # needs G*Power + macOS Accessibility
$ python tools/rea_campaign.py --set sweep
$ python tools/fit_allocation.py                # offline, from the recorded readings
$ python -m pytest tests/test_gpower_observed.py
```
