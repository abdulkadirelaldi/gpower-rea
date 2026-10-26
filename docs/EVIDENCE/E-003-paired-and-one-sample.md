# E-003 — Matched pairs counts *pairs*; the two entries are numerically identical

| | |
|---|---|
| **Finding** | [F-03](../../SPEC.md#f-03--one-sample-and-matched-pairs-ν--n---1-δ--es√n) |
| **Status** | `[TÜRETİLMİŞ + GÖZLEM]` — observed on G\*Power 3.1.9.6 (macOS) |
| **Method** | Cross-entry identity probing |
| **Target** | G\*Power 3.1.9.x, `t tests` |
| **Probe id** | `P-03` |

## Claim

```
Means: Difference from constant (one sample case)     ν = N - 1,  δ = d  · √N
Means: Difference between two dependent means         ν = N - 1,  δ = dz · √N
```

and `N` is the number of **pairs** (participants), not the number of
observations.

## Why this is not settled by the manual

The manual gives the matched-pairs effect size as `dz = μ_diff / σ_diff` and
calls the sample-size field "Total sample size". For a design in which each
participant is measured twice, "total sample size" is genuinely ambiguous in
English — 54 participants or 108 measurements? The field label does not say,
and the surrounding text does not disambiguate. Getting it wrong doubles the
reported requirement, which is the single most consequential misreading
available in this family.

## Derivation

The two menu entries have the same `(ν, δ)` map. If *one* of them counted
observations while the other counted units, then for identical numeric input
they would return different `ν` — `N-1` versus `2N-1` — and therefore
different power. They do not.

This is testable without the GUI at all, as an internal consistency property
of any implementation that claims to reproduce the family:

```python
# tests/test_engine_invariants.py
def test_one_sample_and_paired_agree():
    for d in (0.2, 0.5, 0.9):
        for tails in (1, 2):
            a = solve("ttest-one-sample",   "n", alpha=0.05, power_target=0.9,
                      effect_size=d, tails=tails).sample_size["total"]
            b = solve("ttest-paired-means", "n", alpha=0.05, power_target=0.9,
                      effect_size=d, tails=tails).sample_size["total"]
            assert a == b
```

Combined with the one-sample case — where there is no ambiguity, since each
participant contributes one observation — the pair count reading is forced.

## Discriminating probe `P-03`

### Click path

Run both entries with identical numbers and compare the *whole* output panel.

`Test family = t tests` → `Statistical test = Means: Difference from constant
(one sample case)` → `A priori` → `Tail(s) = Two`, `Effect size d = 0.5`,
`α = 0.05`, `Power = 0.95` → **Calculate**. Then switch
`Statistical test` to *Means: Difference between two dependent means (matched
pairs)*, enter `Effect size dz = 0.5` with the same `α` and power, and
**Calculate** again.

### Predictions

| row | reading of "Total sample size" | predicted output |
|---|---|---|
| `P-03-a` | **pairs** (claimed) | `N = 54`, `Df = 53`, `δ = 3.6742346`, actual power `0.9502120` |
| `P-03-b` | observations | `N = 27`, `Df = 26` (power at 27 pairs is only `0.7058239`) |

and the two menu entries must agree with each other on every printed field.

### Observation

`probes/REA-RESULTS.md`, rows `P-03-a` / `P-03-b`.

## Engine output

```console
$ gpower solve -t one-sample -a 0.05 -p 0.95 -e 0.5 --json
$ gpower solve -t paired     -a 0.05 -p 0.95 -e 0.5 --json
```

Both report `total = 54`, `df = 53`, `noncentrality = 3.6742346`,
`power = 0.9502120` — byte-identical JSON apart from the `test`, `test_title`
and `effect_size.name` fields.

## Implementation note for a clean-room author

Do not model the matched-pairs test as a two-group test with `n₁ = n₂ = N`.
The reduction in `σ_diff` from the pre-post correlation is already absorbed
into `dz` by the effect-size calculator (see E-011); applying it twice is the
other common error.

## [GÖZLEM] Observation — G\*Power 3.1.9.6

Read off the GUI's *Output parameters* panel by `tools/rea_campaign.py`
(raw records in [`probes/observations/`](../../probes/observations/)). The
predictions were registered in `probes/probe_worksheet.csv` before any
observation was made, and are shown unchanged.

| probe | read | G\*Power printed | pre-registered engine prediction | competing prediction | verdict |
|---|---|---|---|---|---|
| `P-03-a` | N / Df / Actual power | `54 / 53 / 0.9502120` | `54 / 53 / 0.9502120` | `27 (if the field counts observations)` | **SUPPORTS** |
| `P-03-b` | whole output panel | `identical across the two menu entries` | `identical across the two menu entries` | `different Df if one entry counted observations` | **SUPPORTS** |

Every other field G\*Power printed for these rows also matches the current
engine — `tests/test_gpower_observed.py` checks each one.

## Verdict

**[GÖZLEM] F-03 — observed.** *Total sample size* counts pairs: `N = 54`, `Df = 53`, and the matched-pairs and one-sample entries print identical output panels for the same effect size.

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k one_sample_and_paired -q
```
