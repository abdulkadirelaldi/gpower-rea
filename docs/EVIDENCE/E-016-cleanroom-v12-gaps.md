# E-016 — The second clean-room pass: 19 gaps in SPEC v1.2, settled by asking G\*Power

| | |
|---|---|
| **Finding** | [F-16](../../SPEC.md#f-16--points-spec-v12-left-undetermined-closed-by-observation-where-possible) |
| **Status** | `[SPEC-CLOSURE]`; twelve of nineteen rows `[REA] OBSERVED` |
| **Method** | A second implementation written from SPEC v1.2 alone; each reported gap then turned into a GUI probe |
| **Probe ids** | `X-G2-*` (`tools/rea_campaign.py --set gaps`), plus `D-*`, `S-*` |

## What happened

SPEC v1.2 (SHA-256 `263775846fa1…e789e`) was handed to a fresh agent session
whose working directory held only `SPEC.md`, `INTERFACE.md` and its own
v1.1-era package. It returned an implementation (82 self-checks passing) and
[`cleanroom/SPEC-GAPS-v1.2.md`](../../cleanroom/SPEC-GAPS-v1.2.md): **19 points
where the text did not determine its code, each with an input on which a
different reasonable reading gives a different output.**

Judged against the recorded G\*Power readings, that implementation reproduced
**212 of 213** a-priori results. The one it missed, `D-28`, is its own gap
G2-04: SPEC v1.2 allowed both "skip a split with a group of 1" and "do not
skip". The first pass (F-13) could only settle such gaps by convention. This
time the reference program was available, so each gap that is a question about
G\*Power became a probe.

## [REA] Observation

| probe | input | G\*Power printed | engine (v1.3) |
|---|---|---|---|
| `D-28` | indep / a priori — tails=2, es=20, alpha=0.05, power=0.8, ratio=3 | Sample size group 1 `1`, Sample size group 2 `3`, Total sample size `4` | identical |
| `X-G2-02` | indep / post hoc — tails=2, es=0.5, n1=0, n2=3, alpha=0.05 | *Input error! Sample size must be greater than or equal to 1.* | both refuse |
| `X-G2-04` | indep / a priori — tails=2, es=8, alpha=0.05, power=0.8, ratio=3 | Sample size group 1 `1`, Sample size group 2 `3`, Total sample size `4` | identical |
| `X-G2-06` | point-biserial / post hoc — tails=2, es=0, n=10, alpha=0.05 | Power (1-β err prob) `0.0500000` | identical |
| `X-G2-07` | regression / sensitivity — tails=2, n=4, predictors=2, alpha=0.001, power=0.99 | Effect size f² `672256.1` | identical |
| `X-G2-08a` | point-biserial / a priori — tails=2, es=5e-06, alpha=0.05, power=0.8 | Total sample size `313910513769` | F-14 region |
| `X-G2-08b` | regression / a priori — tails=2, es=5e-06, predictors=1, alpha=0.05, power=0.8 | *Input error! In an a priori analysis, the absolute value of the effect size be greater than 0.00001.* | both refuse |
| `X-G2-11a` | indep / a priori — tails=2, es=0.5, alpha=0.05, power=0.8, ratio=0.001 | *Input error! The allocation ratio falls outside the admissible range (0.01, 100).* | both refuse |
| `X-G2-11b` | indep / a priori — tails=2, es=0.5, alpha=0.05, power=0.8, ratio=1000 | *Input error! The allocation ratio falls outside the admissible range (0.01, 100).* | both refuse |
| `X-G2-11c` | indep / a priori — tails=2, es=0.5, alpha=0.05, power=0.8, ratio=0.01 | Sample size group 1 `3174`, Sample size group 2 `32`, Total sample size `3206` | identical |
| `X-G2-11d` | indep / a priori — tails=2, es=0.5, alpha=0.05, power=0.8, ratio=100 | Sample size group 1 `32`, Sample size group 2 `3174`, Total sample size `3206` | identical |
| `X-G2-14` | indep / a priori — tails=2, es=1.11, alpha=0.05, power=0.8, ratio=7.8 | Sample size group 1 `7`, Sample size group 2 `59`, Total sample size `66` | identical |
| `X-G2-17` | regression / post hoc — tails=2, es=0.15, n=20, predictors=0, alpha=0.05 | *Input error! There must be at least 1 predictor.* | both refuse |

## What the observations decided

* **G2-04** — no skip: `1 / 3` is a valid reported design (`X-G2-04`, `D-28`).
* **G2-14** — the split is computed in binary double: `66/8.8` is
  `7.4999…`, and G\*Power prints `7 / 59`, not the decimal `8 / 58`.
* **G2-06** — `r = 0` is accepted although the message reads "(0, 0.999999)".
* **G2-08** — the `1e-5` a-priori floor applies to `f²` but not to `r`.
* **G2-11** — the allocation ratio is limited to `[0.01, 100]`.
* **G2-02**, **G2-17** — each group `≥ 1`; `predictors ≥ 1`.
* **G2-07** — a sensitivity `f²` far above the input bound (`672256.1`) is
  computed and printed.

Four of these changed the engine (G2-06, G2-08, G2-11, G2-02 — it had refused
`r = 0` and `r = 5e-6`, and accepted `R = 0.001` and `n₁ = 0`). The rest
confirmed it. The remaining seven gaps (G2-10, G2-12, G2-13, G2-15, G2-16,
G2-18, G2-19) concern warnings, naming and representation, not numbers
G\*Power prints; F-16 states a convention for each.

## Verdict

**F-16 — closed.** The second pass found one live divergence on real data and
eighteen other gaps; observation settled twelve, convention the rest.

## Re-run

```console
$ python tools/rea_campaign.py --set gaps
$ python tools/judge_cleanroom.py
```
