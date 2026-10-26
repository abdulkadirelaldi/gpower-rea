# Oturum 2 — yazım (clean room), round 1, SPEC v1.0

Handover prompt, verbatim (also in docs/CLEANROOM-PROTOCOL.md §3):

```
You are implementing a statistical engine from a specification.

Read ONLY the file SPEC.md in this repository. Do not look for, open,
or reason about: the G*Power application, its manual, docs/EVIDENCE/*,
probes/*, or any file containing recorded G*Power output. If you believe
SPEC.md is incomplete or self-contradictory, STOP and report the gap --
do not fill it from your own knowledge of G*Power, and do not guess.

Implement, in Python 3.10+ with no third-party runtime dependencies:

  1. src/gpower_rea/numerics.py    - the special functions SPEC section 4
                                     requires, to the stated tolerances
  2. src/gpower_rea/procedures.py  - one object per statistical test,
                                     supplying only (df, noncentrality)
  3. src/gpower_rea/engine.py      - the single power formula of F-02 and
                                     the five analysis types of section 3
  4. src/gpower_rea/effectsize.py  - the calculators of F-11
  5. src/gpower_rea/report.py      - the output renderings

Every finding F-01..F-12 must be traceable to the code that implements it.
Where SPEC.md marks a finding REA-OPEN, implement BOTH candidates and make
the choice selectable and reported in the output -- never silently pick one.
```
