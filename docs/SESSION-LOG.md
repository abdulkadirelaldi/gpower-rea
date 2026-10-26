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
| 10 | Arbitration by a 50-digit computation wherever a library disagreed | two numerical defects in the engine found and fixed; twice the library was the less accurate party | done |
| 11 | Interfaces — CLI, MCP server, agent | `cli.py`, `mcp_server.py`, `agent/agent.py` | done |
| 12 | Compliance automation | `tools/compliance_check.py` in CI | done |
| 13 | **GUI probe execution** | `probes/REA-RESULTS.md` | **PENDING — 36 rows unobserved** |
| 14 | **Two-session clean-room attestation** | the table below | **UNSIGNED** |

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

## Attestation 2 — two separate sessions

`SPEC.md` was written before the engine and frozen, and the engine traces only
to `SPEC.md` findings (machine checked, `compliance_check.py` C-4). The
*procedural* separation into two independent agent sessions has not been
executed.

| field | value |
|---|---|
| Session A branch / commit | _unsigned_ |
| Session B branch / commit | _unsigned_ |
| Handover artefact | `SPEC.md` v1.0 (frozen) |
| Session B inputs withheld | `src/gpower_rea/`, `docs/EVIDENCE/`, `probes/` |
| `pytest` result on Session B's implementation | _unsigned_ |
| `gpower selftest` result on Session B's implementation | _unsigned_ |
| Date | _unsigned_ |

**To sign:** follow
[CLEANROOM-PROTOCOL §6](CLEANROOM-PROTOCOL.md#6-executing-and-signing-the-two-session-pass)
and fill in the table.

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
| the engine's `t` quantile beats SciPy's, arbitrated by mpmath | `test_numerics.py` |
| the engine beats statsmodels against an exact reference | `test_reference_statsmodels.py` |
| every text file is intact UTF-8 (the evidence files are the deliverable) | `compliance_check.py` C-5 |
| MCP tools return the engine's output verbatim | `test_mcp_server.py` |
| the MCP server works as a real stdio subprocess | `test_mcp_stdio_e2e.py` |
| CLI contract (exit codes, schema, batch aliasing) | `test_cli.py` |

Recorded result of the last full run: **698 passed, 1 skipped**,
`COMPLIANCE: PASS`, `selftest: 401/401 exact N matches (rate 1.0000)`.
The skip is the clean-room conformance file, which runs only when a second
implementation is present.
