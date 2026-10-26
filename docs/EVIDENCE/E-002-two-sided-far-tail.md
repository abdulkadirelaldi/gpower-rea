# E-002 — The two-sided power formula keeps the wrong-side tail

| | |
|---|---|
| **Finding** | [F-02](../../SPEC.md#f-02--two-sided-power-retains-the-far-tail-term) |
| **Status** | `[REA] OBSERVED` — observed on G\*Power 3.1.9.6 (macOS) |
| **Method** | Differential probing at the null; discriminating-prediction design |
| **Target** | G\*Power 3.1.9.x, test family `t tests` |
| **Probe id** | `P-02` |

## Claim

For a two-tailed test, power is

```
1-β = 1 - T(t_{1-α/2, ν}; ν, δ)  +  T(-t_{1-α/2, ν}; ν, δ)
```

The trailing term — the probability of landing in the rejection region on the
side *away* from the true effect — is retained.

## Why this is not in the manual

The manual names the noncentral *t* distribution but prints no power formula
for the two-tailed case. Both candidate formulas are "a noncentral t
computation", and both are defensible in prose. They are numerically
indistinguishable on exactly the examples a manual would print (textbook effect
sizes, where the far tail is below `1e-9`), and they differ by a factor of two
in the regime nobody documents.

This is the clearest instance in the family of *behaviour that the
documentation cannot settle*.

## Discriminating probe `P-02`

The two candidates:

| candidate | value at `δ = 0`, two tails |
|---|---|
| **A** (far tail kept) | exactly `α` |
| **B** (far tail dropped) | exactly `α/2` |

A factor of two is not a tolerance question — any single observation settles
it. Use a large `α` so the gap is unmissable.

### Click path

`Test family = t tests` → `Statistical test = Generic t test` →
`Type of power analysis = Post hoc` → set **Noncentrality parameter δ = 0**,
**df = 30**, **α err prob = 0.20**, **Tail(s) = Two** → **Calculate**.

If the GUI refuses `δ = 0`, use `δ = 1e-6`; the predictions shift by less than
`1e-6`.

### Inputs and predictions

| row | δ | df | α | tails | prediction A | prediction B |
|---|---|---|---|---|---|---|
| `P-02-a` | 0 | 30 | 0.20 | 2 | `0.2000000` | `0.1000000` |
| `P-02-b` | 0 | 30 | 0.05 | 2 | `0.0500000` | `0.0250000` |
| `P-02-c` | 0 | 5 | 0.20 | 2 | `0.2000000` | `0.1000000` |
| `P-02-d` | 0 | 30 | 0.20 | 1 | `0.2000000` | `0.2000000` (no discrimination) |

Row `P-02-d` is a control: the one-tailed formula is the same under both
candidates, so a deviation there would indicate a probe setup error rather
than a formula difference.

### Observation

Recorded in `probes/REA-RESULTS.md` (rows `P-02-a` … `P-02-d`) once the
worksheet is filled in from the GUI.

## Independent corroboration: another implementation keeps the term too

The same discriminator can be applied to a *different* power-analysis library
rather than to the GUI. `statsmodels.stats.power` is written by other people,
from the statistical literature, with no knowledge of this project — so what it
does is independent evidence about which expression practitioners' tools
actually implement.

Measured (`tests/test_reference_statsmodels.py`):

| α | statsmodels at δ = 0, two tails | candidate A | candidate B |
|---|---|---|---|
| 0.05 | `0.0500000000` | `0.05` ✔ | `0.025` ✘ |
| 0.10 | `0.1000000000` | `0.10` ✔ | `0.050` ✘ |
| 0.20 | `0.2000000000` | `0.20` ✔ | `0.100` ✘ |

A second check away from the null, where the term is large enough that no
tolerance argument applies: at `d = 0.05` with `n₁ = n₂ = 100`, the far-tail
term is `1.04e-2`. The engine and statsmodels agree to `1e-9` there, and the
truncated formula differs from both by more than `1e-3`.

**This was worth measuring rather than assuming.** The initial expectation
when writing this file was that a widely used library would take the textbook
shortcut and that the gap would show up as evidence *against* statsmodels.
It did not: the small residual disagreement between the two libraries is
numerical, not a difference of formula. On the development machine
(statsmodels 0.15.0) that residual was statsmodels' error — up to `7.2e-5` as
power approaches 1, against `1.2e-11` for this engine. On the newer versions
CI installs it is the other way round. Which library is closer depends on its
version and is not asserted anywhere; see
[VALIDATION.md §2b and §3.2](../VALIDATION.md). What *is* asserted is that
both compute the same expression — which is the claim this file needs.

So candidate A is the expression **two independent implementations arrived at**.
That does not by itself settle what G\*Power does — only probe `P-02` does
that — but it does mean candidate B would be the odd one out.

## Secondary, model-internal argument

Candidate A is the only one under which the two-sided test has size exactly
`α`. A tool whose reported power at a null effect were `α/2` would be
reporting the size of a test it is not performing. This is why the engine
implements A, and why the behaviour is pinned by an executable test rather
than left as a comment:

```python
# tests/test_engine_invariants.py
def test_two_tailed_power_at_null_equals_alpha(alpha, df):
    got = solve("ttest-generic", "power", alpha=alpha,
                effect_size=1e-12, tails=2, extra={"df": df}).power
    assert got == pytest.approx(alpha, abs=1e-9)
    assert got != pytest.approx(alpha / 2, abs=1e-6)
```

Run against the engine:

```console
$ gpower solve --test generic --solve power --alpha 0.20 \
      --effect-size 1e-12 --param df=30 --tails 2 --json | findstr power
  "power": 0.20000000000000018,
```

## Where the difference actually bites

| situation | relative effect of dropping the term |
|---|---|
| `δ ≥ 6` (typical textbook a-priori results) | `< 1e-9` — invisible |
| sensitivity analysis at small `N` | up to a few per mille in the returned effect size |
| criterion analysis with `α` near 0.3 | several per cent in the returned `α` |
| compromise analysis | always, because `β` is the complement of this expression (F-10) |

So an implementation can pass a naive a-priori test suite with candidate B and
still be wrong where it matters. This repository's vector set deliberately
includes `α = 0.10` rows for that reason.

## [REA] Observation — G\*Power 3.1.9.6

Read off the GUI's *Output parameters* panel by `tools/rea_campaign.py`
(raw records in [`probes/observations/`](../../probes/observations/)). The
predictions were registered in `probes/probe_worksheet.csv` before any
observation was made, and are shown unchanged.

| probe | read | G\*Power printed | pre-registered engine prediction | competing prediction | verdict |
|---|---|---|---|---|---|
| `P-02-a` | Power | `0.2000000` | `0.2000000` | `0.1000000` | **SUPPORTS** |
| `P-02-b` | Power | `0.0500000` | `0.0500000` | `0.0250000` | **SUPPORTS** |
| `P-02-c` | Power | `0.2000000` | `0.2000000` | `0.1000000` | **SUPPORTS** |
| `P-02-d` | Power | `0.2000000` | `0.2000000` | `0.2000000` | **AMBIGUOUS** |

Every other field G\*Power printed for these rows also matches the current
engine — `tests/test_gpower_observed.py` checks each one.

## Verdict

**[REA] F-02 — observed.** Candidate A (far tail kept) is what G\*Power does: at `δ = 0` two-tailed power equals `α` exactly, not `α/2`. Candidate B is refuted by three independent rows; the one-tailed control row agrees with both, as pre-registered.

## Re-run

```console
$ python -m pytest tests/test_engine_invariants.py -k two_tailed_power_at_null -q
```
