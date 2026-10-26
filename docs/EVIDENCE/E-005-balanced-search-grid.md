# E-005 — The balanced a-priori search enumerates *n per group*, so the total is always even

| | |
|---|---|
| **Finding** | [F-05](../../SPEC.md#f-05--balanced-a-priori-search-runs-over-n-per-group-not-total-n) |
| **Status** | `REA-BEHAVIOURAL` |
| **Method** | Search-space probing with a counter-example design |
| **Target** | G\*Power 3.1.9.x, `t tests` → *Means: Difference between two independent means (two groups)* |
| **Probe id** | `P-05` |

## Claim

With allocation ratio `1`, the a-priori analysis searches

```
n₁ = 2, 3, 4, …        n₂ = n₁
```

and returns the first `n₁` whose power reaches the target. It does **not**
search total `N` and then split it. Therefore:

> a balanced a-priori two-group *t* test never reports an odd total sample size.

## Why this is not in the manual

The manual says the tool computes "the required sample size" and shows an
output panel with three fields (`Sample size group 1`, `Sample size group 2`,
`Total sample size`). It never states what the search space is. Both
candidate search spaces are consistent with the manual's prose, and both
produce correct-looking output — but they disagree on real inputs, and the
disagreement is *not* a rounding artefact.

This is the finding most likely to be missed by a reimplementation, because
the natural way to write the code is to search total `N`.

## Why it is observable: a counter-example design

If the search ran over total `N`, then for some inputs an odd total would be
returned, because an unequal split `(n, n+1)` can already clear the target
while `(n, n)` does not. Such inputs exist and are easy to hit:

| inputs (α = 0.05, two tails) | `(n, n)` | power | `(n, n+1)`, odd `N` | power | reported by the claim |
|---|---|---|---|---|---|
| `d = 0.30`, target `0.80` | (175,175) | `0.7991335` | (175,176), `N = 351` | **`0.8002560`** ✔ | `N = 352` |
| `d = 0.42`, target `0.90` | (120,120) | `0.8997603` | (120,121), `N = 241` | **`0.9009455`** ✔ | `N = 242` |

In both rows an odd total **already satisfies the requirement**, and a
total-`N` search would have found it. If the tool nevertheless reports the even
total, the search space is per-group. If it reports 351 / 241, the search
space is the total.

Two control rows where the two candidates agree (so a mismatch there would
indicate operator error rather than a real difference):

| inputs | `(n, n)` | `(n-1, n)` | both candidates report |
|---|---|---|---|
| `d = 0.50`, target `0.95` | (105,105) `0.9501287` | (104,105) `0.9492249` ✘ | `N = 210` |
| `d = 0.62`, target `0.85` | (48,48) `0.8522730` | (47,48) `0.8485032` ✘ | `N = 96` |

## The counter-examples are not an artefact of our search code

A fair objection to the table above: those numbers come from this engine, so a
bug in *our* integer search could manufacture a counter-example that does not
exist. The objection is answerable without using our search at all.

`statsmodels.stats.power.TTestIndPower.solve_power` returns the **continuous**
per-group `n`, and its `power()` evaluates an unbalanced split directly. Both
are third-party code. Under the two candidate grids the integer answer is then
`2·⌈n_frac⌉` (per-group search) versus the smallest sufficient total
(total-`N` search), and statsmodels' own power function says which one clears
the target:

| `d` | target | statsmodels `n_frac` | per-group grid | odd split | statsmodels power of the odd split | odd suffices? |
|---|---|---|---|---|---|---|
| 0.20 | 0.80 | `393.4057` | `N = 788` | (393,394) `N = 787` | `0.8000936` | **yes** |
| 0.25 | 0.80 | `252.1275` | `N = 506` | (252,253) `N = 505` | `0.8005794` | **yes** |
| 0.30 | 0.80 | `175.3847` | `N = 352` | (175,176) `N = 351` | `0.8002560` | **yes** |
| 0.42 | 0.90 | `120.1003` | `N = 242` | (120,121) `N = 241` | `0.9009455` | **yes** |
| 0.45 | 0.95 | `129.3112` | `N = 260` | (129,130) `N = 259` | `0.9502700` | **yes** |
| 0.35 | 0.90 | `172.5157` | `N = 346` | (172,173) `N = 345` | `0.8999715` | no (control) |
| 0.50 | 0.95 | `104.9279` | `N = 210` | (104,105) `N = 209` | `0.9492249` | no (control) |
| 0.62 | 0.85 | `47.6941`  | `N = 96`  | (47,48) `N = 95`    | `0.8485031` | no (control) |

Every row agrees with the engine-computed table above, from entirely separate
code. Note also that `d = 0.20, power = .80 → N = 788` is the figure commonly
quoted for that design, which is itself a small corroboration of F-05 and F-06.

### How often does the grid choice matter? Half the time.

Sweeping `d` from `0.100` to `1.200` against power `{.80, .90, .95}` — 474
settings, all evaluated with statsmodels — the odd split already suffices in

```
  odd split already sufficient (the grids differ) : 238
  odd split insufficient       (the grids agree)  : 236
  -> the two candidate grids disagree on 50.2% of settings
```

So this is not an edge case to be waved away as rounding: on a balanced
a-priori two-group *t* test, which search space the tool uses changes the
answer about half the time. That is what makes the finding worth a probe
rather than a footnote.

`tests/test_reference_statsmodels_f05.py` re-derives this table on every run,
so the claim cannot drift.

## Discriminating probe `P-05`

### Click path

`Test family = t tests` → `Statistical test = Means: Difference between two
independent means (two groups)` → `Type of power analysis = A priori` →
`Tail(s) = Two`, `Allocation ratio N2/N1 = 1` → enter `Effect size d`,
`α err prob`, `Power` → **Calculate** → read `Total sample size`.

### Rows

| row | `d` | target power | predicted (per-group search) | predicted (total-`N` search) |
|---|---|---|---|---|
| `P-05-a` | 0.30 | 0.80 | `N = 352` | `N = 351` |
| `P-05-b` | 0.42 | 0.90 | `N = 242` | `N = 241` |
| `P-05-c` | 0.50 | 0.95 | `N = 210` | `N = 210` (control) |
| `P-05-d` | 0.62 | 0.85 | `N = 96` | `N = 96` (control) |

### Observation

`probes/REA-RESULTS.md`, rows `P-05-a` … `P-05-d`.

## Parity as a cheap bulk check

The parity consequence is a much weaker claim than the search-space claim, but
it needs no counter-example hunting and can be checked in bulk: run any grid of
balanced a-priori analyses and confirm every total is even. The engine is
locked to this:

```python
# tests/test_engine_invariants.py
def test_balanced_a_priori_never_returns_an_odd_total():
    for d in (0.2, 0.33, 0.5, 0.77, 1.1):
        for pw in (0.8, 0.9, 0.95):
            total = solve("ttest-indep-means", "n", alpha=0.05, power_target=pw,
                          effect_size=d, tails=2,
                          allocation_ratio=1.0).sample_size["total"]
            assert total % 2 == 0
```

## Implementation consequence

The engine therefore searches a *step index* rather than a sample size, and the
mapping from step to allocation is a pluggable rule
(`gpower_rea.engine.ALLOCATION_RULES`). The balanced case is the `ratio = 1`
specialisation of `n1-grid`; see E-009 for the unbalanced case.

## Verdict

Implemented as per-group search; counter-example rows above are the
discriminator; parity consequence locked by test.

## Re-run

```console
$ gpower solve -t indep -a 0.05 -p 0.80 -e 0.30 --json   # expect total 352
$ gpower solve -t indep -s power -a 0.05 -e 0.30 --n1 175 --n2 176 --json
$ python -m pytest tests/test_engine_invariants.py -k odd_total -q
```
