# CLEANROOM-PROTOCOL.md — the two-session rule

> **Rule 2 of the assignment:** two separate agent sessions — one analyses, the
> other writes using `SPEC.md` only.

## 1. Why the rule exists

A clean-room reimplementation is only "clean" if the implementer never saw the
original. The point is not ceremony: it is that a specification written *for*
an implementer who cannot see the original is forced to be **complete**. Every
behaviour the analyst forgot to write down becomes a visible gap the moment
the implementer hits it, instead of being silently patched from memory.

The two-session split is how that constraint is enforced on an agent, which has
no memory wall of its own.

## 2. The boundary

```
   SESSION A — ANALYSIS                     SESSION B — IMPLEMENTATION
   ─────────────────────                    ──────────────────────────
   may use:                                 may use:
     · the G*Power GUI                        · SPEC.md
     · the published manual                   · its own mathematics
     · probe design                           · its own numerics
     · published outputs                      · a general statistics
                                                textbook
   must produce:                            must NOT use:
     · SPEC.md                                 · the GUI
     · docs/EVIDENCE/*.md                      · the manual
     · tools/probe_plan.py                     · docs/EVIDENCE/*
                                               · any G*Power output
   must NOT produce:
     · engine code
```

The asymmetry is deliberate. Session A may not write the engine, because an
analyst who is also the implementer stops writing things down. Session B may
not read the evidence files, because the evidence contains G\*Power outputs —
reading them would turn the implementation into a curve fit against the oracle
rather than an implementation of the specification.

`SPEC.md` is the only channel across the boundary. It is frozen before
Session B starts.

## 3. What Session B was given

The exact handover prompt:

```
You are implementing a statistical engine from a specification.

Read ONLY the file SPEC.md in this repository. Do not look for, open,
or reason about: the G*Power application, its manual, docs/EVIDENCE/*,
probes/*, or any file containing recorded G*Power output. If you believe
SPEC.md is incomplete or self-contradictory, STOP and report the gap --
do not fill it from your own knowledge of G*Power, and do not guess.

Implement, in Python 3.10+ with no third-party runtime dependencies:

  1. src/gpower_rea/numerics.py    - the special functions SPEC section 4
                                     requires, to the stated tolerances
  2. src/gpower_rea/procedures.py  - one object per statistical test,
                                     supplying only (df, noncentrality)
  3. src/gpower_rea/engine.py      - the single power formula of F-02 and
                                     the five analysis types of section 3
  4. src/gpower_rea/effectsize.py  - the calculators of F-11
  5. src/gpower_rea/report.py      - the output renderings

Every finding F-01..F-12 must be traceable to the code that implements it.
Where SPEC.md marks a finding REA-OPEN, implement BOTH candidates and make
the choice selectable and reported in the output -- never silently pick one.
```

## 4. Attestation status — executed and signed

| | status |
|---|---|
| `SPEC.md` written before the engine, and frozen | **yes** — v1.0 at commit `aad154e`, tag `spec-frozen-v1.0` |
| Implementation traceable to `SPEC.md` findings only, machine checked | **yes** (`compliance_check.py` C-4) |
| No recorded G\*Power output anywhere under `src/` | **yes** (§5b.3) |
| Analysis and implementation performed in **two separate agent sessions** | **yes — signed** |
| Second implementation holds to the same contract | **CONFORMING** — 401/401, every SPEC property, 300/300 cross-grid |
| Lexical independence verified after the fact | Jaccard `0.204`, 0 identical comment lines |

The full record, with its caveats, is in
[SESSION-LOG.md § Attestation 2](SESSION-LOG.md). The boundary was enforced by
the handover prompt of §3 plus a physically separate input directory containing
only `SPEC.md` and `INTERFACE.md` — **not** by a sandbox. That is why the
overlap report exists: it is evidence after the fact rather than proof up
front, and this document says so rather than implying more.

### What it cost, and what it returned

One agent session. It returned five specification defects — five places where
two competent readers of the same document produced different numbers — one of
which was a **wrong answer** in the shipped engine, plus three numerical
improvements the engine then adopted. Details in
[EVIDENCE/E-013](EVIDENCE/E-013-cleanroom-divergence.md).

That is the argument for the protocol, and it is worth stating as a claim
rather than a platitude: **a specification that has only ever been implemented
once has not been tested.** Every test of a single implementation is a test of
its self-consistency. `G-05` is the proof — the engine had property tests,
round-trip tests, an independent SciPy re-derivation and a third-party
agreement oracle, and all four were blind to it, because all four went through
the same bracket.

## 5. Specification gaps closed before the engine was written

A specification-first pass is worth running only if it finds something. Four
gaps in the first draft of `SPEC.md` surfaced while implementing against it,
and each was closed by **amending the specification** rather than by filling it
in from background knowledge of G\*Power:

| gap | how SPEC.md was amended |
|---|---|
| F-02 gives the power formula but not how `α` is recovered when it is the unknown; the criterion analysis had no stated method. | §3 now states the method and the monotonicity direction for all five analysis types. |
| F-05 fixed the balanced grid but left the unbalanced grid undetermined — `ratio ≠ 1` was not implementable from the text. | F-09 was written, with **both** candidate grids, the rounding mode, and a discriminator (E-009). |
| No minimum admissible design was stated. `ttest-regression-coef` with `N = 4, p = 10` yields `ν = −7`. | Minimum designs added to F-03, F-04, F-05, F-07; the engine now raises a validation error instead of returning a number. |
| F-12 required agreement to `5e-7` but never stated the accuracy the underlying distribution functions must reach, so no algorithm choice followed from it. | §4 was written: a tolerance table, the mixture representation, and the two cancellation warnings. |

The last one is the most valuable. Without it, the natural choice for the
noncentral *t* CDF is the classical series, which degrades for large `|δ|`
exactly where a-priori analyses live. The specification now tells the
implementer which representation to use **and why** — which is the difference
between a specification and a wish.

## 5b. Verifying the claim

A clean-room claim that cannot be checked is worth nothing. Three checks:

### 5b.1 The specification is sufficient on its face

`SPEC.md` contains every `(ν, δ)` formula, every minimum design, every
analysis-type method, both allocation rules, the rounding mode, the tolerance
table and the two numerical warnings. It does not contain a single recorded
G\*Power output other than the one published example in F-06 — which is cited
*as* published, not as a probe result.

### 5b.2 The implementation cites the specification, not the oracle

Every `Procedure` carries its `spec_refs`, and the link is machine checked in
both directions:

```console
$ python tools/compliance_check.py
  C-4 findings <-> SPEC.md <-> docs/EVIDENCE are in sync
```

```console
$ gpower info point-biserial
...
spec findings  : F-01, F-02, F-04
```

### 5b.3 The implementation contains no oracle data

`src/` contains no recorded G\*Power output at all. The one file that holds
numbers — `src/gpower_rea/data/public_vectors.csv` — is **generated by the
engine** (`tools/make_vectors.py`) and independently re-derived by
`tests/test_reference_scipy.py`. Its freshness is a test:

```console
$ python tools/make_vectors.py --check
fresh: .../public_vectors.csv (401 vectors)
```

So the engine cannot have been fitted to the vectors: the vectors are a
function of the engine.

## 6. Executing (and signing) the two-session pass

Ten minutes, two agent sessions, one signature.

### Session A — analysis (already done; re-run only if you change SPEC.md)

```console
$ git switch -c cleanroom/session-a
$ # verify the spec stands on its own, and that nothing under src/ holds
$ # recorded G*Power output:
$ python tools/compliance_check.py
$ python tools/make_vectors.py --check
$ git tag spec-frozen-v1.0          # the handover point
```

### Session B — implementation from `SPEC.md` alone

```console
$ git switch -c cleanroom/session-b spec-frozen-v1.0
$ # Remove everything Session B may not see, so the boundary is physical
$ # rather than a promise:
$ git rm -r --cached src/gpower_rea docs/EVIDENCE probes
$ rm -rf src/gpower_rea docs/EVIDENCE probes
$ # Keep: SPEC.md, tests/, tools/, pyproject.toml
```

Then start a **fresh** agent session in that worktree and paste the handover
prompt from §3 verbatim. The agent sees `SPEC.md` and the test suite's
*interface* (module and function names), and nothing else.

### Judging the result

Do not diff the two implementations — they are allowed, and expected, to differ
internally. Judge against the frozen contract only, which is what
`tools/judge_cleanroom.py` does:

```console
$ python tools/judge_cleanroom.py
========================================================================
CLEAN-ROOM CONFORMANCE REPORT
========================================================================
conformance vectors : .../401 exact N
power within 5e-7   : .../401
SPEC properties       F-02 F-03 F-04 F-05 F-06/F-12 F-07 F-09
Analysis-type round trips
Cross-implementation grid: .../300 identical
Independence check (lexical overlap with the shipped engine)
VERDICT: ...
```

It checks four things:

1. the **same 401 conformance vectors** at the **same tolerances** the shipped
   engine is held to (exact integer `N`, `5e-7` on power);
2. the SPEC properties that are discriminating — the two-sided size at the
   null (F-02), the three cross-entry identities (F-03/F-04/F-07), the parity
   consequence of the balanced grid (F-05), the ratio signature of the default
   allocation rule (F-09), and the tightest-margin minimality case (F-12);
3. round trips between all five analysis types;
4. **independence**: lexical overlap with the shipped engine. A clean-room
   implementation should share the vocabulary of the domain (`alpha`, `power`,
   `noncentrality`) and nothing else. Shared *private* helper names or verbatim
   comment lines would mean the boundary leaked, and the report names them.

The same checks run as `tests/test_cleanroom_conformance.py`, which skips
itself when no clean-room implementation is present — so the main suite stays
runnable for anyone who has not performed the second session.

A second independent implementation that conforms is a far stronger validation
of `SPEC.md` than any prose about it. If it *diverges*, the divergence is a
specification bug first and an implementation bug second: read the gap report
Session B was asked to produce, and fix `SPEC.md`.

### Then probe the gaps — this is where the value is

Conformance is the easy half. The gap report is the other half, and a reported
gap only matters if it actually bites, so each one gets run on both
implementations:

```console
$ python tools/probe_spec_gaps.py
[DIVERGE ] G-01  sign rule of the compromise analysis (one tail, negative ES)
            shipped alpha=0.1327324 vs cleanroom alpha=0.8672676
...
  AGREE: 8, DIVERGE: 3, N/A: 1
```

Each region is probed with inputs *inside* the underspecified part of the
domain. A `DIVERGE` row is a live specification defect; an `AGREE` row means
the gap is real but latent. On this repository's run, five of twelve diverged
and one of those five was a wrong answer rather than a convention
([E-013](EVIDENCE/E-013-cleanroom-divergence.md)).

Fix each divergence in `SPEC.md`, not in whichever implementation you happen
to prefer — and where the resolution is a *choice* rather than a derivation,
say so. [F-13](../SPEC.md#f-13--points-the-specification-left-undetermined-now-specified)
is that table.

### Signing

Record the outcome in [SESSION-LOG.md](SESSION-LOG.md): the handover commit
and tag, what was withheld, the conformance verdict, the overlap figures, the
defects found, and the caveats. That table is the attestation. On this
repository it is **signed** — see §4.
