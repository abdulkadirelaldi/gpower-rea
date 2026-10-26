# E-008 — A negative effect size is a direction, and only the solvers absolutise it

| | |
|---|---|
| **Finding** | [F-08](../../SPEC.md#f-08--a-negative-effect-size-is-a-direction-not-an-error) |
| **Status** | `REA-OPEN` |
| **Method** | Sign probing across the five analysis types |
| **Target** | G\*Power 3.1.9.x, `t tests` |
| **Probe id** | `P-08` |

## Claim

* **Post hoc** uses the signed noncentrality. A one-tailed test with a
  negative effect size therefore reports power *below* `α`, and that is
  correct — it is the probability of rejecting in the stated direction when the
  truth lies the other way.
* **A priori, criterion and sensitivity** take the hypothesis direction from
  the sign of the supplied effect size, i.e. they solve with `|δ|`.
* Two-tailed analyses are sign-invariant throughout.

## Why this is not in the manual

The manual neither forbids a negative effect size nor explains what happens
when you supply one. Three behaviours are all defensible: reject the input,
silently absolutise it, or honour the sign. A reimplementation that picks the
wrong one produces either a spurious error for a legitimate input or a
silently wrong power number — and since the a-priori search is monotone in
`|δ|` but *not* in `δ`, honouring the sign in the a-priori search would make
the search non-monotone and hang or diverge.

This finding is marked `REA-OPEN` because the engine's choice is a design
decision taken for safety, not a measured behaviour, and the engine *says so*
on every affected output.

## Discriminating probe `P-08`

### Click path

`Test family = t tests` → `Statistical test = Means: Difference from constant
(one sample case)` → set `Effect size d` to a negative value → run each
`Type of power analysis` in turn.

### Rows

| row | analysis | inputs | prediction under "signed" | prediction under "absolutised" | prediction under "rejected" |
|---|---|---|---|---|---|
| `P-08-a` | post hoc, one tail | `d = -0.5`, `α = .05`, `N = 30` | power `≈ 7.7e-6` | power `0.8482542` | error dialog |
| `P-08-b` | post hoc, two tails | `d = -0.5`, `α = .05`, `N = 30` | power `0.7539647` | power `0.7539647` | error dialog |
| `P-08-c` | a priori, one tail | `d = -0.5`, `α = .05`, power `.80` | no solution / hang | `N = 27` | error dialog |

Row `P-08-b` is the control: it cannot discriminate, so a deviation there
indicates a setup problem.

### Observation

`probes/REA-RESULTS.md`, rows `P-08-a` … `P-08-c`.

## What the engine does, and how it tells you

Post hoc honours the sign exactly:

```console
$ gpower solve -t one-sample -s power -a 0.05 -e -0.5 --tails 1 -n 30 --json
  "noncentrality": -2.7386127875258306,
  "power": 7.733107252105853e-06
```

A priori absolutises, and records it:

```console
$ gpower solve -t one-sample -a 0.05 -p 0.8 -e -0.5 --tails 1 --json
  "sample_size": { "n": 27, "total": 27 },
  "warnings": [
    "negative effect size: |ES| used for the directional search (SPEC F-08)"
  ]
```

The warning travels through every layer: the CLI prints it under a `Warnings`
heading, the JSON keeps it in `warnings[]`, and the MCP server returns it
inside `result.warnings`, so an agent quoting the number also sees the caveat.

## Verdict

`REA-OPEN`. The engine's behaviour is explicit, documented and surfaced in
the output; row `P-08-a` settles which of the three candidates the GUI
implements. Should the probe contradict the choice, the fix is confined to
nine lines in `gpower_rea.engine.solve` (the `es_eff = abs(effect_size)` block).

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k negative_effect_size -q
```
