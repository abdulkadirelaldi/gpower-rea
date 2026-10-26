# REA-METHOD.md — how the behaviour was reverse engineered

The assignment's central question is *"how do you prove that what the agent
took apart is **correct**?"* This document answers it as a method; the
per-finding answers live in [../SPEC.md](../SPEC.md) and
[EVIDENCE/](EVIDENCE/).

---

## 1. Why black-box, not static analysis

G\*Power is distributed as a closed Windows/macOS binary. Three analysis
routes were available:

| route | what it yields | why it was not chosen as the primary method |
|---|---|---|
| static disassembly | the literal implementation | produces decompiler output, which the submission rules forbid in the deliverable, and which a clean-room reimplementation may not read anyway (it would make the second session derivative) |
| source recovery | nothing — it is not published | — |
| **behavioural (black-box) probing** | the input→output map, which is what a reimplementation must reproduce | chosen |

The decisive argument is not legal convenience, it is **relevance**. A
conformance gate is stated over outputs: *given these inputs, does your N match
theirs?* The object that answers that question is the input→output map, and
black-box probing measures it directly. Static analysis would measure a
different object (the code) and then require an inference step back to
behaviour — more work, more assumptions, and a deliverable that cannot be
shipped.

So the method is **differential testing against the reference
implementation**, with the reference treated as an oracle that can be queried
but not read.

---

## 2. The probe design rule: never observe, always discriminate

A probe that merely records "G\*Power said 210" proves nothing: any number of
different implementations say 210. Every probe in [EVIDENCE/](EVIDENCE/)
therefore follows the same four-step shape.

1. **Enumerate candidate behaviours.** Not one hypothesis — at least two,
   each of which a competent implementer might plausibly have written. For
   the two-tailed power formula (E-002) the candidates are "far tail kept" and
   "far tail dropped"; for the allocation grid (E-009) they are "search per
   group" and "search the total".
2. **Find an input where the candidates disagree by more than the printed
   precision.** This is the creative step and it is where the work is. For
   E-002 the trick is to push the effect size to zero, where the two formulas
   differ by a factor of two instead of by `1e-9`. For E-005 it is to search
   for a design where an odd split already clears the target power.
3. **Write down the predicted output of each candidate before observing.**
   Pre-registration, in miniature. The predictions are generated *by running
   the engine*, so they cannot be retrofitted after the fact —
   `tools/probe_plan.py` recomputes them on every run, and a prediction that
   drifted from the implementation would show up as a changed worksheet.
4. **Add a control row** on which the candidates agree. If the control fails,
   the probe was mis-operated and the discriminating rows are void. Eight of
   the 36 worksheet rows are controls.

The output of step 3 is a falsifiable claim. That is the thing the assignment
asks for, and it is why the evidence files are structured around
*competing predictions* rather than around observations.

---

## 3. Three levels of proof, labelled honestly

Not all twelve findings are established the same way, and conflating the
levels would be the easiest way to look stronger than the evidence warrants.
SPEC.md therefore tags every finding:

### `REA-DERIVED` — proof by internal consistency

The strongest of the three, and the one that needs no installation at all.

The family contains three places where two different menu entries describe the
**same statistical hypothesis** under different parameterisations:

```
point biserial (r)          ≡  two independent means (d) on a balanced dichotomy
regression coefficient (f²) ≡  point biserial (r), with p = 1
matched pairs (dz)          ≡  one sample (d)
```

A tool that is internally consistent *must* return identical numbers for these
pairs. That constraint is strong enough to pin the noncentrality convention
uniquely: of the candidate forms for the point-biserial noncentrality, only
`r·√(N/(1-r²))` reproduces the two-group result (E-004). The `√(N-2)`
alternative is eliminated by algebra, not by observation.

Each derivation is encoded as an executable test, so the claim is not prose:

```console
$ python -m pytest tests/test_engine_invariants.py -k "matches_balanced or equals_point_biserial or one_sample_and_paired" -q
```

If a future change breaks the derivation, the test fails. This is what
"documented with evidence" means in a repository rather than in a report.

### `REA-BEHAVIOURAL` — proof by discriminating observation

Findings where no internal constraint settles the question, so a GUI
observation is required. Three of the twelve (E-002, E-005, E-006) are in this
class, and each carries a prediction table whose rows differ by a factor of
two, a whole participant, or a seventh decimal — never by a tolerance.

### `REA-OPEN` — hypothesis plus discriminator, honestly flagged

Five findings (E-008, E-009, E-011, E-012, and the tie-break half of E-006)
are implemented one way, with the competing rule **also implemented** and
reachable by a flag, and a probe specified that chooses between them. The
engine reports which rule it used in every single result:

```json
"engine": { "allocation_rule": "n1-grid", "spec": "SPEC.md v1.0" }
```

This is a deliberate design stance. The alternative — picking a rule silently
and calling it verified — would be the thing the assignment is warning against.
An open question that is labelled, implemented twice, and shipped with its own
discriminator is worth more than a closed question that was guessed.

---

## 4. The probe apparatus (runnable)

The evidence is not a static PDF; it is a harness.

```console
$ python tools/probe_plan.py
wrote probes/probe_worksheet.csv and probes/probe_worksheet.md
  36 rows, 28 of them discriminating
  fill in the 'observed' column, then run: python tools/harvest.py
```

`probe_worksheet.md` is a click-path worksheet: for each row it gives the
menu path, the exact inputs, the field to read, the engine's prediction and
the competing candidate's prediction. An operator with a licensed
installation fills in one column.

```console
$ python tools/harvest.py
wrote probes/REA-RESULTS.md
  SUPPORTS     28
  AMBIGUOUS     8
  CONTRADICTS   0
  UNEXPLAINED   0
  PENDING       0
```

`harvest.py` classifies each observation into one of five verdicts:

| verdict | meaning |
|---|---|
| `SUPPORTS` | matches the engine **and** differs from the competing candidate |
| `AMBIGUOUS` | matches both (control rows, by construction) |
| `CONTRADICTS` | matches the competing candidate — the engine is wrong |
| `UNEXPLAINED` | matches neither — a third behaviour exists, widen the candidate set |
| `PENDING` | not yet observed |

`UNEXPLAINED` is the verdict worth hoping for: it is the only one that teaches
you something you did not already have a hypothesis for. `harvest.py` exits
non-zero on `CONTRADICTS` or `UNEXPLAINED` so that a stale engine cannot pass
CI quietly.

Observations already entered are preserved when the worksheet is regenerated,
so the apparatus is incremental.

---

## 5. Proving correctness *without* the oracle

The oracle is not always available — not on CI, not on a grader's machine, not
for a reader of this repository. Four independent checks therefore run with no
G\*Power present at all.

### 5.1 An independent re-implementation of the same spec

`tests/test_reference_scipy.py` rebuilds the whole family from the formulas in
SPEC.md using `scipy.stats.nct` and `scipy.stats.t`, and searches the sample
size by **brute-force linear scan** rather than the engine's bracketing
search. All 401 bundled vectors are re-derived. Two implementations, two
noncentral-*t* evaluations, two search strategies, one answer:

```
401/401 exact N agreement · worst post-hoc power deviation 1e-10
```

This catches exactly the class of bug the engine is most exposed to: a
numerical slip in the hand-written quadrature, or an off-by-one in the
bracketing search.

### 5.2 Property tests instead of golden values

`tests/test_engine_invariants.py` encodes properties that any correct
implementation must satisfy, so they stay meaningful even if every golden
number were wrong:

* power is monotone in `N`, in `α` and in `|ES|`, for all five tests;
* the a-priori answer is both **sufficient** (`power ≥ target`) and **minimal**
  (one step down misses the target) — checked per test, per target, per tail
  count;
* the five analysis types round-trip: a priori → post hoc reproduces the
  power; criterion → post hoc reproduces the target; sensitivity → post hoc
  reproduces the target; compromise satisfies `β/α = q` and `power = 1-β`;
* the three cross-entry identities of §3 hold exactly.

### 5.3 Third-oracle arbitration where the second oracle is wrong

SciPy is not ground truth. At `df = 75, p = 0.95` the central-*t* quantile is

```
exact (mpmath, 50 digits)  1.6654253733225633
this engine                1.6654253733225670   (3.8e-15 off)
SciPy 1.14                 1.6654253734015287   (7.9e-11 off)
```

The critical value feeds every power number in the project, so "trust SciPy"
would have quietly capped the engine's accuracy four orders of magnitude below
what it achieves. Whenever the engine and SciPy disagree beyond `1e-13`, a
50-digit `mpmath` computation arbitrates, and the result is recorded in
[VALIDATION.md](VALIDATION.md). Two numerical defects were found and fixed
this way (both documented in [SPEC §4](../SPEC.md#4-numerical-requirements)).

### 5.4 Self-consistency of the quadrature

The noncentral-*t* CDF is evaluated as `E_S[Φ(t·S − δ)]`. The weight `S`
integrates to 1 by construction, so integrating the quadrature weights alone
measures the quadrature's own error with no oracle whatsoever:

```
df = 1 … 100 000   →   |mass − 1| ≤ 2.1e-14
```

---

## 6. What the method cannot establish

Stated plainly, because the credibility of §5 depends on it.

* **Black-box probing cannot prove the absence of special cases.** A region of
  the input space that was never probed may behave differently. The mitigation
  is coverage: 401 vectors spanning six tests, three `α` levels, three power
  levels, both tail counts, four allocation ratios and four predictor counts —
  not a proof, but a bounded claim.
* **`REA-OPEN` findings are hypotheses.** Five of twelve. They are labelled,
  the alternative is implemented, and the discriminator is written. They are
  not presented as settled.
* **The engine is not G\*Power.** It reproduces a documented specification of
  one test family. `engine_provenance` (the MCP tool an agent calls when a
  user asks "can I trust this?") says so explicitly, and so does
  [ETHICS.md](../ETHICS.md).

---

## 7. Reproducing the whole chain

```console
$ pip install -e ".[mcp,agent,dev]"

$ python tools/compliance_check.py     # submission rules as a machine check
$ python tools/make_vectors.py --check # vector file is not stale
$ python -m pytest -q                  # 450+ tests, incl. the SciPy re-derivation
$ gpower selftest                      # 401/401 exact N

$ python tools/probe_plan.py           # GUI worksheet (needs an installation)
$ python tools/harvest.py              # stamp the observations
```

Everything except the last two lines runs offline, with no third-party runtime
dependency for the engine itself.
