# CLI-CONTRACT.md — the `gpower` command line contract

Everything in this document is locked by `tests/test_cli.py`. If a statement
here is not true of the installed binary, that is a bug.

> **If the course hands out its own CLI contract**, see
> [§8 Adapting to a different contract](#8-adapting-to-a-different-contract).
> The flag surface is a thin layer over `gpower_rea.engine.solve`; retargeting
> it touches one file.

---

## 1. Synopsis

```
gpower [--version]
gpower solve   -t TEST [-s MODE] [parameters] [-f FORMAT]
gpower list    [-f FORMAT]
gpower info    TEST [-f FORMAT]
gpower batch   -i FILE [-o FILE] [--format csv|jsonl|json] [options]
gpower curve   -t TEST -a ALPHA -e ES --n-from N --n-to N [--n-step K]
gpower effect-size -c CALCULATOR --param NAME=VALUE ...
gpower selftest [--vectors FILE] [--min-match FRACTION] [-v]
gpower version
```

`python -m gpower_rea …` is an exact alias for `gpower …`.

### S-2 — implicit `solve`

If the first argument starts with `-` (and is not `-h/--help/-V/--version`),
the `solve` subcommand is inserted automatically. These are identical:

```console
$ gpower solve --test indep --alpha 0.05 --power 0.95 --effect-size 0.5
$ gpower       --test indep --alpha 0.05 --power 0.95 --effect-size 0.5
```

---

## 2. `solve` — the five analysis types

| flag | alias | type | meaning |
|---|---|---|---|
| `-t`, `--test` | | string | test key or alias (see `gpower list`) |
| `-s`, `--solve` | `--solve-for` | enum | `n` (default), `power`, `alpha`, `effect-size`, `compromise`. The G\*Power labels `a priori`, `post hoc`, `criterion`, `sensitivity`, `compromise` are accepted too. |
| `-a`, `--alpha` | | float | α error probability, in `(0,1)` |
| `-p`, `--power` | | float | target power, in `(0,1)` |
| `-e`, `--effect-size` | `--es` | float | `d` / `dz` / `r` / `f²` / `δ`, per test |
| `--tails` | | `1`\|`2` | default `2` |
| `-n`, `--n` | | int | total sample size |
| `--n1`, `--n2` | | int | per-group sizes (two-group test) |
| `--ratio` | `--allocation-ratio` | float | `N₂/N₁`, default `1` |
| `--allocation-rule` | | enum | `n1-grid` (default) \| `total-grid` — see [E-009](EVIDENCE/E-009-allocation-rounding.md) |
| `--q` | `--beta-alpha-ratio` | float | `β/α` for `--solve compromise` |
| `--predictors` | | int | regression: number of predictors |
| `--df` | | float | generic t test: degrees of freedom |
| `--param NAME=VALUE` | | repeatable | any extra test parameter |
| `-f`, `--format` | | enum | `text` (default), `json`, `csv`, `apa` |
| `--json` | | | shorthand for `-f json` |
| `--digits` | | int | decimals in `text` output, default `7` |

### Required parameters per mode

| `--solve` | needs | plus a design |
|---|---|---|
| `n` | `--alpha --power --effect-size` | `--ratio` for two-group |
| `power` | `--alpha --effect-size` | `--n` or `--n1 --n2` |
| `alpha` | `--power --effect-size` | `--n` or `--n1 --n2` |
| `effect-size` | `--alpha --power` | `--n` or `--n1 --n2` |
| `compromise` | `--effect-size --q` | `--n` or `--n1 --n2` |

Anything missing is a **usage** or **validation** error (§5), never a silent
default. The one exception is `--tails`, which defaults to `2`.

---

## 3. S-3 — the JSON result schema

`--format json` prints exactly one object, schema id
`gpower-rea/result/1`:

```json
{
  "schema": "gpower-rea/result/1",
  "test": "ttest-indep-means",
  "test_title": "Means: Difference between two independent means (two groups)",
  "family": "t tests",
  "solve_for": "n",
  "tails": 2,
  "alpha": 0.05,
  "power": 0.950128703388722,
  "df": 208.0,
  "noncentrality": 3.6228442074512673,
  "critical_t": 1.9714346585202587,
  "effect_size": { "name": "d", "value": 0.5 },
  "sample_size": {
    "n1": 105, "n2": 105, "total": 210,
    "allocation_ratio": 1.0, "actual_ratio": 1.0
  },
  "target": { "power": 0.95 },
  "engine": {
    "name": "gpower-rea", "version": "1.0.0",
    "spec": "SPEC.md v1.0", "allocation_rule": "n1-grid"
  },
  "warnings": []
}
```

Guarantees:

* **`power` is the achieved power; `target.power` is what was requested.**
  They are different fields on purpose — see
  [F-06](../SPEC.md#f-06--minimality-and-actual-power-is-recomputed).
* `sample_size` carries `n1`/`n2`/`total` for the two-group test and
  `n`/`total` otherwise. `total` is always present.
* `effect_size.parameters` appears when the test takes extras
  (`{"predictors": 5}`, `{"df": 30}`).
* `target.beta` and `target.beta_alpha_ratio` appear for `compromise`.
* `warnings` is always an array, possibly empty. Non-empty means a documented
  interpretation was applied (e.g. [F-08](../SPEC.md#f-08--a-negative-effect-size-is-a-direction-not-an-error)).
* No `NaN` or `Infinity` is ever emitted — the writer uses
  `allow_nan=False`.
* Fields are added only in a new schema id; `gpower-rea/result/1` is stable.

Other formats: `csv` is one header row plus one data row with the flattened
columns of §4; `apa` is a single sentence; `text` is a
protocol block laid out like the GUI's Output Parameters panel, followed by the
APA sentence.

---

## 4. S-4 — `batch`

Runs a file of cases. Designed for exactly the hidden-vector scenario:

```console
$ gpower batch -i hidden_vectors.csv -o results.csv \
      --expect expected_N --min-match 0.90
gpower: batch summary -- rows=250 compared=250 exact_N_matches=250 rate=1.0000 errors=0
```

### Input

* **CSV** with a header row (delimiter auto-detected: `,` `;` tab `|`),
* **JSON** array of objects, or
* **JSON Lines**;
* `-i -` reads standard input.

### Column recognition

Column names are normalised (lower-cased, non-alphanumerics → `_`) and matched
against a table of spellings, then against a longest-prefix fallback. All of
the following resolve, including the labels G\*Power itself prints in its
protocol:

| canonical | accepted spellings (excerpt) |
|---|---|
| `test` | `test`, `test_id`, `statistical_test`, `procedure` |
| `solve` | `solve`, `solve_for`, `analysis`, `type`, `Type of power analysis` |
| `alpha` | `alpha`, `α err prob`, `alpha err prob`, `sig_level` |
| `power` | `power`, `Power (1-β err prob)`, `target_power` |
| `effect_size` | `effect_size`, `es`, `d`, `dz`, `r`, `f2`, `Effect size d` |
| `tails` | `tails`, `Tail(s)`, `sides` |
| `n` / `n1` / `n2` | `n`, `Total sample size`, `Sample size group 1`, … |
| `ratio` | `ratio`, `Allocation ratio N2/N1` |
| `predictors` | `predictors`, `Number of predictors` |
| `df` | `df`, `degrees_of_freedom` |

Greek letters in headers are transliterated before matching (`α` → `alpha`,
`β` → `beta`, `²` → `2`), because `str.isalnum()` is true for them and they
would otherwise survive normalisation as themselves and match nothing.

Unrecognised columns are **passed through untouched** to the output.

### Value recognition

| input | read as |
|---|---|
| `0.05` | `0.05` |
| `0,05` | `0.05` — decimal comma, for exports from comma-decimal locales |
| `1,200` in an **integer** field (`n`, `n1`, `n2`, `tails`, `predictors`) | `1200` — a sample size cannot be fractional, so the comma must group thousands |
| `1,234.5` | `1234.5` — a dot is present, so commas group thousands |
| `A priori`, `a priori: compute required sample size` | `solve = n` |
| `Post hoc`, `Criterion`, `Sensitivity`, `Compromise` | `power`, `alpha`, `effect-size`, `compromise` |
| empty, `NA`, `N/A`, `NaN`, `null`, `none`, `-` | absent |

Missing fields fall back to `--test`, `--solve`, `--alpha`, `--tails`;
`tails` finally defaults to `2`.

The column named by `--expect` is **excluded from input matching**, so a
vector file whose expected-answer column is literally called `N` cannot have
that answer fed back in as the design.

### Output

Input columns are preserved verbatim; computed columns are appended with the
prefix from `--result-prefix` (default `gp_`, so collisions with the input are
impossible):

| column | meaning |
|---|---|
| `gp_n1`, `gp_n2`, `gp_N` | sample sizes (`gp_n2` is `0` for single-group tests) |
| `gp_power` | achieved power |
| `gp_alpha` | α used or solved |
| `gp_effect_size` | effect size used or solved |
| `gp_df`, `gp_ncp`, `gp_crit_t` | degrees of freedom, noncentrality, critical value |
| `gp_status` | `ok` \| `error` |
| `gp_message` | error text when `gp_status = error`, else empty |
| `gp_expected_N`, `gp_match` | only with `--expect`: the parsed expectation and `yes`/`no` |

`--result-prefix ""` emits the bare names (`N`, `power`, …) when the consumer
needs them unprefixed.

### Options

| flag | effect |
|---|---|
| `--expect COLUMN` | compare `gp_N` against that column; print a summary to **stderr** |
| `--min-match FRACTION` | exit `5` if the exact-match rate falls below it |
| `--continue-on-error` | record per-row errors instead of aborting the run |
| `--format csv\|jsonl\|json` | output encoding, default `csv` |
| `-o FILE` | output file; `-` (default) is stdout |

The summary line goes to stderr so that `-o -` stays machine-parsable.

---

## 5. S-5 — exit codes

| code | name | when |
|---|---|---|
| `0` | OK | success |
| `1` | internal | unexpected failure / interrupt |
| `2` | usage | unknown flag, missing `--test`, bad `--param` syntax, missing input file |
| `3` | validation | input outside a documented domain: unknown test, `α ∉ (0,1)`, `tails ∉ {1,2}`, `df ≤ 0`, `|r| ≥ 1`, unknown extra parameter |
| `4` | no solution | the requested quantity is unattainable inside the search domain |
| `5` | conformance | `batch --min-match` or `selftest --min-match` not met |

Errors go to stderr, prefixed `gpower: `. Nothing but the requested output is
ever written to stdout — `gpower … --json | jq` is always safe, and
`BrokenPipeError` exits `0` so `| head` does not produce a traceback.

---

## 6. `selftest`

```console
$ gpower selftest
selftest: 401/401 exact N matches (rate 1.0000), 0 finding(s)
```

Runs the 401 bundled reference vectors through the engine and compares
`expected_N` exactly and `expected_power` to `5e-7`
([F-12](../SPEC.md#f-12--boundary-behaviour-and-reported-precision)).
`--vectors FILE` points it at an external set; `-v` lists every passing row.
Exit `5` on any disagreement.

---

## 7. Worked examples

```console
# how many participants? (the canonical G*Power example)
$ gpower solve -t indep -s n -a 0.05 -p 0.95 -e 0.5 --tails 2

# ... unbalanced, twice as many controls
$ gpower solve -t indep -s n -a 0.05 -p 0.95 -e 0.5 --ratio 2

# what power do I have with what I already collected?
$ gpower solve -t indep -s power -a 0.05 -e 0.42 --n1 31 --n2 47 --json

# what is the smallest effect I could have detected?
$ gpower solve -t paired -s effect-size -a 0.05 -p 0.80 -n 24 -f apa

# balance the two error rates instead of fixing alpha
$ gpower solve -t indep -s compromise -e 0.5 --n1 40 --n2 40 --q 1

# one predictor inside a six-predictor model
$ gpower solve -t regression-coef -a 0.05 -p 0.9 -e 0.15 --predictors 6

# raw descriptives -> effect size -> sample size
$ gpower effect-size -c d-two-independent-means \
      --param mean1=10.4 --param mean2=8.9 --param sd1=3.1 --param sd2=2.8
$ gpower solve -t indep -a 0.05 -p 0.9 -e 0.5076

# sample size vs power, as a table
$ gpower curve -t indep -a 0.05 -e 0.5 --n-from 20 --n-to 200 --n-step 20

# bulk conformance against someone else's vectors
$ gpower batch -i vectors.csv --expect N --min-match 0.90
```

---

## 8. Adapting to a different contract

The CLI is ~500 lines of argument plumbing over one function. If the course
specifies different flag names, a different JSON schema or a different exit-code
map, retargeting is mechanical and touches **only**
[`src/gpower_rea/cli.py`](../src/gpower_rea/cli.py):

| change | where |
|---|---|
| flag names / shorthands | `_add_solve_arguments` |
| subcommand names | `build_parser`, `_COMMANDS` |
| JSON field names | `_flatten_result` (flat/CSV) and `engine._build_result` (nested) |
| exit codes | the `EXIT_*` constants and the `except` ladder in `main` |
| batch column spellings | `_COLUMN_ALIASES` |
| result column names/prefix | `_RESULT_COLUMNS`, `--result-prefix` |

The engine, the MCP server and the agent are unaffected, because none of them
go through the CLI (see [ARCHITECTURE.md](ARCHITECTURE.md)).
