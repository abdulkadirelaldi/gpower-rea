# gpower-rea

**Sample size and statistical power for the G\*Power *t tests* family — from a
command line, from an MCP server, or in plain language.**

G\*Power is the tool clinical researchers use to answer *"how many participants
do I need?"*. It is free and excellent, and it has only a graphical interface:
no CLI, no API, nothing scriptable. An AI agent can drive it only by taking
screenshots and clicking, which is slow, expensive and silently unreliable.

This repository reverse engineers one of its test families **by running the
real program** — G\*Power 3.1.9.6, driven black-box through its own GUI —
documents every finding with `[REA]` evidence, reimplements it clean-room, and
gives it three interfaces.

> **Against the real G\*Power: 435 recorded runs, 421/421 identical in every
> printed field outside the one documented region where G\*Power itself is
> inexact, and 219/219 exact a-priori sample sizes.**
> ([VALIDATION §0](docs/VALIDATION.md#0-against-the-real-gpower--435-recorded-runs))

```console
$ gpower solve --test indep --alpha 0.05 --power 0.95 --effect-size 0.5
t tests - Means: Difference between two independent means (two groups)

Analysis:          A priori: Compute required sample size
Input Parameters
  Tail(s)                        = 2
  Effect size d                  = 0.5
  alpha err prob                 = 0.05
  Power (1-beta err prob)        = 0.95
  Allocation ratio N2/N1         = 1
Output Parameters
  Noncentrality parameter delta  = 3.6228442
  Critical t                     = 1.9714347
  Df                             = 208
  Sample size group 1            = 105
  Sample size group 2            = 105
  Total sample size              = 210
  Actual power                   = 0.9501287

An a priori power analysis for a two-tailed means: difference between two
independent means (two groups) (d = 0.5, alpha = 0.05, target power = 0.95)
indicated that n1 = 105 and n2 = 105 (total N = 210) is required; the achieved
power at that sample size is 0.9501.
```

Those are the numbers G\*Power prints for that design, to all seven decimals
(probe `P-01-a`).

---

## Install

```console
$ pip install -e .                      # engine + CLI, zero dependencies
$ pip install -e ".[mcp]"               # + MCP server
$ pip install -e ".[mcp,agent]"         # + natural-language agent
$ pip install -e ".[mcp,agent,dev]"     # + test suite (scipy, pytest)
```

Python 3.10+. The engine and CLI have **no third-party runtime dependencies**
— enforced by a test that blocks `numpy`/`scipy`/`pandas` at import time and
then runs the CLI.

---

## The three interfaces, one engine

```
natural language ──► agent ──► MCP server ──┐
shell / CI ──────────────────► CLI ─────────┼──► engine.solve()
Python ─────────────────────────────────────┘
```

No arithmetic exists outside the engine, and that is checked rather than
promised ([ARCHITECTURE.md](docs/ARCHITECTURE.md)). The practical payoff: a
number the agent reports in prose is byte-reproducible by a grader typing the
equivalent `gpower` command.

### 1 · CLI — 85-point baseline

```console
$ gpower list                                    # the six tests
$ gpower info point-biserial                     # parameters + spec findings
$ gpower solve -t paired -s power -a .05 -e .6 -n 24 --json
$ gpower solve -t indep -s compromise -e .5 --n1 40 --n2 40 --q 1
$ gpower effect-size -c d-two-independent-means \
      --param mean1=10.4 --param mean2=8.9 --param sd1=3.1 --param sd2=2.8
$ gpower curve -t indep -a .05 -e .5 --n-from 20 --n-to 200 --n-step 20
$ gpower batch -i vectors.csv --expect expected_N --min-match 0.90
$ gpower selftest
```

Full contract — flags, JSON schema, batch column aliasing, exit codes — in
[docs/CLI-CONTRACT.md](docs/CLI-CONTRACT.md).

### 2 · MCP server — +15

```console
$ gpower-mcp          # stdio
```

```json
{ "mcpServers": { "gpower": { "command": "gpower-mcp", "args": [] } } }
```

Six tools: `list_tests`, `describe_test`, `power_analysis`,
`compute_effect_size`, `power_curve`, `engine_provenance`. Each one forwards
to the engine and returns its JSON verbatim — asserted with `==` in
`tests/test_mcp_server.py`, and again over a real stdio subprocess in
`tests/test_mcp_stdio_e2e.py`. Works with both `mcp` 1.x (`FastMCP`) and
`mcp` 2.x (`MCPServer`).

### 3 · AI agent — +10

```console
$ export ANTHROPIC_API_KEY=...        # or: ant auth login
$ python agent/agent.py "40 kişilik iki grubum var, d=0.6 ile gücüm ne?"
```

Claude Opus 5.5 over the MCP server. Its system prompt forbids it from stating
any number that did not come back from a tool call, and
`tools/compliance_check.py` fails the build if the agent file contains
arithmetic at all. The loop is covered by 22 offline tests.

**A live run is recorded** in
[agent/transcripts/2026-10-26-unbalanced-a-priori.md](agent/transcripts/2026-10-26-unbalanced-a-priori.md):
a Turkish question, a model whose only tools were the six MCP tools, five tool
calls, and an answer whose every number is reproducible with a `gpower`
command. The run also **found a defect in our output** (a post-hoc report
printed the default allocation ratio instead of the design's) — fixed and
locked by a test. (`agent.py` itself needs an API key the build machine did not
have; that run used Claude Code as the harness over the same MCP server —
[agent/README.md](agent/README.md) says which is which.)

---

## What was reverse engineered

Sixteen findings. Every G\*Power claim is labelled **`[REA]`**, has an evidence file, and
is settled by recorded G\*Power output — and every one is behaviour the manual
does not state:

| # | finding | `[REA]` status |
|---|---|---|
| [F-01](SPEC.md#f-01--one-model-for-the-whole-family) | the whole family reduces to one `(ν, δ)` pair | derived + observed |
| [F-02](SPEC.md#f-02--two-sided-power-retains-the-far-tail-term) | **two-sided power keeps the wrong-side tail** — at `δ = 0` G\*Power prints `α`, not `α/2` | observed |
| [F-03](SPEC.md#f-03--one-sample-and-matched-pairs-ν--n---1-δ--es√n) | matched pairs counts *pairs*, not observations | derived + observed |
| [F-04](SPEC.md#f-04--point-biserial-ν--n---2-δ--r√n1-r²) | point biserial: `δ` uses `√N`, the statistic uses `√(N−2)` | derived + observed |
| [F-05](SPEC.md#f-05--balanced-a-priori-search-runs-over-n-per-group-not-total-n) | **a balanced total is never odd**, even when an odd split suffices (50 % of settings) | observed |
| [F-06](SPEC.md#f-06--minimality-and-actual-power-is-recomputed) | "Actual power" is recomputed — and **can be below the requested power** | observed, one clause **refuted** |
| [F-07](SPEC.md#f-07--regression-coefficient-ν--n---p---1-δ--f²n) | the predictor count enters `ν` only, never `δ` | derived + observed |
| [F-08](SPEC.md#f-08--a-negative-effect-size-is-a-direction-not-an-error) | **a negative effect is a direction**: power from `\|δ\|`, sign on `δ` and `t` — except in the criterion analysis | **refuted → corrected** |
| [F-09](SPEC.md#f-09--allocation-ratio-rounding) | **unbalanced designs: even totals only, stopping test on the unrounded split** — neither pre-registered candidate was right | **refuted → corrected** |
| [F-10](SPEC.md#f-10--compromise-analysis-is-defined-on-the-critical-value) | compromise analysis solves for the critical value | derived + observed |
| [F-11](SPEC.md#f-11--the-effect-size-drawer-offers-two-pooled-sds-and-the-equal-n-one-is-an-rms) | the equal-*n* pooling option is an RMS, not a pooled SD | **open** — the drawer is not reachable by the GUI driver |
| [F-12](SPEC.md#f-12--boundary-behaviour-and-reported-precision) | no epsilon slack at the boundary (`0.8000014` accepted) | observed |
| [F-13](SPEC.md#f-13--points-the-specification-left-undetermined-now-specified) | twelve points SPEC v1.0 did not determine, found by implementing it twice | spec closure |
| [F-14](SPEC.md#f-14--gpowers-own-answers-become-inexact-below-α--1e-9-and-above-n--1e7) | **G\*Power itself is inexact** below `α ≈ 1e-9` (*Internal Math Error*) and above `N ≈ 1e7` (picks a design below target) | observed, arbitrated at 50 digits |
| [F-15](SPEC.md#f-15--the-input-domain-gpower-accepts) | **the input domain**: `r ≤ 0.999999`, `\|ES\| ≥ 1e-5` a priori, `power ≥ α`, `q ∈ [0.01, 100]`, `N ≥ 3` — and a priori may return `N = 2`, which post hoc then refuses | observed |
| [F-16](SPEC.md#f-16--points-spec-v12-left-undetermined-closed-by-observation-where-possible) | **nineteen points SPEC v1.2 did not determine**, found by a second clean-room session — twelve then settled by asking G\*Power (e.g. the split is computed in binary double: `66/8.8 → 7 / 59`) | spec closure, 12 rows observed |

Read [SPEC.md](SPEC.md) for the specification,
[docs/EVIDENCE/](docs/EVIDENCE/) for the sixteen evidence files,
[probes/REA-OBSERVED.md](probes/REA-OBSERVED.md) for every recorded reading
against the engine, and [docs/REA-METHOD.md](docs/REA-METHOD.md) for the method.

---

## How do you prove the engine is right?

The assignment's question. The short answer this project arrived at:

> **Agreement between implementations proves a specification is implemented.
> Only the reference program proves the specification is right.**

| # | check | result |
|---|---|---|
| 1 | **the real G\*Power 3.1.9.6**, driven through its GUI on 435 inputs | **421/421** outside F-14; **219/219** exact a-priori `N` |
| 2 | pre-registered predictions, committed before G\*Power was run once | 26 supported, **2 refuted** (F-08, F-09) — kept in the record |
| 3 | 401 reference vectors, exact integer `N` | 401/401 |
| 4 | independent re-derivation: SciPy + brute-force search, from `SPEC.md` | 401/401 |
| 5 | an implementation by other people (`statsmodels`) | agrees, including the far-tail term of F-02 |
| 6 | **a second implementation of `SPEC.md`, written clean-room in a separate agent session** | judged against the same contract **and against the G\*Power readings** ([CLEANROOM-PROTOCOL](docs/CLEANROOM-PROTOCOL.md)) |
| 7 | property tests: monotonicity, minimality, round trips, cross-entry identities | all pass |
| 8 | arbitration by 50-digit `mpmath` wherever two answers differ | decides who is right — including against G\*Power (F-14) |

Check 1 is the one that changed the engine. Before it, checks 3–8 all passed —
and the engine still disagreed with G\*Power on **32 % of a-priori designs
(61 % of unbalanced ones)**, because SciPy, statsmodels and the first clean
room had all implemented the same guessed allocation rule. Observation found
that rule wrong, a fine power sweep exposed the real one, and the same campaign
found the negative-effect rule, the input domain, a large-`ν` numerical defect
in the engine, and two regions where G\*Power is itself inexact.

```console
$ python -m pytest -q                     # 1330 passed, incl. every recorded G*Power reading
$ python tools/rea_report.py              # cases=435 match=396 both_refuse=25 mismatch=14
$ python tools/fit_allocation.py          # F-09: 7 candidate rules vs the readings
$ gpower selftest                         # 401/401 exact N matches (rate 1.0000)
$ python tools/compliance_check.py        # COMPLIANCE: PASS (C-1..C-5)
$ python tools/judge_cleanroom.py         # the second implementation, same contract
```

---

## Scope

Test family **`t tests`**, all six entries, all five analysis types:

| test | effect size | a priori | post hoc | criterion | sensitivity | compromise |
|---|---|:-:|:-:|:-:|:-:|:-:|
| Means: two independent means | `d` | ✅ | ✅ | ✅ | ✅ | ✅ |
| Means: two dependent means (matched pairs) | `dz` | ✅ | ✅ | ✅ | ✅ | ✅ |
| Means: difference from constant (one sample) | `d` | ✅ | ✅ | ✅ | ✅ | ✅ |
| Correlation: point biserial model | `r` | ✅ | ✅ | ✅ | ✅ | ✅ |
| Linear multiple regression: single coefficient | `f²` | ✅ | ✅ | ✅ | ✅ | ✅ |
| Generic t test | `δ` | — | ✅ | ✅ | ✅ | ✅ |

Plus the "Determine ⇒" effect-size calculators, including both pooling options
of F-11.

Other families (`F tests`, `χ² tests`, `z tests`, exact tests) are out of
scope by design — one family, done properly, with evidence. Adding a family is
a `Procedure` object and a `SPEC.md` finding; the CLI, MCP server and agent
pick it up with no edit ([ARCHITECTURE.md](docs/ARCHITECTURE.md#extension-checklist)).

---

## Repository map

```
SPEC.md                      the specification; the clean-room handover artefact
ETHICS.md                    what was analysed, what is not here, and why
PUBLISH.md                   how to verify and publish a release
docs/
  REA-METHOD.md              how the behaviour was established, and its limits
  EVIDENCE/E-001 … E-012     one file per finding: claim, probe, [REA] observation
  EVIDENCE/E-013             what the clean-room pass found (5 spec defects)
  EVIDENCE/E-014 … E-016     G*Power's inexact regions; its input domain; round-2 gaps
  CLI-CONTRACT.md            flags, JSON schema, exit codes
  ARCHITECTURE.md            the one-engine rule and how it is enforced
  VALIDATION.md              measured evidence, with the gaps named
  CLEANROOM-PROTOCOL.md      the two-session rule and how to sign it
  SESSION-LOG.md             what is done, what is unsigned
src/gpower_rea/
  numerics.py                Φ, incomplete beta/gamma, central and noncentral t
  procedures.py              six (ν, δ) maps + validation
  engine.py                  THE ENGINE: one power formula, five analysis types
  effectsize.py              the "Determine ⇒" calculators
  report.py                  GUI-style protocol block + APA sentence
  cli.py                     the `gpower` command
  mcp_server.py              six MCP tools
  data/public_vectors.csv    401 generated reference vectors
agent/agent.py               Claude Opus 5.5 over MCP
agent/transcripts/           a recorded live run, natural language -> MCP -> engine
tools/
  gpower_ax.py               drive the G*Power GUI, black box (macOS Accessibility)
  rea_campaign.py            run case sets through G*Power AND the engine; record
  rea_report.py              re-score the engine against every recorded reading
  fit_allocation.py          score candidate F-09 rules against the readings
  stamp_worksheet.py         fill the pre-registered worksheet from the readings
  probe_plan.py              generate the GUI probe worksheet
  harvest.py                 stamp observations into a verdict per finding
  make_vectors.py            regenerate / verify the vector file
  judge_cleanroom.py         hold the independent 2nd implementation to the contract
  probe_spec_gaps.py         probe the 12 regions SPEC.md v1.0 left undetermined
  compliance_check.py        the submission rules, as a machine check
  publish.ps1                verify, commit and push (refuses if the gate fails)
probes/
  observations/*.jsonl       435 raw G*Power 3.1.9.6 readings (never edited)
  REA-OBSERVED.md            the engine against every reading, field by field
  probe_worksheet.{csv,md}   36 pre-registered rows with competing predictions
  REA-RESULTS.md             per-finding verdict of the pre-registration
tests/
  test_numerics.py           accuracy, self-consistency, mpmath arbitration
  test_engine_invariants.py  monotonicity, minimality, round trips, identities
  test_reference_scipy.py    all 401 vectors re-derived independently
  test_reference_statsmodels.py      agreement with a third-party implementation
  test_reference_statsmodels_f05.py  F-05 counter-examples, without our search
  test_allocation_rule_rates.py      the measured rates quoted in F-09
  test_cli.py                the CLI contract
  test_mcp_server.py         MCP tools == engine output
  test_mcp_stdio_e2e.py      the server as a real subprocess over stdio
  test_effectsize.py         both pooling options (F-11)
  test_cleanroom_conformance.py  the 2nd implementation, same contract
  test_spec_f13.py           each of F-13's twelve resolutions
  test_agent_offline.py      the agent loop, driven with a stub client
  test_gpower_observed.py    [REA] the engine prints what G*Power printed
  test_compliance.py         the submission rules
cleanroom/
  src/gpower_cleanroom/      the independent 2nd implementation (Session B)
  SPEC-GAPS.md               the 12 gaps it reported against SPEC.md v1.0
  selfcheck.py               its own 56 self-checks
  SPEC.md, INTERFACE.md      exactly what it was allowed to read
```

---

## Licence and attribution

MIT ([LICENSE](LICENSE)). **This is not G\*Power** and is not affiliated with
or endorsed by its authors. If this contributes to published research, cite
G\*Power for the method — Faul, Erdfelder, Lang & Buchner (2007) and Faul,
Erdfelder, Buchner & Lang (2009). See [ETHICS.md](ETHICS.md).
