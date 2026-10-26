# gpower-rea

**Sample size and statistical power for the G\*Power *t tests* family — from a
command line, from an MCP server, or in plain language.**

G\*Power is the tool clinical researchers use to answer *"how many participants
do I need?"*. It is free and excellent, and it has only a graphical interface:
no CLI, no API, nothing scriptable. An AI agent can drive it only by taking
screenshots and clicking, which is slow, expensive and silently unreliable.

This repository reverse engineers one of its test families behaviourally,
documents the findings with evidence, reimplements it clean-room, and gives it
three interfaces.

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

Those are the canonical published G\*Power numbers for that design, reproduced
to all seven printed decimals.

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

Claude Opus 5 over the MCP server. Its system prompt forbids it from stating
any number that did not come back from a tool call, and
`tools/compliance_check.py` fails the build if the agent file contains
arithmetic at all. See [agent/README.md](agent/README.md).

---

## What was reverse engineered

Twelve findings, each with an evidence file, each labelled by how strongly it
is established — and every one of them is behaviour the documentation does not
settle:

| # | finding | status |
|---|---|---|
| [F-01](SPEC.md#f-01--one-model-for-the-whole-family) | the whole family reduces to one `(ν, δ)` pair | derived |
| [F-02](SPEC.md#f-02--two-sided-power-retains-the-far-tail-term) | **two-sided power keeps the wrong-side tail** — at `δ=0` the two candidate formulas differ by a factor of two | behavioural |
| [F-03](SPEC.md#f-03--one-sample-and-matched-pairs-ν--n---1-δ--es√n) | matched pairs counts *pairs*, not observations | derived |
| [F-04](SPEC.md#f-04--point-biserial-ν--n---2-δ--r√n1-r²) | point biserial: `δ` uses `√N`, the statistic uses `√(N−2)` | derived |
| [F-05](SPEC.md#f-05--balanced-a-priori-search-runs-over-n-per-group-not-total-n) | **the balanced search runs per group, so the total is never odd** — and an odd split would already have sufficed in **50 %** of settings | behavioural |
| [F-06](SPEC.md#f-06--minimality-and-actual-power-is-recomputed) | `≥` not `>`, and "Actual power" is a recomputation (`0.9501287`, not `0.9500000`) | behavioural |
| [F-07](SPEC.md#f-07--regression-coefficient-ν--n---p---1-δ--f²n) | the predictor count enters `ν` only, never `δ` | derived |
| [F-08](SPEC.md#f-08--a-negative-effect-size-is-a-direction-not-an-error) | a negative effect size is a direction; only the solvers absolutise it | open |
| [F-09](SPEC.md#f-09--allocation-ratio-rounding) | **two candidate grids for unbalanced allocation** that disagree on **75.7 %** of settings by 1–3 participants; rounding is half-away-from-zero | open |
| [F-10](SPEC.md#f-10--compromise-analysis-is-defined-on-the-critical-value) | compromise analysis solves for the critical value | derived |
| [F-11](SPEC.md#f-11--the-effect-size-drawer-offers-two-pooled-sds-and-the-equal-n-one-is-an-rms) | **the equal-*n* pooling option is an RMS, not a pooled SD** — 49 % difference in required `N` on a realistic example | open |
| [F-12](SPEC.md#f-12--boundary-behaviour-and-reported-precision) | no epsilon slack at the boundary; display rounding is display only | open |

Read [SPEC.md](SPEC.md) for the specification,
[docs/EVIDENCE/](docs/EVIDENCE/) for the twelve evidence files, and
[docs/REA-METHOD.md](docs/REA-METHOD.md) for the method — in particular, why
every probe is built around *competing predictions* rather than observations.

---

## How do you prove the engine is right?

The assignment's question. Five answers, four of which need no G\*Power
installation at all:

| # | check | result |
|---|---|---|
| 1 | 401 reference vectors, exact integer `N` | **401 / 401** |
| 2 | independent re-derivation: SciPy + brute-force linear search, from `SPEC.md` | **401 / 401**, post-hoc power within `1e-10` |
| 3 | an implementation written by *other people* (`statsmodels`) | agrees, **including the far-tail term of F-02** — so that formula is what two unrelated implementations arrived at |
| 4 | property tests: monotonicity, minimality, five-way round trips, three cross-entry identities | all pass, no golden values involved |
| 5 | arbitration by a 50-digit `mpmath` computation wherever the engine and a library disagree | engine `3.8e-15` vs SciPy `7.9e-11`; statsmodels is off by up to `7.2e-5` near power 1 vs the engine's `1.2e-11`. **Two numerical defects in the engine were found and fixed this way** |
| 6 | 36-row GUI probe worksheet with pre-registered competing predictions | generated and runnable, **0 rows observed** |

The rule the project settled on: *a second implementation settles what the
answer is; only a higher-precision computation settles who is right.*

Numbers, grids and tolerances in [docs/VALIDATION.md](docs/VALIDATION.md).
Check 6 is **unsigned** — it needs a G\*Power installation — and
[docs/SESSION-LOG.md](docs/SESSION-LOG.md) says so in a table rather than
burying it.

```console
$ python -m pytest -q                     # 698 passed
$ gpower selftest                         # 401/401 exact N matches (rate 1.0000)
$ python tools/compliance_check.py        # COMPLIANCE: PASS (C-1..C-4)
$ python tools/make_vectors.py --check    # vectors are a function of the engine
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
PUBLISH.md                   how to get this onto GitHub (git is not installed here)
docs/
  REA-METHOD.md              how the behaviour was established, and its limits
  EVIDENCE/E-001 … E-012     one file per finding: claim, probe, predictions
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
agent/agent.py               Claude Opus 5 over MCP
tools/
  probe_plan.py              generate the GUI probe worksheet
  harvest.py                 stamp observations into a verdict per finding
  make_vectors.py            regenerate / verify the vector file
  judge_cleanroom.py         hold the independent 2nd implementation to the contract
  compliance_check.py        the submission rules, as a machine check
  publish.ps1                verify, commit and push (refuses if the gate fails)
probes/
  probe_worksheet.{csv,md}   36 rows with competing pre-registered predictions
  REA-RESULTS.md             per-finding verdict (currently all PENDING)
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
  test_compliance.py         the submission rules
cleanroom/src/gpower_cleanroom/  the independent 2nd implementation (Session B)
```

---

## Licence and attribution

MIT ([LICENSE](LICENSE)). **This is not G\*Power** and is not affiliated with
or endorsed by its authors. If this contributes to published research, cite
G\*Power for the method — Faul, Erdfelder, Lang & Buchner (2007) and Faul,
Erdfelder, Buchner & Lang (2009). See [ETHICS.md](ETHICS.md).
