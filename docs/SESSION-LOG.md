# SESSION-LOG.md — what was done, in what order, and what is still unsigned

This file exists so that the provenance claims elsewhere in the repository can
be checked rather than taken on trust. It is deliberately blunt about the
difference between *done* and *ready to be done*.

---

## Phase log

| # | phase | output | status |
|---|---|---|---|
| 1 | Target scoping — pick one test family and enumerate its menu entries | the six `Procedure` keys | done |
| 2 | Candidate enumeration — for each behaviour, write down ≥2 plausible implementations | the `competing_prediction` column of the probe worksheet | done |
| 3 | Probe design — find inputs where the candidates separate by more than printed precision | `tools/probe_plan.py`, 36 rows, 28 discriminating | done |
| 4 | Derivation — use the three cross-entry identities to pin what algebra can pin | F-01, F-03, F-04, F-07, F-10 marked `REA-DERIVED` | done |
| 5 | **Specification** — `SPEC.md` v1.0, frozen | 12 findings, tolerance table, both allocation rules | done |
| 6 | Evidence catalogue | `docs/EVIDENCE/E-001 … E-012` | done |
| 7 | Implementation from `SPEC.md` | `src/gpower_rea/` (engine, 6 procedures, numerics) | done |
| 8 | Specification repair — four gaps found while implementing, fixed in `SPEC.md`, not guessed | see [CLEANROOM-PROTOCOL §5](CLEANROOM-PROTOCOL.md#5-specification-gaps-closed-before-the-engine-was-written) | done |
| 9 | Independent re-derivation with SciPy + brute-force search | `tests/test_reference_scipy.py`, 401/401 | done |
| 9b | Agreement oracle written by other people (`statsmodels`) | `tests/test_reference_statsmodels.py`; independently confirms the F-02 far-tail term | done |
| 10 | Arbitration by a 50-digit computation wherever a library disagreed | six numerical defects in the engine found and fixed | done |
| 10b | **Correction**: an early draft asserted the engine beat SciPy and statsmodels. True on the dev machine, false on the versions CI installs. Tests rewritten to assert the engine's own error and mere agreement | [VALIDATION §3.2](VALIDATION.md) | done |
| 11 | Interfaces — CLI, MCP server, agent | `cli.py`, `mcp_server.py`, `agent/agent.py` | done |
| 11b | Agent loop tested offline against a stub client | `tests/test_agent_offline.py`, 22 tests | done |
| 11c | **Agent run against the live Anthropic API** | — | **NOT VERIFIED — no credentials on the build machine** |
| 12 | Compliance automation | `tools/compliance_check.py` in CI | done |
| 13 | **GUI probe execution** | `probes/REA-RESULTS.md` | **PENDING — 36 rows unobserved** |
| 14 | Two-session clean-room implementation | `cleanroom/`, 12-gap report | done |
| 15 | Clean-room conformance judgement | `tools/judge_cleanroom.py` — **CONFORMING**, 401/401 | done |
| 16 | Gap divergence probe | `tools/probe_spec_gaps.py` — 5 live defects found | done |
| 17 | Specification repair round 2 | `SPEC.md` v1.0 → v1.1 (F-13), engine 1.0.0 → 1.1.0 | done |
| 18 | Numerics overhaul driven by (16) | log-scale quadrature, Φ-transition panels, `nct_sf`, `t_isf` | done |

---

## Attestation 1 — GUI probes

The probe harness is generated and runnable; no observation has been entered.

```console
$ python tools/harvest.py
  SUPPORTS     0
  AMBIGUOUS    0
  CONTRADICTS  0
  UNEXPLAINED  0
  PENDING      36
```

| field | value |
|---|---|
| G\*Power version probed | _not yet run_ |
| Platform | _not yet run_ |
| Operator | _not yet run_ |
| Date | _not yet run_ |
| Rows observed | 0 / 36 |
| `CONTRADICTS` / `UNEXPLAINED` | 0 / 0 |

**To sign:** run `python tools/probe_plan.py`, fill the `observed` column of
`probes/probe_worksheet.csv` from the GUI, run `python tools/harvest.py`, then
fill in the table above and commit both the worksheet and
`probes/REA-RESULTS.md`.

What is *not* pending: the five `REA-DERIVED` findings are proven offline by
the cross-entry consistency tests
([VALIDATION.md §4](VALIDATION.md#4-property-tests--correctness-without-golden-values)),
and the canonical published example is reproduced to all seven printed decimals
([E-001](EVIDENCE/E-001-common-noncentral-t-model.md)).

---

## Attestation 1b — the agent against the live API

Everything around the model call is tested (22 offline tests driving the loop
with a stub client, plus the stdio transport end-to-end). The model call
itself is not: the build machine has no Anthropic credentials, so
`python agent/agent.py "..."` has never been executed here.

| field | value |
|---|---|
| Model configured | `claude-opus-5`, adaptive thinking, effort `high` |
| SDK surface verified | `client.beta.messages.tool_runner` accepts `system`, `thinking`, `output_config`, `betas`, `fallbacks`; the runner is async-iterable and exposes `generate_tool_call_response` |
| MCP transport verified | yes — `tests/test_mcp_stdio_e2e.py` spawns the server and round-trips a tool call |
| Live API call | _not run_ |
| Sample transcript | _not captured_ |

**To sign:** `ant auth login` (or export `ANTHROPIC_API_KEY`), then

```console
$ python agent/agent.py -v "iki grubum var, her birinde 40 kişi, d=0.6, gücüm ne?"
$ gpower solve -t indep -s power -a 0.05 -e 0.6 --n1 40 --n2 40 --json
```

and paste both outputs here. The second command is the point: the agent's
number must be reproducible through a different code path.

---

## Attestation 2 — two separate sessions · **SIGNED**

| field | value |
|---|---|
| Handover artefact | `SPEC.md` **v1.0**, frozen at commit `aad154e`, tag `spec-frozen-v1.0` |
| Session A (analysis + spec) | this session; produced `SPEC.md` v1.0 and `docs/EVIDENCE/E-001…E-012` |
| Session B (implementation) | a separate agent session, launched with only `cleanroom/SPEC.md` and `cleanroom/INTERFACE.md` in its working directory |
| Inputs withheld from Session B | `src/gpower_rea/`, `docs/EVIDENCE/`, `probes/`, `tests/`, `src/gpower_rea/data/public_vectors.csv`, the G\*Power application and its manual, the web |
| Session B deliverables | [`cleanroom/src/gpower_cleanroom/`](../cleanroom/src/gpower_cleanroom/) (7 modules), [`cleanroom/selfcheck.py`](../cleanroom/selfcheck.py) (56 self-checks), [`cleanroom/SPEC-GAPS.md`](../cleanroom/SPEC-GAPS.md) (12 gaps) |
| Third-party imports in Session B's code | **none** — standard library only, asserted by `test_no_third_party_imports` |
| **Conformance verdict** | **CONFORMING** — 401/401 exact `N`, 401/401 powers within `5e-7`, all 7 SPEC properties, all 4 round trips, 300/300 on the cross-implementation grid |
| Independence (lexical overlap) | Jaccard **0.204**; shared private helpers `_SQRT2`, `_STIRLING_MIN`; **0** identical comment lines |
| Specification defects found | **12 reported, 5 live** (`G-01`, `G-03`, `G-04`, `G-05`, `G-11`) |
| Of those, a wrong answer in the shipped engine | **1** — `G-05`, the criterion analysis returned `1e-12` where the answer was `4.2e-60` |
| Numerical defects adopted from Session B's approach | **3** — log-scale quadrature, Φ-transition panels, direct survival function (defects 3–5 in [VALIDATION §3.3](VALIDATION.md)) |
| Outcome | `SPEC.md` v1.0 → **v1.1** (F-13 closes all twelve points); engine 1.0.0 → **1.1.0** |
| Verified by | `python tools/judge_cleanroom.py`, `python tools/probe_spec_gaps.py`, `tests/test_cleanroom_conformance.py` (17 tests), `tests/test_spec_f13.py` |

### What the exercise actually bought

Not a second opinion — a set of defects that were structurally invisible
without it:

* **One wrong answer.** `G-05`. Every test the engine had either round-tripped
  through its own bisection or compared against a reference that used the same
  bracket, so the floor-return was self-consistent and undetectable.
* **Three numerical improvements.** Session B reparametrised the quadrature to
  `y = log s` and computed the survival function directly. Both were better,
  and adopting them turned a *wrong answer* below `ν = 1` (size `0.252` where
  `α` was `0.100`) into `6.7e-16`, and gave relative — not merely absolute —
  accuracy for a small power.
* **Four latent ambiguities** that had not bitten yet but would have, in any
  third implementation.

### Honest caveats

* The boundary was enforced by the handover prompt plus a physically separate
  input directory, **not** by a sandbox. It is verified after the fact by the
  lexical-overlap report above, which is evidence rather than proof.
* Session B implemented v1.0. Three of the five divergences are closed in
  v1.1 by *stating this engine's convention*, which the clean room had no way
  to know. Those are documentation fixes, not bugs on either side, and F-13
  labels them as choices.
* None of this is evidence about G\*Power. It is evidence that the
  specification is now strong enough to be implemented twice with the same
  result — which is a different and more modest claim.

---

## What is signed, right now, by machine

Everything in this list is a command a reader can run:

```console
$ python tools/compliance_check.py        # COMPLIANCE: PASS (C-1..C-4)
$ python tools/make_vectors.py --check    # vectors are a function of the engine
$ python -m pytest -q                     # property tests + SciPy re-derivation
$ gpower selftest                         # 401/401 exact N
```

| claim | checked by |
|---|---|
| no G\*Power binary or installer in the tree | `compliance_check.py` C-1 |
| no decompiler / disassembler output | `compliance_check.py` C-2 |
| one engine; CLI/MCP/agent are adapters | `compliance_check.py` C-3, `test_mcp_server.py` |
| every code finding exists in `SPEC.md`, every cited evidence file exists | `compliance_check.py` C-4 |
| engine imports with no third-party package | `test_compliance.py` |
| vector file is not stale | `make_vectors.py --check` |
| 401 vectors re-derived by an independent implementation | `test_reference_scipy.py` |
| a third-party implementation agrees, far-tail term included | `test_reference_statsmodels.py` |
| the engine's `t` quantile is within `1e-13` of a 50-digit computation | `test_numerics.py` |
| the engine's power is within `1e-10` of an exact reference | `test_reference_statsmodels.py` |
| the engine agrees with SciPy (`1e-9` rel) and statsmodels (`1e-4`) | both files |
| every text file is intact UTF-8 (the evidence files are the deliverable) | `compliance_check.py` C-5 |
| MCP tools return the engine's output verbatim | `test_mcp_server.py` |
| the MCP server works as a real stdio subprocess | `test_mcp_stdio_e2e.py` |
| CLI contract (exit codes, schema, batch aliasing) | `test_cli.py` |

| the clean-room implementation conforms to the same contract | `test_cleanroom_conformance.py`, `tools/judge_cleanroom.py` |
| the two implementations are lexically independent | `test_implementations_are_lexically_independent` |
| each of F-13's twelve resolutions | `test_spec_f13.py` |

Recorded result of the last full run: **850 passed**, `COMPLIANCE: PASS`,
`selftest: 401/401 exact N matches (rate 1.0000)`,
`judge_cleanroom: CONFORMING`.
