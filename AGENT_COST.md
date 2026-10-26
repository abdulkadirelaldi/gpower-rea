# AGENT_COST.md — which agents, what they cost, what we would do differently

## Agents used

| role | agent | model | where |
|---|---|---|---|
| Oturum 1 — analysis: drove G\*Power, wrote SPEC / evidence / ledger / tools | Claude Code (interactive) | Claude Opus 5.5 | the student's Mac |
| Oturum 2 — clean-room implementation, rounds 2 and 3 | a separate Claude Code sub-agent, fresh context, isolated directory | Claude Opus 5.5 | same machine, outside the repository |
| the product's AI agent (evaluation and the recorded live run) | Claude Code headless (`claude -p`) over the `gpower` MCP server only | Claude Opus 5.5 | same machine |
| `agent/agent.py` (Anthropic SDK tool runner) | — | `claude-opus-5-5` | not run live: no API key on the machine; 22 offline tests |

## Measured

| item | tokens | cost | time | iterations |
|---|---|---|---|---|
| Oturum 2, round 2 (SPEC v1.2 → 19 gaps) | **176 902** | — | 829 s | 35 tool calls |
| Oturum 2, round 3 (SPEC v1.3 → 4 gaps) | **211 400** (cumulative context) | — | 224 s | 10 tool calls |
| live transcript run (`agent/transcripts/`) | — | **$0.19** | — | 7 turns, 5 tool calls |
| 10-question evaluation ([agent/eval/REPORT.md](agent/eval/REPORT.md)) | **605 470 in / 9 832 out** | **$1.30** | 14.0 s / question | 1 run per question |
| G\*Power GUI campaign | no model tokens — a deterministic driver (`tools/gpower_ax.py`) | $0 | ≈ 3 h of GUI time for 443 runs | 6 case sets + reruns |

Most of the evaluation's input tokens are the agent harness's own cached
system prompt (≈ 60 k per question, served from the prompt cache); the
question, the tool schemas and the tool results are a small fraction. The
part the MCP design controls — one tool call returning one JSON object — is a
few hundred tokens per call. The GUI-path comparison is measured by
`tools/gui_token_eval.py` (needs Screen Recording permission; see README).

## Not metered

Oturum 1 ran as one long interactive session; the harness does not report
its token total. Order of magnitude: a few hundred tool calls over one
working day, with context repeatedly compacted. We do not state a number we
did not measure.

## What we would do differently

1. **Read the full course brief first.** The fixed CLI contract
   (`gpower-clone`, one-line JSON) arrived late; the first CLI was built to our
   own contract and had to be wrapped. Every hidden vector depends on it.
2. **Observe before specifying.** SPEC v1.0/v1.1 were written from the manual
   and from derivations, then implemented twice and checked against three
   libraries — and were still wrong on 32 % of a-priori designs (H-1). Twenty
   minutes of GUI readings would have found that on day one.
3. **Ask the reference, not the agent, whenever a gap is about the program.**
   Of the 23 gaps the clean-room session reported, 14 were settled in minutes
   by putting them to G\*Power; the earlier round had settled them by
   convention.
4. **Paste numbers, never type them** (H-8).
5. **Budget for the screenshot evidence early.** macOS applies the Screen
   Recording permission only after the terminal restarts, which ends the
   session; that step should come first, not last.
