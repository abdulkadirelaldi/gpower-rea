# E-006 — `≥`, not `>`, and "Actual power" is recomputed at the integer design

| | |
|---|---|
| **Finding** | [F-06](../../SPEC.md#f-06--minimality-and-actual-power-is-recomputed) |
| **Status** | `REA-BEHAVIOURAL` |
| **Method** | Boundary probing + output-field semantics |
| **Target** | G\*Power 3.1.9.x, `t tests` |
| **Probe id** | `P-06` |

## Claim

Two separate behaviours:

1. **Minimality with a non-strict comparison.** The a-priori result is the
   smallest design on the search grid (E-005, E-009) satisfying
   `power ≥ target`. The comparison is non-strict: a design whose power equals
   the target exactly is accepted.
2. **Actual power is a recomputation.** The output panel reports
   *Actual power*, obtained by evaluating the power formula at the returned
   integer design. It is **not** the requested power echoed back.

## Why this is not in the manual

The manual's output panel is simply labelled. It does not say that the
reported power differs from the requested power, nor by how much, nor that it
is the result of a second evaluation. A reimplementation that echoes the
target back is wrong in a way that is easy to miss for a whole release cycle:
the sample size is right and only the power field is off, usually in the third
decimal.

The non-strict comparison is likewise undocumented and matters at boundaries
(see the margin table below).

## Discriminating probe `P-06`

### Click path

`Test family = t tests` → `Statistical test = Means: Difference between two
independent means (two groups)` → `A priori` → `Tail(s) = Two`,
`Effect size d = 0.5`, `α = 0.05`, `Power = 0.95`, `Allocation ratio = 1` →
**Calculate**.

### Predictions

| row | field | if power is recomputed (claimed) | if the target is echoed |
|---|---|---|---|
| `P-06-a` | `Total sample size` | `210` | `210` |
| `P-06-b` | `Actual power` | `0.9501287` | `0.9500000` |

The seven printed decimals make this unambiguous. The design at one step
below — `n₁ = n₂ = 104` — yields `0.9483147`, confirming 210 is minimal.

Boundary rows for behaviour (1), chosen so that the achieved power sits
extremely close to the target:

| row | test | inputs | predicted `N` | predicted actual power | margin over target |
|---|---|---|---|---|---|
| `P-06-c` | one sample | `d = 0.162`, `α = .05`, power `.80`, two tails | `301` | `0.8000014` | `1.4e-6` |
| `P-06-d` | one sample | `d = 0.5`, `α = .05`, power `.80`, two tails | `34` | `0.8077775` | `7.8e-3` |

Row `P-06-c` is the tightest margin found by sweeping `d` over
`[0.100, 1.200]` in steps of `0.001`. An implementation using a strict `>`
comparison, or applying an epsilon slack of more than `1.4e-6`, returns `302`
for that row. The engine returns `301`.

### Observation

`probes/REA-RESULTS.md`, rows `P-06-a` … `P-06-d`.

## Engine output

```console
$ gpower solve -t indep -a 0.05 -p 0.95 -e 0.5 --json
  "power": 0.950128703388722,          <- actual, recomputed
  "target": { "power": 0.95 },         <- what was asked for
  "sample_size": { "n1": 105, "n2": 105, "total": 210 }

$ gpower solve -t one-sample -a 0.05 -p 0.80 -e 0.162 --json
  "sample_size": { "n": 301, "total": 301 },
  "power": 0.8000013825646128
```

The result object keeps the two numbers in different fields
(`power` vs `target.power`) precisely so that collapsing them is impossible,
and the text renderer labels the a-priori case `Actual power` to match the GUI.

## Consequence for conformance testing

Because the achieved power can sit within `1.4e-6` of the target, a
conformance harness must not compare powers with a tolerance looser than that
in the direction that would mask an off-by-one in `N`. The tolerance adopted
in [SPEC §F-12](../../SPEC.md#f-12--boundary-behaviour-and-reported-precision)
is `5e-7` on power and *exact* on `N`.

## Verdict

Both behaviours implemented; the `0.9501287` vs `0.9500000` row is the
discriminator for (2), and the `d = 0.162` row for (1).

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k apriori_is_minimal -q
$ gpower selftest
```
