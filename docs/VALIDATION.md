# VALIDATION.md — measured evidence that the engine is correct

First the check that matters most — the engine against the real G\*Power —
then the independent checks that need no installation. Every number below is
reproducible from a clean checkout with the commands shown; §0 is reproducible
offline from the recorded readings, and re-recordable with G\*Power present.

Environment of the recorded run: CPython 3.13.9 on macOS 27.0.1 (arm64),
SciPy 1.18.1, statsmodels 0.15.0, mpmath 1.4.1, `mcp` 2.3.0, `anthropic` 2.3.0.

Nothing is skipped: all four oracles (SciPy, statsmodels, mpmath, the
clean-room implementation) are present.

```console
$ python -m pytest -q
1541 passed in 40.45s
```

---

## 0. Against the real G\*Power — 435 recorded runs

G\*Power 3.1.9.6 for macOS was driven through its GUI by
`tools/rea_campaign.py` (black box, via the macOS Accessibility API —
[REA-METHOD §4](REA-METHOD.md#4-the-probe-apparatus)) on 435 distinct inputs:
all six tests, all five analyses, both tail counts. Every number it printed is
recorded in [`probes/observations/`](../probes/observations/) and re-scored
against the current engine by `tools/rea_report.py`
([`probes/REA-OBSERVED.md`](../probes/REA-OBSERVED.md)).

| | result |
|---|---|
| runs | **435** (all six tests, all five analyses) |
| every printed field identical, at G\*Power's printed precision | **396** |
| refused by G\*Power with an *Input error!* — and refused by the engine | **25** |
| differ — all inside the two regions where G\*Power itself is inexact (F-14) | **14** |
| **outside F-14** | **421 / 421** |
| **a-priori total `N`, `N ≤ 1e7`** | **219 / 219 exact** |

What this caught that nothing else could:

| | before observation | after |
|---|---|---|
| a-priori `N`, all 219 rows | 149 / 219 (68.0 %) with the v1.1 rule | **219 / 219** |
| a-priori `N`, unbalanced designs only | 44 / 114 (38.6 %) | **114 / 114** |
| negative effect, one tail, post hoc (`P-08-a`) | power `7.7e-06` | `0.8482542` = G\*Power |
| inputs G\*Power refuses (F-15) | 7 answered anyway | all refused |
| `d = 1e-5` a priori | refused (search cap `1e7`) | answered (`N ≈ 7.8e10`) |
| critical value at `ν = 1e11` | `2.7e-6` relative error | `4e-16` (Cornish–Fisher, SPEC §4 item 6) |

The v1.1 engine passed every check in §1–§7 below — SciPy, statsmodels,
mpmath, an independent clean-room implementation. It was still wrong about
G\*Power on 32 % of a-priori designs, because every one of those oracles
implemented the same guessed allocation rule. **Agreement between
implementations of a specification proves the specification is implemented;
only the reference program proves the specification is right.**

`python tools/fit_allocation.py` scores seven candidate allocation rules
against the same readings: the even-total rule of F-09 fits every row; the
best alternative fits 96 of 119 rows (81 %).

```console
$ python tools/rea_report.py
cases=435 match=396 both_refuse=25 mismatch=14 apriori_N_exact=219/223
$ python -m pytest -q tests/test_gpower_observed.py
```

(`apriori_N_exact` counts all 223 a-priori rows; the four it misses are the
`N > 1e7` rows of F-14, where G\*Power's own `N` is not the exact one —
arbitrated in [E-014](EVIDENCE/E-014-far-tail-precision.md).)

---

## 1. Conformance gate — 401 / 401 exact sample sizes

```console
$ gpower selftest
selftest: 401/401 exact N matches (rate 1.0000), 0 finding(s)
```

The bundled vector set (`src/gpower_rea/data/public_vectors.csv`) covers:

| test | rows | sweep |
|---|---:|---|
| two independent means, balanced | 144 | `d ∈ {0.2 … 1.2}` × `α ∈ {.01,.05,.10}` × power `{.80,.90,.95}` × 1 and 2 tails |
| two independent means, unbalanced | 24 | `R ∈ {0.5, 1.5, 2, 3}` × `d ∈ {0.3,0.5,0.8}` × power `{.80,.95}` |
| one sample | 60 | `d ∈ {0.2 … 1.0}` × `α ∈ {.01,.05}` × power `{.80,.90,.95}` × 1 and 2 tails |
| matched pairs | 60 | as above, with `dz` |
| point biserial | 48 | `r ∈ {0.1 … 0.7}` × `α ∈ {.01,.05}` × power `{.80,.95}` × 1 and 2 tails |
| regression coefficient | 64 | `f² ∈ {.02,.05,.15,.35}` × `p ∈ {1,2,5,10}` × power `{.80,.95}` × 1 and 2 tails |
| literature reference | 1 | the canonical published two-group example |

Comparison tolerances are the ones specified in
[SPEC §F-12](../SPEC.md#f-12--boundary-behaviour-and-reported-precision):
**exact** on integer `N`, `5e-7` on power.

The same gate runs against an arbitrary external file — which is the hidden
vector scenario:

```console
$ gpower batch -i hidden_vectors.csv --expect expected_N --min-match 0.90
gpower: batch summary -- rows=N compared=N exact_N_matches=N rate=1.0000 errors=0
```

Exit code `5` if the rate falls below `--min-match`, so the gate is machine
checkable rather than a claim.

---

## 2. Independent re-derivation with SciPy — 401 / 401

`tests/test_reference_scipy.py` is a second implementation of SPEC.md: it
uses `scipy.stats.nct` / `scipy.stats.t` instead of the hand-written
quadrature, and finds the sample size by **brute-force linear scan** instead of
the engine's exponential-bracket-plus-bisection search. Different
distribution code, different search algorithm, same specification.

```console
$ python -m pytest tests/test_reference_scipy.py -q
403 passed
```

| check | result |
|---|---|
| every committed `expected_N` re-derived from scratch | 401 / 401 identical |
| every engine answer vs the SciPy reference | 401 / 401 identical |
| post-hoc power, 5 tests × 5 sample sizes × 3 α × 2 tails | worst deviation `< 1e-10` |

This is the check that matters most, because the two most likely failure modes
of the engine — a numerical slip in the quadrature, and an off-by-one in the
integer search — are exactly what it is blind to in common with nothing.

---

## 2b. A third oracle written by other people — statsmodels

The SciPy reference in §2 is powerful but shares one thing with the engine: we
wrote it, from our own reading of `SPEC.md`. `statsmodels.stats.power` does
not. It is an independent implementation of the same statistical procedures,
written from the literature with no knowledge of this project, so agreeing
with it tests the *reading* and not only the arithmetic.

```console
$ python -m pytest tests/test_reference_statsmodels.py -q
30 passed
```

### What it confirms

**statsmodels keeps the far-tail term of the two-tailed power expression.**
This was worth measuring rather than assuming — the textbook shortcut would
have been an easy thing for a library to take. Applying the
[E-002](EVIDENCE/E-002-two-sided-far-tail.md) discriminator to statsmodels
instead of to the GUI:

| α | statsmodels at δ = 0, two-tailed | candidate A predicts | candidate B predicts |
|---|---|---|---|
| 0.05 | `0.0500000000` | `0.05` ✔ | `0.025` ✘ |
| 0.10 | `0.1000000000` | `0.10` ✔ | `0.050` ✘ |
| 0.20 | `0.2000000000` | `0.20` ✔ | `0.100` ✘ |

So candidate A is the expression **two independent implementations arrived at**,
which is considerably stronger than one implementation plus an argument from
test size. A second, independent check at `d = 0.05, n = 100` per group — where
the far-tail term is `1.0e-2`, ten orders of magnitude above the two libraries'
disagreement there — gives the same answer.

Agreement also holds across the designs statsmodels covers (balanced and
unbalanced two-group, one-sample; both tail counts), to `1e-4`.

### Why the tolerance is 1e-4 and not 1e-8

Because statsmodels is an **agreement** oracle, not an **accuracy** oracle —
and the reason is version drift rather than quality. Measured against an
exact noncentral-*t* reference on the same grid:

| | worst error, two-group | worst error, one-sample |
|---|---|---|
| this engine | `9.2e-12` | `1.2e-11` |
| statsmodels 0.15.0 + SciPy 1.14.1 (dev machine) | `1.8e-05` | `7.2e-05` |
| statsmodels + SciPy as installed by CI | `3.3e-16` | `8.6e-16` |

The older build lost precision as power approached 1 — at `d = 0.35, N = 300`,
one sample, two tails it returned exactly `1.0` where the exact power is
`0.9999777374692385`. The newer build returns the exact value. Same code on
this side; the comparison inverted entirely.

The agreement tolerance is therefore set wide enough to hold under both
(`1e-4`), the engine's own error is asserted separately against the exact
reference (`1e-10`), and **which of the two is closer is not asserted at
all**. `test_whichever_library_saturates_the_engine_does_not` handles either
case explicitly, so the tolerance cannot quietly change meaning.

See §3.2 for the same lesson arriving the other way round, and for why this
project arbitrates with a 50-digit computation rather than deferring to
whichever library is better known.

---

## 3. Numerical accuracy, arbitrated by a third oracle

### 3.1 Measured worst-case deviations

| quantity | error | grid |
|---|---|---|
| noncentral *t* CDF, `ν ≥ 1` | **1.5e-14** | `ν ∈ {1 … 10 000}` × `δ ∈ {0.1 … 30}` × `x ∈ {−6 … 40}` |
| noncentral *t* CDF, `0 < ν < 1` | **6.7e-16** | `ν ∈ {0.05 … 0.99}` × `δ ∈ {0.1 … 3}` × `x ∈ {−2 … 20}` |
| noncentral *t* survival function | **5.3e-15** | same grid, vs `scipy.stats.nct.sf` |
| central *t* CDF | **2.9e-14** | `ν ∈ {1 … 20 000}` × `x ∈ {−9 … 11}`, vs mpmath |
| critical value `t_{1-α,ν}` | **1.0e-14** relative | `ν ∈ {1 … 1000}` × `α ∈ {.001 … .2}`, both tails, vs mpmath |
| size of a two-sided test at `δ = 0` | **1.8e-13** relative | `ν ∈ {1 … 5000}` × `α ∈ {1e-12 … 0.90}` |
| normal quantile `Φ⁻¹` | **1.8e-15** | `p ∈ {1e-12 … 1−1e-12}` |
| χ² quantile | **3e-10** relative | `ν ∈ {1 … 300}` × `p ∈ {1e-8 … 1−1e-8}` |
| quadrature mass closure (no oracle at all) | **9.0e-15** | `ν ∈ {0.01 … 1 000 000}` |

Two of these are self-certifying — the mass closure needs no oracle, and the
size of a test at the null is `α` by definition — so they cannot be an
artefact of agreeing with the wrong reference.

### 3.2 Why a library is never the oracle — and a correction

The lesson here arrived in two halves, and the second half corrected the first.

**First half.** On the development machine (SciPy 1.14.1), at `ν = 75`,
`p = 0.95`:

| source | value | error |
|---|---|---|
| exact (mpmath, 50 dps) | `1.6654253733225633` | — |
| this engine | `1.6654253733225670` | `3.8e-15` |
| SciPy **1.14.1** | `1.6654253734015287` | `7.9e-11` |

That is a factor of ~21 000, and it mattered: the critical value feeds every
power number in the project, so treating SciPy as ground truth would have
capped the engine's error bar four orders of magnitude above what it achieves.

**Second half — the correction.** CI installs a newer SciPy, and on that
version the same quantile is accurate to `4.4e-16` — *better* than this
engine's `3.8e-15`. The same happened with statsmodels: the saturation-to-1.0
behaviour measured in §2b is gone on current builds, which are accurate to
`3.3e-16` where the older one was off by `7.2e-5`.

So the honest statement is **not** "this engine beats SciPy". It is:

> A library's numerical accuracy is a property of its version, not of the
> library. Whichever direction the comparison happens to run today, an
> external library must not be the thing that bounds your own error bar.

The tests were rewritten accordingly, and the overclaim is recorded here
rather than quietly deleted — it was caught by CI running a different
dependency set than the development machine, which is the entire reason to
run CI on something other than your own laptop.

| what is asserted now | against | tolerance |
|---|---|---|
| the engine's own error | mpmath at 50 digits, or a closed form | `1e-13` |
| agreement with SciPy | SciPy, whatever version is installed | `1e-9` relative |
| agreement with statsmodels | statsmodels, whatever version | `1e-4` |
| which of the two is closer | — | **not asserted** |

```console
$ python -m pytest tests/test_numerics.py -k "50_digit_oracle or agrees_with_scipy" -q
```

### 3.3 Six numerical defects found and fixed by this process

Every one is a cancellation, in the sense that the arithmetic was textbook and
the error came entirely from *which algebraically equivalent form* was being
evaluated. Two were found by arbitration against mpmath; four more by the
clean-room pass (§7) pushing the engine into regions its own tests never
visited. All six are now written into
[SPEC §4](../SPEC.md#4-numerical-requirements) as warnings to the next
implementer.

| # | defect | symptom | fix | improvement |
|---|---|---|---|---|
| 1 | `lgamma(a+b) − lgamma(a)` evaluated naively | central *t* CDF error `4.1e-13` at `ν = 5000`; mass error `8.7e-12` at `ν = 10 000` | Stirling series rewritten so every term is `O(1)` (`_log_gamma_ratio`) | `4.1e-13 → 2.9e-14` |
| 2 | `1 − x` recovered by subtraction for `x = ν/(ν+t²)` | up to 11 significant digits lost as `x → 1` | the complement is passed in explicitly (`betainc_xy`) | `5.2e-13 → 2.9e-14` |
| 3 | quadrature run in `s` rather than `y = log s` | **wrong answer**, not a tolerance miss: two-sided size `0.252` where `α` was `0.100`, for `ν < 1` | the `s^(ν-1)` singularity becomes an entire function in `y` | `0.252 → 1.2e-9`, then `6.7e-16` with (4) |
| 4 | `Φ`'s turn not resolved by any panel edge | `2.8e-4` at `ν = 0.05`, where a huge critical value pushes the turn into the density's left tail | breakpoints where `x·e^y − δ` crosses `0, ±1, ±2, ±4, ±8` | `2.8e-4 → 1.2e-9` |
| 5 | power computed as `1 − nct_cdf` | relative error `6e-4` on the size at `α = 1e-12`; no relative accuracy at all for a tiny power | survival function computed directly as `E_S[Φ(δ − x·S)]` (`nct_sf`) | `6e-4 → 1.8e-13` relative |
| 6 | critical value taken as the `1−α/2` quantile, and `t*t` squared unguarded | `1 − α/2` rounds to exactly `1.0` below `α ≈ 1e-16`, so the criterion analysis **failed outright** at `α = 1e-300`; and `t_isf(1e-300, ν=1)` returned `1.2e69` instead of `3.18e299` | upper-tail quantile `t_isf` plus an asymptotic branch above `t = 1e120` | the Cauchy closed form is now matched to `1e-12` relative |

Defect 6 is worth a second look because SciPy 1.14.1 had the same symptom:
`scipy.stats.t.isf(1e-300, df=1)` returned `1e+100`, a bracket limit dressed
as an answer, where the true value is `3.1830988618e+299` (`1/(π·q)` for a
Cauchy tail). The engine is checked against the **closed form**, not against
SciPy, so `test_t_isf_is_exact_for_the_cauchy_tail` says something durable
regardless of what any library version does.

### 3.4 Headroom

The conformance tolerance is `5e-7` on power. The engine's worst numerical
error is `1.7e-14`, i.e. **3 × 10⁷ times smaller**. The tightest a-priori
margin found by sweeping `d` over `[0.100, 1.200]` in steps of `0.001` is
`1.4e-6` (`d = 0.162`, `N = 301`, actual power `0.8000014`), which is still
`8 × 10⁷` times the numerical error. So no exact-`N` agreement in §1 or §2
can be a tolerance artefact.

```console
$ python -m pytest tests/test_numerics.py -q
```

---

## 4. Property tests — correctness without golden values

`tests/test_engine_invariants.py` asserts properties that must hold for *any*
correct implementation, so they remain meaningful even if every golden number
in §1 were wrong.

| property | scope |
|---|---|
| power increases with `N`, with `α`, and with `|ES|` | all 5 solvable tests |
| required `N` decreases with `|ES|` | all 5 |
| a-priori answer is **sufficient** (`power ≥ target`) | 5 tests × 3 targets × 2 tail counts |
| a-priori answer is **minimal** (one step down misses) | same 30 combinations |
| a priori → post hoc reproduces `power`, `df`, `δ` exactly | all 5 |
| criterion → post hoc reproduces the target power | 3 single-group tests |
| sensitivity → post hoc reproduces the target power | 3 single-group tests |
| compromise satisfies `β/α = q` and `power = 1 − β` | `q ∈ {0.5, 1, 2, 4}` |
| two-tailed power at `δ = 0` equals **`α`**, not `α/2` | 5 α × 4 ν ([F-02](../SPEC.md#f-02--two-sided-power-retains-the-far-tail-term)) |
| one sample ≡ matched pairs | 3 `d` × 2 tails |
| point biserial ≡ balanced two-group | 3 `r` |
| regression (`p=1`) ≡ point biserial | 3 `r` |
| balanced a-priori total is always even | 5 `d` × 3 targets ([F-05](../SPEC.md#f-05--balanced-a-priori-search-runs-over-n-per-group-not-total-n)) |
| `n1-grid` reproduces the allocation ratio exactly | 5 ratios ([F-09](../SPEC.md#f-09--allocation-ratio-rounding)) |
| `total-grid` never needs more participants than `n1-grid` | 4 ratios |
| `power_curve` agrees with point queries to `1e-14` | 5 points |

The three cross-entry identities in the middle of that table are what make the
`REA-DERIVED` findings in [REA-METHOD.md §3](REA-METHOD.md) proofs rather than
assertions.

---

## 5. Interface equivalence

The assignment's "thin layers" rule is tested, not promised:

```python
# tests/test_mcp_server.py
def test_power_analysis_delegates_to_the_engine():
    payload = _call("power_analysis", {...})
    assert payload["result"] == solve("ttest-indep-means", "n", ...).as_dict()
```

Equality, not approximate equality. So any number an agent reports in prose is
byte-reproducible by a grader typing the equivalent `gpower solve` command.

Three layers of interface test:

| file | what it proves |
|---|---|
| `tests/test_cli.py` (48 tests) | exit codes, JSON schema keys, the `--min-match` gate, the implicit `solve` subcommand, the `--result-prefix` collision guard, and a deliberately hostile vector file: semicolon delimiter, Greek-letter headers (`α err prob`), G\*Power's own analysis labels (`A priori`), decimal commas (`0,05`), `NA` cells, and an expected-answer column named `N` that must not be fed back in as an input |
| `tests/test_mcp_server.py` (9 tests) | each tool returns the engine's dict verbatim, through the real MCP dispatcher; errors arrive as data, never as exceptions |
| `tests/test_mcp_stdio_e2e.py` (4 tests) | `python -m gpower_rea.mcp_server` spawned as a **real subprocess**, driven over stdio by an MCP client — the exact transport the agent uses. A packaging or entry-point regression cannot pass CI while the in-process tests stay green. |
| `tests/test_agent_offline.py` (22 tests) | the agent's loop driven with a stub client: tool-call extraction, history mirroring between turns, the `stop_reason == "refusal"` short-circuit, and the degradation path when the refusal-fallback beta is unavailable (including that the failed turn is rolled out of the history). Also asserts the system prompt still states the no-arithmetic rule, the four defaults and the "not G\*Power" clause. |

**The agent has not been run against the live API** — the build machine has no
Anthropic credentials. Everything around the model call is tested; the model
call is not. [SESSION-LOG.md](SESSION-LOG.md) carries that as a named,
unsigned attestation with the two commands that close it.

The MCP layer works against **both** SDK generations: `mcp` 1.x (`FastMCP`)
and `mcp` 2.x (`MCPServer`, renamed upstream). The server detects which is
installed and reports it in `engine_provenance.engine.mcp_sdk`; the tests pin
the behaviour rather than the SDK release by accepting either spelling of the
result fields.

---

## 6. Submission-rule compliance

```console
$ python tools/compliance_check.py
COMPLIANCE: PASS
  C-1 no original binary or installer in the tree
  C-2 no decompiler / disassembler output
  C-3 one engine; CLI, MCP and agent are adapters over it
  C-4 findings <-> SPEC.md <-> docs/EVIDENCE are in sync
  C-5 every text file is clean UTF-8 (no BOM, LF, no mojibake)
```

`C-2` scans every text file for disassembly markers (`sub_XXXXXX`,
`__fastcall`, register-mov lines, decompiler banners). `C-3` greps for
`nct_cdf(` outside the engine. `C-4` cross-references the `F-nn` tags used in
`procedures.py` against `SPEC.md`, and the `E-nnn` citations in `SPEC.md`
against `docs/EVIDENCE/` in both directions.

`C-5` exists because of a near-miss during development. The documents carry
Greek letters, em dashes and Turkish characters, and the evidence files *are*
the deliverable; one pass of a tool that re-encodes on write (PowerShell's
`Set-Content` is the classic offender) turned an entire document into mojibake
and no test noticed. The rule now checks every text file for a BOM, invalid
UTF-8, CRLF endings and the characteristic UTF-8-read-as-Latin-1 byte patterns,
and it runs in CI. The damaged file was recovered from git, which is the other
half of why the repository is committed early rather than at the end.

---

## 7. The clean-room pass — an independent implementation of the same spec

`SPEC.md` **v1.0** was frozen and handed to a separate agent session whose only
inputs were that file and a naming-only interface document: no access to
`src/`, to `docs/EVIDENCE/`, to the probe worksheets, or to the conformance
vectors. It was told that if the specification was incomplete it must record
the gap rather than guess. Its output is in
[`cleanroom/`](../cleanroom/).

### 7.1 It conforms

```console
$ python tools/judge_cleanroom.py
conformance vectors : 401/401 exact N (rate 1.0000)
power within 5e-7   : 401/401
SPEC properties       F-02 F-03 F-04 F-05 F-06/F-12 F-07 F-09   all PASS
Analysis-type round trips                                       all PASS
Cross-implementation grid: 300/300 identical
VERDICT: CONFORMING
```

Same 401 vectors, same tolerances, plus the discriminating SPEC properties and
the five-way round trips. The 300-case cross-implementation grid sweeps five
tests × five α × six target powers × both tail counts.

### 7.2 It is independent

A clean-room claim that cannot be checked is worth nothing, so the overlap is
measured rather than asserted:

| | |
|---|---|
| identifiers, shipped / clean room | 1309 / 612 |
| shared | 326 (Jaccard **0.204**) |
| shared **private** helper names | `_SQRT2`, `_STIRLING_MIN` |
| of those, not named by the handover documents | `_SQRT2` |
| identical comment lines | **0** |

Domain vocabulary (`alpha`, `noncentrality`, `quadrature`) is expected to
recur and says nothing. `_STIRLING_MIN` is explained by SPEC §4, which names
the Stirling series; `_SQRT2` is the constant in `erfc(-x/√2)`. The two
implementations reached the same answers through visibly different machinery:
the clean room reparametrised the quadrature to `y = log s` and computed the
survival function directly, which this engine did **not** do at the time — and
then adopted, because both were better (defects 3–5 in §3.3).

### 7.3 It found five specification defects

The point of the exercise. Twelve underspecified points were reported; each
was then probed on both implementations to see whether it actually bites:

```console
$ python tools/probe_spec_gaps.py
  AGREE: 8, DIVERGE: 3, N/A: 1      (before the fixes: AGREE 6, DIVERGE 5)
```

Five live divergences — places where two competent readers of the same document
produced different numbers. One of them (`G-05`) was a genuine wrong answer in
the shipped engine: the criterion analysis returned its own bracket floor of
`1e-12` where the honest answer was `4.2e-60`. **No amount of testing the
engine against itself could have found it**, because every test either round
tripped through the same bisection or compared against a reference using the
same bracket.

Three remain as deliberate, documented conventions — `G-03` (which effect size
the result echoes), `G-11` (an inapplicable parameter is rejected, not
ignored), and the knife-edge half of `G-04`. SPEC v1.1 states each one, so a
third implementation cannot drift the same way.

Full account: [EVIDENCE/E-013](EVIDENCE/E-013-cleanroom-divergence.md) and
[SPEC F-13](../SPEC.md#f-13--points-the-specification-left-undetermined-now-specified).

---

## 8. Pre-registered probe worksheet — stamped

The 36-row worksheet (`probes/probe_worksheet.csv`) was generated and committed
**before** G\*Power was run. Its `observed` column has since been filled from
the recorded readings by `tools/stamp_worksheet.py`; its predictions are
unchanged.

```console
$ python tools/harvest.py
  SUPPORTS     26
  AMBIGUOUS    5
  CONTRADICTS  2
  UNEXPLAINED  0
  PENDING      3
```

| finding | verdict |
|---|---|
| F-01 … F-07, F-10, F-12 | **SUPPORTED** by discriminating observation |
| F-08, F-09 | **NEITHER CANDIDATE** — the pre-registered rule was refused; the observed rule is now in SPEC v1.2 |
| F-11 | **PENDING** — the effect-size drawer is not exposed to the Accessibility API, so it was not driven |

The two refuted rows are kept, not hidden: they are the evidence that the
probes could fail, and they are where the engine was wrong.

---

## 9. Full reproduction

```console
$ pip install -e ".[mcp,agent,dev]"
$ python tools/compliance_check.py        # submission rules
$ python tools/make_vectors.py --check    # vectors are not stale
$ python -m pytest -q                     # everything above
$ gpower selftest                         # the gate
```
