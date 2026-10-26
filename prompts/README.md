# prompts/ — the first prompt of each session

| file | session | role | what it was allowed to see |
|---|---|---|---|
| [session-1-analysis.md](session-1-analysis.md) | **Oturum 1 — inceleme** (analysis) | ran G\*Power, wrote `SPEC.md`, the evidence and the ledger | the G\*Power GUI, the manual, everything in this repository |
| [session-2-implementation-v1.0.md](session-2-implementation-v1.0.md) | **Oturum 2 — yazım** (clean room), round 1 | wrote `cleanroom/src/gpower_cleanroom/` from SPEC v1.0 | `SPEC.md`, `INTERFACE.md` only |
| [session-2-implementation-v1.2.md](session-2-implementation-v1.2.md) | Oturum 2, round 2 | updated it from SPEC v1.2, reported 19 gaps | a fresh directory holding only `SPEC.md`, `INTERFACE.md`, `selfcheck.py` and its own package |
| [session-2-implementation-v1.3.md](session-2-implementation-v1.3.md) | Oturum 2, round 3 (same session) | applied SPEC v1.3, reported 4 gaps | the same directory |

The two sessions never shared context: Oturum 2 was a separate agent whose
working directory physically contained nothing but the files listed. The SPEC
it received is identified by SHA-256 in
[docs/CLEANROOM-PROTOCOL.md](../docs/CLEANROOM-PROTOCOL.md).
