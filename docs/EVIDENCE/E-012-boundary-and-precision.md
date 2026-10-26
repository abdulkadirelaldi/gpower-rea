# E-012 — No epsilon slack at the boundary; display rounding is display only

| | |
|---|---|
| **Finding** | [F-12](../../SPEC.md#f-12--boundary-behaviour-and-reported-precision) |
| **Status** | `[GÖZLEM]` — observed on G\*Power 3.1.9.6 (macOS) |
| **Method** | Boundary sweep to locate the tightest admissible margin |
| **Target** | G\*Power 3.1.9.x, `t tests` |
| **Probe id** | `P-12` |

## Claim

1. The a-priori acceptance test is `power ≥ target` in double precision with
   **no epsilon slack** and **no rounding of `power` before the comparison**.
2. The seven-decimal display is a formatting step applied *after* the search.
3. Consequently, a conformance harness must compare integer sample sizes
   **exactly** and powers to no looser than `5e-7`.

## Why this is not in the manual

Nothing in the documentation discusses tie-breaking or internal precision, and
the GUI shows seven decimals, which invites the assumption that the comparison
happens on the displayed value. It does not, and the difference is a whole
participant on boundary cases.

Three plausible implementations exist:

| candidate | behaviour at the boundary |
|---|---|
| **A** (claimed) | compare unrounded `power ≥ target` |
| B | compare `round(power, 7) ≥ target` |
| C | compare `power ≥ target - ε` for some small `ε` |

B and C differ from A only when the achieved power sits within `~5e-8` (B) or
`~ε` (C) of the target — so you have to go looking for such a case.

## Discriminating probe `P-12`

A sweep of `d` over `[0.100, 1.200]` in steps of `0.001` for the one-sample
test (`α = 0.05`, target power `0.80`, two tails) locates the tightest margin
in that range:

| row | inputs | predicted `N` | predicted actual power | margin over target |
|---|---|---|---|---|
| `P-12-a` | one sample, `d = 0.162`, `α = .05`, power `.80`, two tails | `301` | `0.8000014` | `1.38e-6` |

Candidate C with `ε > 1.4e-6` returns `300` instead; candidate B agrees with A
here (the margin is above `5e-8`) and so this row discriminates A/B jointly
against C. For a row that separates A from B one needs a margin below `5e-8`;
`tools/probe_plan.py` searches for one on demand with
`python tools/probe_plan.py --hunt-boundary` and emits it as `P-12-b` when
found. (Such cases exist but are sparse: the a-priori margin is a
pseudo-random draw from roughly `[0, 1.3e-2]`, so a margin below `5e-8` occurs
about once in 2.6e5 parameter settings.)

### Click path

`Test family = t tests` → `Statistical test = Means: Difference from constant
(one sample case)` → `A priori` → `Tail(s) = Two`, `Effect size d = 0.162`,
`α err prob = 0.05`, `Power = 0.80` → **Calculate** → read `Total sample size`
and `Actual power`.

### Observation

`probes/REA-RESULTS.md`, rows `P-12-a` (and `P-12-b` if hunted).

## Engine output

```console
$ gpower solve -t one-sample -a 0.05 -p 0.80 -e 0.162 --json
  "sample_size": { "n": 301, "total": 301 },
  "power": 0.8000013825646128,
  "target": { "power": 0.8 }

$ gpower solve -t one-sample -s power -a 0.05 -e 0.162 -n 300 --json
  "power": 0.7988...   <- below target, so 301 is minimal
```

The engine compares the raw double:

```python
# gpower_rea/engine.py
def attains(step: int) -> bool:
    ...
    pw, _ = _power_from_ncp(alpha, df, ncp, tails)
    return pw >= power_target          # no epsilon, no rounding
```

## The reason this finding exists at all

It is the finding that makes the conformance contract meaningful. Without it,
"does the engine agree with G\*Power?" has no answer, because the comparison
tolerance is undefined. With it, the contract in
[SPEC §5](../../SPEC.md#5-conformance) is checkable:

* integer `N`: **exact** equality;
* `power`: `|Δ| ≤ 5e-7`, which is one unit in the last printed decimal, and
  which is `360×` tighter than the tightest observed margin, so a power
  comparison can never mask an off-by-one in `N`.

Both tolerances are what `gpower selftest` and `gpower batch --expect` apply,
and what the 401 bundled vectors are validated to in
`tests/test_reference_scipy.py`.

## Numerical headroom

For the contract to be meaningful the engine's own numerical error must be far
below `5e-7`. Measured worst-case deviations
([docs/VALIDATION.md](../VALIDATION.md)):

| quantity | engine error | headroom vs `5e-7` |
|---|---|---|
| noncentral `t` CDF | `1.7e-14` | `3e7 ×` |
| central `t` quantile | `3.8e-15` | `1e8 ×` |
| quadrature mass closure | `2.1e-14` | `2e7 ×` |

So the 401/401 exact-`N` agreement in
[docs/VALIDATION.md](../VALIDATION.md) is not a tolerance artefact.

## [GÖZLEM] Observation — G\*Power 3.1.9.6

Read off the GUI's *Output parameters* panel by `tools/rea_campaign.py`
(raw records in [`probes/observations/`](../../probes/observations/)). The
predictions were registered in `probes/probe_worksheet.csv` before any
observation was made, and are shown unchanged.

| probe | read | G\*Power printed | pre-registered engine prediction | competing prediction | verdict |
|---|---|---|---|---|---|
| `P-12-a` | N / Actual power | `301 / 0.8000014` | `301 / 0.8000014` | `300 (epsilon slack > 1.4e-6)` | **SUPPORTS** |

Every other field G\*Power printed for these rows also matches the current
engine — `tests/test_gpower_observed.py` checks each one.

## Verdict

**[GÖZLEM] F-12 — observed.** `N = 301` with *Actual power* `0.8000014`: the design is accepted with a margin of `1.4e-6`, so no epsilon slack of that size or larger is applied.

## Re-run

```console
$ gpower selftest --verbose
$ python -m pytest tests/test_engine_invariants.py -k apriori_is_minimal -q
```
