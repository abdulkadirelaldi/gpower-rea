# ARCHITECTURE.md

## The one rule

> **Rule 3 of the assignment:** the computation lives in a single engine; the
> CLI, the MCP server and the agent are thin layers that call it.

This repository enforces that mechanically rather than trusting it:

```console
$ python tools/compliance_check.py
COMPLIANCE: PASS
  C-1 no original binary or installer in the tree
  C-2 no decompiler / disassembler output
  C-3 one engine; CLI, MCP and agent are adapters over it
  C-4 findings <-> SPEC.md <-> docs/EVIDENCE are in sync
```

`C-3` greps every module for `nct_cdf(` and fails if it appears outside
`engine.py` / `numerics.py`; it fails if `cli.py` or `mcp_server.py` does not
import the engine; and it fails if `agent/agent.py` contains arithmetic at all.
The check runs in CI and as `tests/test_compliance.py`.

---

## Layers

```
                         ┌───────────────────────────────┐
  natural language ──────►  agent/agent.py               │   Claude Opus 5
                         │  (Anthropic SDK, tool loop)   │   + MCP client
                         └──────────────┬────────────────┘
                                        │ MCP (stdio)
                         ┌──────────────▼────────────────┐
                         │  gpower_rea/mcp_server.py     │   6 tools
                         │  FastMCP, pass-through only   │
                         └──────────────┬────────────────┘
                                        │
  shell / CI ────────────►┌─────────────▼────────────────┐
                         │  gpower_rea/cli.py            │   argparse, CSV/JSON
                         │  solve · batch · selftest …   │
                         └──────────────┬────────────────┘
                                        │
  Python import ─────────►┌─────────────▼────────────────┐
                         │  gpower_rea/engine.py         │  ◄── THE ENGINE
                         │  power() · solve() · curve()  │
                         │  allocation rules · searches  │
                         └──────┬─────────────────┬──────┘
                                │                 │
              ┌─────────────────▼──┐   ┌──────────▼─────────────┐
              │ procedures.py      │   │ numerics.py            │
              │ 6 × (ν, δ) maps    │   │ norm · beta · gamma    │
              │ + validation       │   │ central t · noncentral t│
              └────────────────────┘   └────────────────────────┘
                    effectsize.py  ·  report.py   (pure, no state)
```

Every arrow points **down**. There is no path from the engine upward, so the
engine is importable with nothing but the standard library — which is also a
test:

```python
# tests/test_compliance.py
def test_engine_has_no_runtime_dependencies():
    """Blocks numpy/scipy/pandas/mcp/anthropic at import time, then runs the CLI."""
```

---

## Module responsibilities

| module | lines (approx.) | owns | must not |
|---|---|---|---|
| `numerics.py` | 420 | `Φ`, `Φ⁻¹`, incomplete beta/gamma, central *t* CDF & quantile, χ², Gauss–Legendre nodes, **noncentral *t* CDF** | know what a power analysis is |
| `procedures.py` | 330 | the six `(ν, δ)` maps, effect-size domains, extra-parameter validation, alias resolution | compute power |
| `engine.py` | 530 | the single power formula, the five analysis types, allocation rules, integer & scalar searches, the `Result` object | format output |
| `effectsize.py` | 180 | the "Determine ⇒" calculators | call the engine |
| `report.py` | 150 | the GUI-style protocol block and the APA sentence | compute anything |
| `cli.py` | 700 | argument parsing, CSV/JSON I/O, exit codes, batch column matching | arithmetic |
| `mcp_server.py` | 240 | 6 MCP tool definitions + error-to-data conversion | arithmetic |
| `agent/agent.py` | 260 | the model loop, the system prompt, the MCP session | arithmetic (CI-enforced) |

`procedures.py` is the extension point. Adding *F tests* or *χ² tests* means
adding `Procedure` objects — the engine, CLI, MCP server and agent pick them up
with no edit, because every one of them enumerates `PROCEDURES` at runtime
rather than hard-coding a list.

---

## Why "one engine" is more than tidiness

It is what makes the three interfaces *verifiably* equivalent:

```python
# tests/test_mcp_server.py — the MCP tool must return the engine's dict verbatim
def test_power_analysis_delegates_to_the_engine():
    payload = _call("power_analysis", {...})
    ref = solve("ttest-indep-means", "n", ...).as_dict()
    assert payload["result"] == ref        # equality, not approximately
```

So an answer an agent gives in prose is reproducible by a grader typing a
`gpower solve` command — byte for byte, through a different code path. That is
the property the assignment's "thin layers" rule is actually protecting, and
testing it costs one assertion.

---

## Data flow of one request

```
"I have two groups of 40, d = 0.6, what's my power?"
        │
        ├─ agent: picks ttest-indep-means, fills defaults (α .05, two tails),
        │          says so, and calls one tool. Computes nothing.
        │
        ├─ mcp_server.power_analysis(test=…, solve_for="power", …)
        │          → engine.solve(...)              → returns .as_dict()
        │          → report.text_block / apa_sentence
        │
        └─ engine.solve
             ├─ procedures.resolve("ttest-indep-means")
             ├─ Procedure.normalise_extra({})         (validation)
             ├─ _explicit_sample(n1=40, n2=40)        → Sample(40, 40)
             ├─ Procedure.df / .ncp                   → (78, 2.683)
             ├─ numerics.t_ppf(0.975, 78)             → 1.99085
             ├─ numerics.nct_cdf(±1.99085, 78, 2.683) → F-02 both tails
             └─ Result(power=0.7564, …)
```

The noncentral-*t* evaluation at the bottom is reached exactly once per power
value, from exactly one call site (`engine._power_from_ncp`).

---

## Numerical design notes

Two decisions carry the accuracy (details and measurements in
[VALIDATION.md](VALIDATION.md)):

1. **The noncentral *t* CDF is a mixture, not a series.** With
   `T = (Z+δ)/√(V/ν)`, `T(x;ν,δ) = E_S[Φ(x·S − δ)]` for `S = √(V/ν)`. The
   integrand is smooth and unimodal, so 24-point Gauss–Legendre on panels cut
   at χ² quantiles reaches `1.7e-14` for every `ν` from 1 to 10 000 — whereas
   the classical series (AS 243) degrades for large `|δ|`. Panel edges and
   Legendre nodes are cached per `ν`, so a 40-step sample-size search costs
   roughly 15 ms.

2. **Cancellation is removed, not tolerated.** `lgamma(a+b) − lgamma(a)` is
   rewritten so every Stirling term is `O(1)`, and the incomplete beta takes
   `1−x` as a separate argument instead of recovering it by subtraction. Those
   two changes moved the central *t* CDF from `4.1e-13` to `2.9e-14` and the
   quadrature mass closure from `8.7e-12` to `2.1e-14`. Both are documented in
   [SPEC §4](../SPEC.md#4-numerical-requirements) as warnings to the next
   implementer.

Zero runtime dependencies is a consequence, not a goal: the standard library
has `erfc`, `lgamma` and `log1p`, and everything else is 420 lines. The
payoff is that `pip install gpower-rea` cannot fail on a wheel build, and CI
needs no scientific stack to run the gate.

---

## Extension checklist

To add a statistical test:

1. Add a `Procedure` to `procedures.py` with its `(ν, δ)` map, effect-size
   domain, minimum design and `spec_refs`.
2. Add the corresponding `F-nn` finding to `SPEC.md` and an `E-nnn` evidence
   file (`compliance_check.py` fails if either is missing).
3. Add probe rows to `tools/probe_plan.py`.
4. Extend `tools/make_vectors.py` and regenerate.
5. Extend the reference implementation in `tests/test_reference_scipy.py`.

Nothing in `cli.py`, `mcp_server.py` or `agent/agent.py` changes.
