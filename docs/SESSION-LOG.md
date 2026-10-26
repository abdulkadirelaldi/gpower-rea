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
| 11c | **Agent run against the live Anthropic API** (`agent/agent.py`) | — | **not run — no API key on the build machine**; the same MCP server was driven live by Claude Code instead (row 24) |
| 12 | Compliance automation | `tools/compliance_check.py` in CI | done |
| 13 | **GUI probe execution** | `probes/observations/`, `probes/REA-RESULTS.md` | **done — 33/36 pre-registered rows observed (F-11's 3 rows unreachable, see below)** |
| 14 | Two-session clean-room implementation | `cleanroom/`, 12-gap report | done |
| 15 | Clean-room conformance judgement | `tools/judge_cleanroom.py` — **CONFORMING**, 401/401 | done |
| 16 | Gap divergence probe | `tools/probe_spec_gaps.py` — 5 live defects found | done |
| 17 | Specification repair round 2 | `SPEC.md` v1.0 → v1.1 (F-13), engine 1.0.0 → 1.1.0 | done |
| 18 | Numerics overhaul driven by (16) | log-scale quadrature, Φ-transition panels, `nct_sf`, `t_isf` | done |
| 19 | **GUI driver** — G\*Power 3.1.9.6 for macOS driven black-box through the Accessibility API | `tools/gpower_ax.py`, `tools/rea_campaign.py` | done |
| 20 | **Pre-registration stamped** — 26 supported, **2 refuted** (F-08, F-09) | `tools/stamp_worksheet.py`, `probes/REA-RESULTS.md` | done |
| 21 | Mechanism probes — ratio sweep, fine power sweep, sign sweep, domain edges, 240-row random grid | 443 recorded runs | done |
| 22 | **Specification repair round 3** — F-05/F-06/F-08/F-09 rewritten from observation; F-14, F-15 added | `SPEC.md` v1.1 → **v1.2**, engine 1.1.0 → **1.2.0** | done |
| 23 | Engine numerical defect found by observation — critical value `2.7e-6` off at `ν = 1e11` | Cornish–Fisher branch in `t_isf` (SPEC §4 item 6) | done |
| 24 | Agent run live over the MCP server (Claude Code harness) — found an output defect, fixed | `agent/transcripts/` | done |
| 25 | Second clean-room session, from SPEC v1.2 → 19 gaps; v1.3 (F-16) → 4 more, two settled by G\*Power (an **empty group** is a real G\*Power output) | `cleanroom/`, `SPEC-GAPS-v1.2.md`, `SPEC-GAPS-v1.3.md`; SPEC v1.3, engine 1.3.0 | done — **CONFORMING**, 225/225 against G\*Power ([CLEANROOM-PROTOCOL §4b](CLEANROOM-PROTOCOL.md)) |

---

## Attestation 1 — GUI probes · **SIGNED**

```console
$ python tools/harvest.py
  SUPPORTS     26
  AMBIGUOUS    5
  CONTRADICTS  2
  UNEXPLAINED  0
  PENDING      3
$ python tools/rea_report.py
cases=443 match=404 both_refuse=25 mismatch=14 apriori_N_exact=225/229
```

| field | value |
|---|---|
| G\*Power version probed | **3.1.9.6 for macOS**, `GPowerMac_3.1.9.6.zip` from the authors' site, SHA-256 `841390e00110ccdd5201f334af985b54837b9f9b4ffb3151d49e28efb9bb3964`, notarised Developer ID of Albert-Georg Lang |
| Platform | macOS 27.0.1 (Apple silicon; the x86_64 build under Rosetta), comma-decimal locale |
| Instrument | `tools/gpower_ax.py` — macOS Accessibility API; inputs typed into labelled fields, outputs read from the *Output parameters* panel, every input echo verified |
| Operator | Claude Code session (analysis session, "Session A"), on the student's machine, with the student's permission |
| Date | 2026-10-26 |
| Runs recorded | **443** distinct inputs (`probes/observations/*.jsonl`) |
| Pre-registered rows observed | 33 / 36 — the 3 F-11 rows need the effect-size drawer, which this build does not expose to the Accessibility API |
| `CONTRADICTS` | 2 — `P-08-a` (F-08), `P-09-c` (F-09). Both findings were rewritten from the observations (SPEC v1.2) |
| Outside F-14 | **429 / 429** identical in every printed field |

The binary was not copied into the repository, not disassembled, not
decompiled, and not inspected beyond its code signature.

---

## Attestation 1b — the agent, live · **PARTLY SIGNED**

| field | value |
|---|---|
| `agent/agent.py` model | `claude-opus-5-5`, adaptive thinking, effort `high`, server-side refusal fallbacks |
| `agent/agent.py` live run | **not run** — no Anthropic API key on the build machine; the loop is covered by 22 offline tests |
| Live natural-language run over **the same MCP server** | **done**, 2026-10-26, Claude Code 2.1.310 headless as the harness, model `claude-opus-5-5`, tools restricted to the six `gpower` MCP tools |
| Transcript | [agent/transcripts/2026-10-26-unbalanced-a-priori.md](../agent/transcripts/2026-10-26-unbalanced-a-priori.md) |
| Every number in the answer from a tool call | yes — and each is re-derived there through the CLI |
| Defects it found | the post-hoc report printed the default allocation ratio; `ttest-independent` was not an alias. Both fixed. |

**To sign the remaining row:** `ant auth login` (or export
`ANTHROPIC_API_KEY`), then

```console
$ python agent/agent.py -v "iki grubum var, her birinde 40 kişi, d=0.6, gücüm ne?"
$ gpower solve -t indep -s power -a 0.05 -e 0.6 --n1 40 --n2 40 --json
```

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
$ python tools/compliance_check.py        # COMPLIANCE: PASS (C-1..C-5)
$ python tools/rea_report.py              # the engine against 443 G*Power readings
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
| **the engine prints what G\*Power 3.1.9.6 printed, for every recorded run** | `test_gpower_observed.py`, `tools/rea_report.py` |
| the pre-registered predictions were not edited after observation | `stamp_worksheet.py` writes only `observed`; CI diffs `probes/` |
| the clean-room implementation conforms to the same contract | `test_cleanroom_conformance.py`, `tools/judge_cleanroom.py` |
| the two implementations are lexically independent | `test_implementations_are_lexically_independent` |
| each of F-13's twelve resolutions | `test_spec_f13.py` |

Recorded result of the last full run: **1541 passed**, `COMPLIANCE: PASS`,
`selftest: 401/401 exact N matches (rate 1.0000)`,
`judge_cleanroom: CONFORMING`.
