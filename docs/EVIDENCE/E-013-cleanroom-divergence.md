# E-013 — What the clean-room pass found

| | |
|---|---|
| **Finding** | [F-13](../../SPEC.md#f-13--points-the-specification-left-undetermined-now-specified) |
| **Status** | `SPEC-CLOSURE` — a defect report against this specification, not a claim about G\*Power |
| **Method** | Two-session clean room, then differential probing of the underspecified regions |
| **Target** | SPEC.md **v1.0** |
| **Probe id** | `G-01 … G-12` (`tools/probe_spec_gaps.py`) |

## What happened

SPEC.md v1.0 was frozen and handed to an independent implementation session
whose only inputs were that file and a naming-only interface document. It had
no access to `src/`, to `docs/EVIDENCE/`, to the probe worksheets, or to the
conformance vectors. It was told explicitly: **if the specification is
incomplete, do not guess and do not fill the gap from background knowledge —
record it.**

It produced a working implementation and a 12-item gap report
([`cleanroom/SPEC-GAPS.md`](../../cleanroom/SPEC-GAPS.md)).

Then the question that matters: does any gap actually bite? A gap is only a
defect if two readers of the document behave differently because of it. So
each of the twelve regions was probed on both implementations:

```console
$ python tools/probe_spec_gaps.py
  AGREE: 6, DIVERGE: 5, N/A: 1
```

**Five live specification defects.** Each one is a place where two competent
implementations of the same document produced different numbers — and none of
them could have been found by testing the shipped engine against itself, at
any level of effort, because the engine was self-consistently wrong.

## The five divergences

| gap | input | shipped engine | clean room |
|---|---|---|---|
| `G-01` sign rule of the compromise analysis | `d = -0.5`, one tail, `n₁=n₂=40`, `q=1` | `α = 0.1327324` | `α = 0.8672676` |
| `G-03` which effect size the result reports after `\|ES\|` substitution | a-priori, `d = -0.5`, one tail | `-0.5` (the input) | `0.5` (the value used) |
| `G-04` lower end of the sensitivity bracket | `α = 0.20`, target power `0.20`, `N = 50` | `1.000e-09` | `1.000e-12` |
| `G-05` criterion analysis with a tiny answer | target power `0.05`, `d = 1.5`, `N = 200` | `1.000e-12` | `4.213e-60` |
| `G-11` an inapplicable design parameter | `predictors=3` on a one-sample test | `ValidationError` | computes, ignoring it |

### `G-05` was a real defect, not a convention

The other four are conventions: two defensible readings, and the specification
simply had to pick one. `G-05` is different. The criterion analysis asks *what
`α` brings power down to the requested level*; at `d = 1.5` with `N = 200` the
answer is `4.2e-60`. The shipped engine bisected `α` linearly on
`[1e-12, 1-1e-12]` and returned its own bracket floor — a wrong answer, dressed
as a round number, with nothing in the output to say so.

Fixed by bisecting `log α` over `[1e-300, 1-1e-15]`:

```python
# gpower_rea/engine.py
def pw_of_log_alpha(la: float) -> float:
    return _power_from_ncp(math.exp(la), df, ncp, tails)[0]

la = _bisect_scalar(pw_of_log_alpha, math.log(ALPHA_SEARCH_MIN),
                    math.log(ALPHA_SEARCH_MAX), power_target)
```

```console
$ gpower solve -t one-sample -s alpha -p 0.05 -e 1.5 -n 200 --json
  "alpha": 4.2133...e-60,
```

This is the single most valuable thing the clean-room pass produced, and it is
worth being precise about *why* it was invisible before: every test the engine
had was either a round trip through its own bisection, or a comparison against
a reference that used the same bracket. A second implementation with a
different bracket was the only thing that could expose it.

## What changed, and what did not

* **SPEC.md v1.0 → v1.1**: F-13 added, closing all twelve points. F-01…F-12
  unchanged except for measured frequencies added to F-05 and F-09.
* **The engine**: `log α` bisection (`G-05`), effect-size brackets lowered to
  `1e-12` (`G-04`), explicit rejection of a zero effect size in the three
  solving analyses (`G-08`), explicit rejection of a negative `f²` (`G-02`),
  and the `|δ|` rule extended to compromise with the F-08 warning (`G-01`).
* **Not changed**: `G-03` (the result still echoes the effect size *as
  supplied*, which is better provenance — the value actually used is
  recoverable from `noncentrality`) and `G-11` (an inapplicable parameter is
  still rejected, because a silently ignored parameter is a typo nobody ever
  notices).

For `G-03` and `G-11` the specification now states the engine's convention, so
the divergence is closed by documentation rather than by code. That is a
legitimate resolution — but it is a *choice*, and F-13 says so rather than
presenting it as a derivation.

## Re-probe after the fixes

```console
$ python tools/probe_spec_gaps.py
```

Three of the five divergences are now closed in code; `G-03` and `G-11` remain
visible as deliberate, documented differences between an implementation of
v1.0 and one of v1.1. `tests/test_spec_f13.py` locks each resolution.

## Why this is in the evidence directory

Every other file here is evidence *about G\*Power*. This one is evidence about
the method: it is what a clean-room pass is for. The protocol's claim was that
writing the specification first, and handing it to someone who cannot see the
code, forces the specification to be complete. That claim is now testable —
it found five defects, one of them a genuine wrong answer — and the cost of
the exercise was one agent session.

## Re-run

```console
$ python tools/judge_cleanroom.py        # 401/401, all properties, CONFORMING
$ python tools/probe_spec_gaps.py        # the twelve regions
$ python -m pytest tests/test_spec_f13.py tests/test_cleanroom_conformance.py -q
```
