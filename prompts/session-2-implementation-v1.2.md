# Oturum 2 — yazım (clean room), round 2, SPEC v1.2

Launched as a fresh agent with no access to Session 1's context. Working
directory: a new folder outside the repository containing only `SPEC.md`
(v1.2, SHA-256 `263775846fa176243e77f6bfdbca06960efebbad2f1e3442dcf24bd5e60e789e`),
`INTERFACE.md`, `selfcheck.py` and its own earlier package. Prompt, verbatim
(only the absolute path of the working directory is shortened):

```text
You are Session B of a two-session clean-room implementation. You implement a statistical engine from a specification, and only from it.

Your working directory is exactly:
  <scratchpad>/cleanroom-b2

It contains: SPEC.md (version v1.2, the specification), INTERFACE.md (the required public API, naming only), selfcheck.py, and src/gpower_cleanroom/ — a Python package that an earlier Session B wrote from SPEC.md v1.1.

HARD BOUNDARY — read this twice:
- Read ONLY files inside that directory. Do not open, list, search or reason about any file outside it (in particular nothing under /Users/, no other repository, no "gpower_rea" package, no docs/EVIDENCE, no probes/ directory, no test suites you might find elsewhere). SPEC.md links to such paths; do NOT follow those links.
- Do not use the web, do not use any knowledge of how the program "G*Power" behaves beyond what SPEC.md states. Do not install packages. Standard library only in the package (math, etc.). You may run python3 to test your own code.
- SPEC.md contains a handful of worked numerical examples taken from the real program. Use them as sanity checks of your reading of the rules, not as fitting targets: never special-case an input to hit a number.
- If SPEC.md is incomplete, ambiguous or self-contradictory on a point, do NOT fill the gap from outside knowledge — record it (see deliverable 3) and choose the most literal reading.

TASK: bring src/gpower_cleanroom/ into conformance with SPEC.md v1.2 and INTERFACE.md. The specification changed materially since v1.1. Read the "Status" table at the top of SPEC.md and every finding marked "REFUTED → CORRECTED", plus F-14 and F-15 (new), §3, §4 (note item 7, new) and §5. In particular you will need to handle at least: the new default allocation rule of F-09 ("even-total", which must become the default of required_sample_size's allocation_rule parameter, while "n1-grid" and "total-grid" stay selectable), the observed sign rule of F-08 (including the criterion exception and the point-biserial domain), the corrected clause of F-06, the input domain of F-15 (raise ValueError exactly where F-15 says the original refuses; accept everything it accepts), the a-priori search limit of §3, the large-df numerics of §4 item 7, and the warnings of F-14 (your result dict may carry a "warnings" list). Keep the public functions and return keys exactly as INTERFACE.md specifies. Do not rewrite modules that are already correct; change what v1.2 requires.

DELIVERABLES (all inside the working directory):
1. The updated package src/gpower_cleanroom/.
2. selfcheck.py extended with self-checks for every v1.2 change (keep the old checks that are still valid; delete or fix ones v1.2 contradicts). It must run with `python3 selfcheck.py` from the working directory and exit 0.
3. SPEC-GAPS-v1.2.md: every point where SPEC.md v1.2 did not determine your implementation, or contradicted itself, numbered G2-01, G2-02, …, each with: the SPEC section, what was undetermined, what you chose, and an input where a different reasonable choice would give a different output. If you found no gaps, say so explicitly — but look hard; the previous session found twelve in v1.0.
4. CHANGES-v1.2.md: a short list of what you changed and which SPEC finding each change implements.

When done, reply with: the selfcheck result line, the list of gap ids with one-line titles, and the list of files you changed. Do not paste code in the reply.
```
