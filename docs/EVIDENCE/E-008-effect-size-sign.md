# E-008 — A negative effect size: direction, not a wrong-way test

| | |
|---|---|
| **Finding** | [F-08](../../SPEC.md#f-08--a-negative-effect-size-is-a-direction-not-an-error) |
| **Status** | `[GÖZLEM: ÇÜRÜTÜLDÜ → DÜZELTİLDİ]` — v1.1's post-hoc rule refuted; observed rule implemented |
| **Method** | Pre-registered discriminating probes, then a sign sweep across tests and analyses |
| **Target** | G\*Power 3.1.9.6 (macOS), `t tests`, all entries that accept a signed effect size |
| **Probe ids** | `P-08-a…c` (pre-registered), `N-01…N-12` |

## [GÖZLEM] Claim

```
every probability is computed from |δ|          (power, α, β — all five analyses)
δ is printed with the sign of the effect size
critical t is printed as sign(ES)·t_crit         a priori, post hoc, compromise
critical t is printed as +t_crit                 criterion — the sign is NOT applied
point biserial: a negative r is refused          "outside the admissible range (0, 0.999999)"
```

## Why this is not in the manual

The manual never says what a negative `d` means. Two readings are both
defensible: (A) the test is one-sided in the positive direction and a negative
effect points the wrong way, so power falls below `α`; (B) the sign states the
direction of the alternative. They differ by five orders of magnitude on a
one-tailed post-hoc analysis. SPEC v1.1 chose (A) for post hoc and (B) for the
solving analyses.

## [GÖZLEM] Observation — G\*Power 3.1.9.6

Pre-registered rows (predictions committed before observation):

| probe | input | G\*Power printed | v1.1 predicted | competing | verdict |
|---|---|---|---|---|---|
| `P-08-a` | one sample, `d = -0.5`, `N = 30`, α `.05`, **one** tail, post hoc | power **`0.8482542`**, `δ = -2.7386128`, `t = -1.6991270` | `7.733e-06` (signed) | `0.8482542` (absolutised) | **CONTRADICTS** v1.1 |
| `P-08-b` | same, two tails | power `0.7539647`, `t = -2.0452296` | `0.7539647` | `0.7539647` | control |
| `P-08-c` | one sample, `d = -0.5`, power `.80`, one tail, a priori | `N = 27`, `δ = -2.5980762`, `t = -1.7056179` | `27` | no solution | **SUPPORTS** |

The sign sweep `N-*`:

| row | test / analysis | input | G\*Power printed |
|---|---|---|---|
| `N-01` | one sample / criterion, 1 tail | `d = -0.5`, `N = 30`, power `.8` | `δ = -2.7386128`, **`t = +1.8880297`**, `α = 0.0345321` |
| `N-02` | one sample / criterion, 2 tails | same | `δ = -2.7386128`, **`t = +1.8880431`**, `α = 0.0690624` |
| `N-03` | two groups / compromise, 1 tail | `d = -0.5`, `40 + 40`, `q = 1` | `δ = -2.2360680`, `t = -1.1216208`, `α = β = 0.1327324` |
| `N-04` | two groups / compromise, 2 tails | same, `q = 2` | `δ = -2.2360680`, `t = -1.5551029`, `α = 0.1239699` |
| `N-05` | generic / post hoc, 1 tail | `δ = -2.5`, `ν = 30` | `t = -1.6972609`, power `0.7876008` |
| `N-06` | generic / post hoc, 2 tails | same | `t = -2.0422725`, power `0.6770315` |
| `N-07` | point biserial / post hoc | `r = -0.3`, `N = 50` | dialog: *"Input error! Effect size r is outside the admissible range (0, 0.999999)."* |
| `N-08` | matched pairs / post hoc, 1 tail | `dz = -0.4`, `N = 40` | `δ = -2.5298221`, `t = -1.6848751`, power `0.7997378` |
| `N-09` | two groups / post hoc, 1 tail | `d = -0.5`, `30 + 30` | `δ = -1.9364917`, `t = -1.6715528`, power `0.6060253` |
| `N-10` | two groups / a priori, 1 tail, `R = 2` | `d = -0.5`, power `.8` | `38 / 76`, `δ = -2.5166115`, `t = -1.6585726` |
| `N-11` | one sample / post hoc | `d = 0`, `N = 30` | power `0.0500000` (= α, F-02) |
| `N-12` | generic / criterion, 1 tail | `δ = -2.5`, `ν = 30`, power `.8` | **`t = +1.6533561`**, `α = 0.0543434` |

Every power and `α` equals the value for `|ES|`. The criterion analysis — and
only it — prints a positive critical value next to a negative `δ` (`N-01`,
`N-02`, `N-12`), an internal inconsistency of G\*Power that a conforming
implementation must reproduce to match its output.

## What changed in the engine

`engine.power()` computes from `|δ|` and returns `δ` and the critical value
with the sign of the effect; the criterion analysis returns `+t_crit`; the
point-biserial procedure refuses `r ≤ 0`. `warnings[]` still records that a
negative effect size was supplied.

## Verdict

**[GÖZLEM] F-08 — observed.** The sign is a direction; G\*Power never computes a
"wrong-way" power. All 14 rows above are reproduced in every printed field.

## Re-run

```console
$ python tools/rea_campaign.py --set probes --only P-08-a P-08-b P-08-c
$ python tools/rea_campaign.py --set sign
$ python -m pytest tests/test_gpower_observed.py -k "P-08 or N-"
```
