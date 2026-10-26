# E-015 — The input domain G\*Power accepts

| | |
|---|---|
| **Finding** | [F-15](../../SPEC.md#f-15--the-input-domain-gpower-accepts) |
| **Status** | `[GÖZLEM]` |
| **Method** | Boundary probing: values on, just inside and just outside each plausible edge |
| **Target** | G\*Power 3.1.9.6 (macOS), `t tests`, all six entries |
| **Probe ids** | `D-01…D-46` (`tools/rea_campaign.py --set domain`), `N-07` |

## [GÖZLEM] Claim

G\*Power validates its inputs against ranges the manual never states, and
refuses everything outside them with an *"Input error!"* dialog. SPEC F-15
lists the ranges; this file is the record they were read from. Two of the
observed rules are internal inconsistencies of the program itself:

* the a-priori analysis returns `N = 2` for a large effect (`D-23`), a design
  the post-hoc analysis then refuses as input (`D-41`);
* the `f²` range check admits negative values (*"admissible range (-20, 20)"*),
  which then fail during computation with *"Internal Math Error"* (`D-37`,
  `D-38`, `D-42`).

## Why this matters for a reimplementation

A clean-room engine that accepts what G\*Power refuses gives an answer where
the reference gives none; one that refuses what G\*Power accepts loses a
conformance row. Before these probes the engine did both: it answered for
`r = 0.9999995`, `N = 2`, `power < α` and `q = 1e-4`, and it refused
`d = 1e-5` (its search stopped at `N = 1e7`; G\*Power's answer is
`N = 7.8e10`).

## [GÖZLEM] Observation — every boundary probe

The message text is G\*Power's, verbatim. *Engine* compares the current
engine against that reading (`tools/rea_report.py`).

| probe | input | G\*Power printed | engine |
|---|---|---|---|
| `D-01` | point-biserial / post hoc — tails=2, es=0.999999, n=50, alpha=0.05 | Df `48`, Power (1-β err prob) `1.0000000` | identical |
| `D-02` | point-biserial / post hoc — tails=2, es=0.9999995, n=50, alpha=0.05 | *Input error! Effect size r is outside the admissible range (0, 0.999999).* | both refuse |
| `D-03` | point-biserial / post hoc — tails=2, es=1, n=50, alpha=0.05 | *Input error! Effect size r is outside the admissible range (0, 0.999999).* | both refuse |
| `D-04` | point-biserial / post hoc — tails=1, es=-0.3, n=50, alpha=0.05 | *Input error! Effect size r is outside the admissible range (0, 0.999999).* | both refuse |
| `D-05` | one-sample / a priori — tails=2, es=0, alpha=0.05, power=0.8 | *Input error! In an a priori analysis, the absolute value of the effect size be greater than 0.00001.* | both refuse |
| `D-06` | indep / post hoc — tails=2, es=0, n1=20, n2=20, alpha=0.05 | Df `38`, Power (1-β err prob) `0.0500000` | identical |
| `D-07` | one-sample / post hoc — tails=1, es=0.3, n=30, alpha=0.75 | Df `29`, Power (1-β err prob) `0.9895897` | identical |
| `D-08` | one-sample / post hoc — tails=2, es=0.5, n=2, alpha=0.05 | *Input error! Total sample size is outside the admissible range (3, 9223372036854775806)* | both refuse |
| `D-09` | one-sample / post hoc — tails=2, es=0.5, n=1, alpha=0.05 | *Input error! Total sample size is outside the admissible range (3, 9223372036854775806)* | both refuse |
| `D-10` | generic / post hoc — tails=2, es=1, df=0.5, alpha=0.05 | Power (1-β err prob) `0.0611031` | identical |
| `D-11` | regression / post hoc — tails=2, es=0, n=50, predictors=1, alpha=0.05 | Df `48`, Power (1-β err prob) `0.0500000` | identical |
| `D-12` | regression / a priori — tails=2, es=0, predictors=1, alpha=0.05, power=0.8 | *Input error! In an a priori analysis, the absolute value of the effect size be greater than 0.00001.* | both refuse |
| `D-13` | one-sample / a priori — tails=2, es=0.5, alpha=0.05, power=0.04 | *Input error! Power must be greater than or equal to alpha.* | both refuse |
| `D-14` | indep / a priori — tails=2, es=0.8, alpha=0.05, power=0.8, ratio=0.05 | Df `272`, Total sample size `274`, Actual power `0.8010198` | identical |
| `D-15` | indep / a priori — tails=2, es=0.8, alpha=0.05, power=0.8, ratio=20 | Df `272`, Total sample size `274`, Actual power `0.8010198` | identical |
| `D-16` | regression / post hoc — tails=2, es=0.15, n=6, predictors=5, alpha=0.05 | *Input error! Total sample size is outside the admissible range (7, 9223372036854775806)* | both refuse |
| `D-17` | indep / post hoc — tails=2, es=0.5, n1=1, n2=1, alpha=0.05 | *Input error! Total sample size is outside the admissible range (3, 9223372036854775806)* | both refuse |
| `D-18` | one-sample / a priori — tails=2, es=0.1, alpha=0.05, power=0.999 | Df `2552`, Total sample size `2553`, Actual power `0.9990021` | identical |
| `D-19` | indep / compromise — tails=2, es=0.5, n1=40, n2=40, q=0.0001 | *Input error! β/α ratio is outside the admissible range (0.01, 100)* | both refuse |
| `D-20` | one-sample / sensitivity — tails=2, n=30, alpha=0.05, power=0.04 | *Input error! Power must be greater than or equal to alpha.* | both refuse |
| `D-21` | paired / a priori — tails=2, es=5, alpha=0.05, power=0.8 | Df `2`, Total sample size `3`, Actual power `0.9754623` | identical |
| `D-22` | indep / a priori — tails=1, es=0.5, alpha=0.05, power=0.8, ratio=1.5 | Df `104`, Total sample size `106`, Actual power `0.8041596` | identical |
| `D-23` | paired / a priori — tails=2, es=20, alpha=0.05, power=0.8 | Df `1`, Total sample size `2`, Actual power `0.9735240` | identical |
| `D-24` | indep / post hoc — tails=2, es=0.5, n1=1, n2=2, alpha=0.05 | Df `1`, Power (1-β err prob) `0.0540922` | identical |
| `D-25` | point-biserial / post hoc — tails=2, es=0.5, n=3, alpha=0.05 | Df `1`, Power (1-β err prob) `0.0729889` | identical |
| `D-26` | point-biserial / post hoc — tails=2, es=0.5, n=4, alpha=0.05 | Df `2`, Power (1-β err prob) `0.1097859` | identical |
| `D-27` | indep / a priori — tails=2, es=20, alpha=0.05, power=0.8 | Df `2`, Total sample size `4`, Actual power `1.0000000` | identical |
| `D-28` | indep / a priori — tails=2, es=20, alpha=0.05, power=0.8, ratio=3 | Df `2`, Total sample size `4`, Actual power `0.9999996` | identical |
| `D-29` | point-biserial / a priori — tails=2, es=0.99, alpha=0.05, power=0.8 | Df `2`, Total sample size `4`, Actual power `0.9999359` | identical |
| `D-30` | regression / a priori — tails=2, es=50, predictors=3, alpha=0.05, power=0.8 | *Input error! Effect size f² is outside the admissible range (-20, 20).* | both refuse |
| `D-31` | one-sample / a priori — tails=2, es=1e-05, alpha=0.05, power=0.8 | Df `78488272180`, Total sample size `78488272181`, Actual power `0.8000265` | see F-14 |
| `D-32` | one-sample / a priori — tails=2, es=0.5, alpha=0.05, power=0.05 | Df `1`, Total sample size `2`, Actual power `0.0619486` | identical |
| `D-33` | indep / compromise — tails=2, es=0.5, n1=40, n2=40, q=0.01 | Df `78`, α err prob `0.8928789`, Power (1-β err prob) `0.9910712` | identical |
| `D-34` | indep / compromise — tails=2, es=0.5, n1=40, n2=40, q=100 | Df `78`, α err prob `0.006965227`, Power (1-β err prob) `0.3034773` | identical |
| `D-35` | one-sample / criterion — tails=2, es=1e-06, n=30, power=0.8 | Df `29`, α err prob `0.8000000` | identical |
| `D-36` | one-sample / post hoc — tails=2, es=0.5, n=30, alpha=0.9999 | Df `29`, Power (1-β err prob) `0.9999976` | identical |
| `D-37` | regression / post hoc — tails=2, es=-0.15, n=50, predictors=1, alpha=0.05 | *Internal Math Error! GPower encountered an error during generation of the plot of central and noncentral distributions. The graph is omitted!* | both refuse |
| `D-38` | regression / post hoc — tails=1, es=-0.15, n=50, predictors=1, alpha=0.05 | *Internal Math Error! GPower encountered an error during generation of the plot of central and noncentral distributions. The graph is omitted!* | both refuse |
| `D-39` | regression / post hoc — tails=2, es=19.99, n=10, predictors=1, alpha=0.05 | Df `8`, Power (1-β err prob) `1.0000000` | identical |
| `D-40` | one-sample / a priori — tails=2, es=9e-06, alpha=0.05, power=0.8 | *Input error! In an a priori analysis, the absolute value of the effect size be greater than 0.00001.* | both refuse |
| `D-41` | paired / post hoc — tails=2, es=0.5, n=2, alpha=0.05 | *Input error! Total sample size is outside the admissible range (3, 9223372036854775806)* | both refuse |
| `D-42` | regression / a priori — tails=2, es=-0.15, predictors=1, alpha=0.05, power=0.8 | *Internal Math Error! GPower encountered an error during generation of the plot of central and noncentral distributions. The graph is omitted!* | both refuse |
| `D-43` | one-sample / a priori — tails=2, es=0.0001, alpha=0.05, power=0.95 | Df `1299470952`, Total sample size `1299470953`, Actual power `0.9500000` | see F-14 |
| `D-44` | indep / a priori — tails=2, es=0.001, alpha=0.05, power=0.8, ratio=2 | Df `35319872`, Total sample size `35319874`, Actual power `0.8000000` | see F-14 |
| `D-45` | point-biserial / sensitivity — tails=2, n=50, alpha=0.05, power=0.8 | Df `48`, Effect size |ρ| `0.3748677` | identical |
| `D-46` | regression / sensitivity — tails=2, n=50, predictors=2, alpha=0.05, power=0.8 | Df `47`, Effect size f² `0.1636463` | identical |
| `N-07` | point-biserial / post hoc — es=-0.3, n=50, alpha=0.05, tails=1 | *Input error! Effect size r is outside the admissible range (0, 0.999999).* | both refuse |

## What changed in the engine

`engine.APRIORI_MIN_ABS_ES`, `BETA_ALPHA_RATIO_RANGE`, `MIN_INPUT_TOTAL`,
`_require_power_at_least_alpha`, `_check_input_design`; the point-biserial
domain `(0, 0.999999]` and the `f²` domain `[0, 20)` in `procedures.py`; the
a-priori search cap raised from `1e7` to G\*Power's `2⁶³ - 2`. Each refusal
names the rule and cites F-15.

## Verdict

**[GÖZLEM] F-15 — observed.** Every boundary probe is either identical or refused
by both, except the three huge-`N` rows, which belong to F-14.

## Re-run

```console
$ python tools/rea_campaign.py --set domain
$ python -m pytest tests/test_gpower_observed.py -k "D-"
```
