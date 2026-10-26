# E-009 — Unbalanced allocation: which grid, and which rounding

| | |
|---|---|
| **Finding** | [F-09](../../SPEC.md#f-09--allocation-ratio-rounding) |
| **Status** | `REA-OPEN` — both candidates implemented, discriminator specified |
| **Method** | Differential probing over the allocation ratio |
| **Target** | G\*Power 3.1.9.x, `t tests` → *Means: Difference between two independent means (two groups)* |
| **Probe id** | `P-09` |

## Claim

With `R = N₂/N₁ ≠ 1` there are two self-consistent search grids:

| rule | grid | group sizes | property |
|---|---|---|---|
| **`n1-grid`** (engine default) | `n₁ = 2, 3, 4, …` | `n₂ = round_half_up(R·n₁)` | reproduces `R` exactly whenever `R·n₁` is an integer |
| `total-grid` | `N = 4, 5, 6, …` | `n₁ = round_half_up(N/(1+R))`, `n₂ = N - n₁` | minimises total `N`, at the cost of a slightly different realised ratio |

and rounding is **half away from zero** (`2.5 → 3`), not IEEE/banker's
round-half-to-even (`2.5 → 2`).

## Why this is not in the manual

The manual introduces the `Allocation ratio N2/N1` field and says the group
sizes are adjusted accordingly. It does not say what happens when `R·n₁` is
not an integer, nor whether the optimisation target is the total or the
per-group size.

**The two readings disagree most of the time.** Measured over a 378-setting
sweep (`R ∈ {0.5, 1.5, 2, 2.5, 3, 4}` × `d ∈ [0.20, 1.20]` in steps of `0.05`
× power `{.80, .90, .95}`), with both rules implemented and run:

| `R` | settings where the two rules give a different total |
|---|---|
| 0.5 | 12.7 % |
| 1.5 | 76.2 % |
| 2.0 | 88.9 % |
| 2.5 | 90.5 % |
| 3.0 | 90.5 % |
| 4.0 | 95.2 % |
| **overall** | **75.7 %** |

Size of the disagreement, over all 378 settings: identical in 24.3 %,
1 participant in 34.9 %, 2 in 38.6 %, 3 in 2.1 %.

A difference that appears in three settings out of four is not a rounding
footnote — on an unbalanced design it changes the recruitment target, and
therefore the budget and the ethics submission, most of the time. That is why
this is a finding with a probe rather than a comment in the code.

Reproduce with `python -m pytest tests/test_allocation_rule_rates.py -q`.

Rounding mode is a second, independent undocumented choice: Python, NumPy,
IEEE-754 and most SQL engines default to half-to-even, so an implementer who
reaches for the language built-in gets a different answer from one who writes
`floor(x + 0.5)`, whenever `R·n₁` lands exactly on `.5`.

## Discriminating probe `P-09`

The two grids are measurably different. Engine-computed predictions
(`α = 0.05`, two tails, `d = 0.5`, target power `0.95`):

| row | `R` | `n1-grid` (default) | `total-grid` | discriminates? |
|---|---|---|---|---|
| `P-09-a` | 0.5 | `n₁=157, n₂=79, N=236`, power `0.9505146` | `n₁=157, n₂=79, N=236`, power `0.9505146` | **no** (control) |
| `P-09-b` | 1.5 | `n₁=88, n₂=132, N=220`, power `0.9512569` | `n₁=88, n₂=131, N=219`, power `0.9506900` | **yes** |
| `P-09-c` | 2.0 | `n₁=79, n₂=158, N=237`, power `0.9509116` | `n₁=79, n₂=157, N=236`, power `0.9505146` | **yes** |
| `P-09-d` | 3.0 | `n₁=70, n₂=210, N=280`, power `0.9505630` | `n₁=70, n₂=208, N=278`, power `0.9501093` | **yes** |

Rows `P-09-b/c/d` separate the candidates by `1`, `1` and `2` participants
respectively, and separate the reported power in the fourth decimal — so even
a printed-power observation settles it, without needing the group sizes.

Note the structural signature: under `n1-grid` the realised ratio `n₂/n₁` is
*exactly* `R` in all three rows (132/88 = 1.5, 158/79 = 2, 210/70 = 3); under
`total-grid` it is not (131/88 = 1.4886, 157/79 = 1.9873, 208/70 = 2.9714).
**If the GUI's two group sizes are in exact integer proportion `R`, the grid is
per-group.** That is the cheapest single observation in this file.

The signature is clean across the whole sweep. A sample of worked instances,
one per ratio, all at `α = 0.05`, two tails:

| `R` | `d` | target | `n1-grid` | realised ratio | `total-grid` | realised ratio |
|---|---|---|---|---|---|---|
| 0.5 | 0.25 | .80 | 379 / 190, `N = 569` | `0.5013` | 379 / 189, `N = 568` | `0.4987` |
| 1.5 | 0.20 | .90 | 439 / 659, `N = 1098` | `1.5011` | 439 / 658, `N = 1097` | `1.4989` |
| 2.0 | 0.20 | .90 | 395 / 790, `N = 1185` | **`2.0000`** | 395 / 789, `N = 1184` | `1.9975` |
| 2.5 | 0.20 | .80 | 276 / 690, `N = 966` | **`2.5000`** | 276 / 689, `N = 965` | `2.4964` |
| 3.0 | 0.20 | .80 | 263 / 789, `N = 1052` | **`3.0000`** | 263 / 787, `N = 1050` | `2.9924` |
| 4.0 | 0.20 | .80 | 246 / 984, `N = 1230` | **`4.0000`** | 246 / 982, `N = 1228` | `3.9919` |

Where `R` is an integer the `n1-grid` ratio is exact to every digit; the
`total-grid` ratio never is. `R = 0.5` and `R = 1.5` are the weak rows —
`R·n₁` is a half-integer for odd `n₁`, so neither rule can hit the ratio
exactly — which is why the probe table above uses `R = 2` as its primary
discriminator and treats `R = 0.5` as a control.

### Rounding-mode rows

Pick `R` and a target so that `R·n₁` lands on a half-integer at the solution.

| row | inputs | `round_half_up` | `round_half_even` |
|---|---|---|---|
| `P-09-e` | `R = 1.5`, `d = 0.5`, `α = .05`, power `.95` | `n₁ = 88 → n₂ = 132` | `n₁ = 88 → n₂ = 132` (even `n₁`: no split) |
| `P-09-f` | `R = 1.5`, odd `n₁` at the solution | `n₂ = ⌈1.5·n₁⌉` | `n₂ = ⌊1.5·n₁⌋` when `⌊1.5·n₁⌋` is even |

Row `P-09-f` requires searching for a parameter setting whose solution has odd
`n₁`; `tools/probe_plan.py` emits a concrete instance.

### Click path

`Test family = t tests` → `Statistical test = Means: Difference between two
independent means (two groups)` → `A priori` → `Tail(s) = Two`,
`Effect size d = 0.5`, `α err prob = 0.05`, `Power = 0.95`,
`Allocation ratio N2/N1 = …` → **Calculate** → read all three sample-size
fields *and* `Actual power`.

### Observation

`probes/REA-RESULTS.md`, rows `P-09-a` … `P-09-f`.

## How the ambiguity is handled rather than hidden

Both rules are first-class in the engine, selectable per call, and the active
rule is reported in every result:

```console
$ gpower solve -t indep -a .05 -p .95 -e .5 --ratio 2 --json
  "sample_size": { "n1": 79, "n2": 158, "total": 237,
                   "allocation_ratio": 2.0, "actual_ratio": 2.0 },
  "engine": { "allocation_rule": "n1-grid", ... }

$ gpower solve -t indep -a .05 -p .95 -e .5 --ratio 2 \
      --allocation-rule total-grid --json
  "sample_size": { "n1": 79, "n2": 157, "total": 236, ... }
```

Invariants that hold under both rules, and are tested:

* both return a design whose power meets the target
  (`tests/.../test_total_grid_never_needs_more_than_n1_grid`);
* `total-grid` never needs more participants than `n1-grid` (same test);
* `n1-grid` reproduces `R` exactly (`test_n1_grid_rule_reproduces_the_ratio_exactly`).

## Verdict

`REA-OPEN`. Default `n1-grid`, chosen because the exact-integer-proportion
signature is what published unbalanced G\*Power outputs show. One probe row
(`P-09-c`) flips the default if the observation disagrees, and flipping it is a
one-word change to `DEFAULT_ALLOCATION_RULE` — no other code moves. The 24
unbalanced rows in the bundled vector set carry `ratio` explicitly so that a
re-stamp regenerates them cleanly.

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k "grid or ratio" -q
$ python tools/make_vectors.py --check
```
