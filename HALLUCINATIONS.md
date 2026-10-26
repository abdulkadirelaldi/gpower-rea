# HALLUCINATIONS.md — what the agent got wrong, how it was noticed, what caught it

Every entry below happened in this project. The agent (Claude, in Claude Code)
stated each one confidently; each one was wrong. The pattern is the lesson:
**every one of them passed every check that did not involve the original
program** — and was caught either by G\*Power itself or by a second,
independent reading of the specification.

| # | the agent's claim | reality | how it was noticed | what caught it |
|---|---|---|---|---|
| H-1 | *"With an allocation ratio ≠ 1, G\\*Power searches `n₁ = 2, 3, …` and sets `n₂ = round(R·n₁)`"* (SPEC v1.1 F-09, the engine's default rule) | G\\*Power searches **even totals** and tests the **unrounded** split; `R = 2`, `d = 0.5`, power `.95` gives `79 / 157`, not `79 / 158` | the first GUI reading of a pre-registered row contradicted it | `probes/probe_worksheet.csv` row `P-09-c` (**CONTRADICTS**), then `tools/fit_allocation.py` (old rule: 55 / 119 rows) and `tests/test_gpower_observed.py` |
| H-2 | *"A one-tailed post-hoc test with a negative d has power below α (7.7e-06)"* (SPEC v1.1 F-08) | G\\*Power computes from `\|δ\|`: power `0.8482542`; only the signs of `δ` and `t` change | pre-registered row `P-08-a` | `P-08-a` (**CONTRADICTS**), `tests/test_spec_f13.py::test_the_sign_rule_still_applies_to_d_dz_and_generic_delta` |
| H-3 | *"Actual power strictly exceeds the target"* (SPEC v1.1 F-06; also in the agent's own system prompt) | with unequal groups it can be **below**: target `0.9495` → `87 / 131`, actual `0.9494095` | the fine power sweep `S-*` | sweep row `S-019`; `tests/test_gherkin_spec.py::test_scenario_actual_power_below_target` |
| H-4 | *"Every group has at least one participant"* — the engine clamped each group to `≥ 1` and printed `1 / 5` with power `1.0` for `d = 20`, `R = 100` | G\\*Power prints **`0 / 6`**, `δ = 0`, *Actual power* `0.0500000` | the clean-room session read SPEC literally and got `0 / 6`; it reported the point as gap G3-01 | probe `X-G3-01a`; `tests/test_spec_f16.py::test_g3_01_even_total_reports_an_empty_group_like_gpower` |
| H-5 | *"The engine is more accurate than SciPy and statsmodels"* (an early draft of VALIDATION) | true on the development machine's library versions, false on the versions CI installs | CI failed on another machine | the test was rewritten to measure the engine against a 50-digit `mpmath` oracle instead (commit `a94f122`) |
| H-6 | *"The critical value is accurate to 1e-14 everywhere"* (SPEC §4 table) | at `ν = 1e11` it was `2.7e-6` relative off | G\\*Power returned `N = 7.8e10` for `d = 1e-5`; re-scoring that row exposed the engine's own critical value | row `D-31`, then a 40-digit `mpmath` sweep; fixed by a Cornish–Fisher branch (SPEC §4 item 6) |
| H-7 | *"`d = 1e-5` has no solution"* — the engine refused it (search cap `1e7`) | G\\*Power answers `N = 78 488 272 181` | domain probe | `D-31` (`tests/test_gpower_observed.py`) |
| H-8 | in the agent transcript, a "verification" line read *`power = 0.9484904`* for `78 + 156` | the CLI prints `0.9485150`; the agent had typed a plausible number instead of copying the output | re-running the three commands before publishing the transcript | the command output itself; the line was replaced by real output (`agent/transcripts/`) |
| H-9 | *"G\\*Power's release notes describe no change to this family between 3.1.9.6 and 3.1.9.7"* | never checked | self-review before commit: no source could be named | removed; [docs/REA-METHOD.md §6](docs/REA-METHOD.md) now says the Windows build was not compared |
| H-10 | *"A post-hoc design with 79 + 158 has allocation ratio 1"* — the report printed the default ratio | the ratio of an explicit design is `n₂/n₁ = 2` | the live agent run noticed the inconsistency in the tool output and said so to the user | `agent/transcripts/2026-10-26-unbalanced-a-priori.md`; `tests/test_engine_invariants.py::test_an_explicit_design_reports_its_own_ratio_not_the_default` |

## Why H-1 matters most

H-1 was not a careless guess. It was a documented, tested rule that agreed
with three independent oracles: a SciPy re-derivation, `statsmodels`, and a
clean-room implementation written by a separate agent session. All four
implemented the same plausible reading of the documentation, so they agreed
with each other — and disagreed with G\\*Power on **32 % of all a-priori
designs and 61 % of unbalanced ones**. Agreement between implementations is
evidence that a specification is implemented, not that it is right. Only the
reference program could say that.

## How these are kept from coming back

* Every G\\*Power reading is a test: `tests/test_gpower_observed.py` re-runs the
  engine on all 435 recorded inputs on every CI build.
* The pre-registered predictions are never regenerated
  (`tools/probe_plan.py` refuses), so H-1 and H-2 stay visible in
  [`probes/REA-RESULTS.md`](probes/REA-RESULTS.md).
* The agent may not state a number that did not come from a tool
  (`agent/agent.py`, rule 1; `tools/compliance_check.py` C-3 forbids arithmetic
  in the agent file). H-8 is the reason that rule exists for the human-facing
  documents too: numbers are pasted from output, never typed.
