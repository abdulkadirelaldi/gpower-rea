"""`gpower` -- the command line interface.

A thin adapter: it parses, validates, calls :func:`gpower_rea.engine.solve`
and formats.  Every number it prints comes from the engine (invariant I-3).

The contract -- flags, output schema, exit codes -- is specified in
docs/CLI-CONTRACT.md and locked down by tests/test_cli.py.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import effectsize as esmod
from . import engine as eng
from .procedures import PROCEDURES, ValidationError, resolve
from .report import apa_sentence, text_block

PROG = "gpower"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_NO_SOLUTION = 4
EXIT_CONFORMANCE = 5

VECTORS_DIR = Path(__file__).resolve().parent / "data"
PUBLIC_VECTORS = VECTORS_DIR / "public_vectors.csv"

# --------------------------------------------------------------------------
# batch-mode column aliases: every spelling we are willing to accept
# --------------------------------------------------------------------------
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "test": (
        "test", "test_id", "testkey", "statistical_test", "procedure",
        "analysis_test", "test_name",
    ),
    "solve": (
        "solve", "solve_for", "analysis", "analysis_type", "mode", "type",
        "target", "type_of_power_analysis", "power_analysis",
    ),
    "alpha": (
        "alpha", "alpha_err_prob", "alpha_error_probability", "sig_level",
        "significance", "a",
    ),
    "power": (
        "power", "target_power", "power_target", "one_minus_beta", "1_beta",
        "power_1_beta_err_prob", "1_beta_err_prob", "desired_power",
    ),
    "effect_size": (
        "effect_size", "effectsize", "es", "effect", "d", "dz", "r", "f2",
        "cohens_d", "effect_size_d", "effect_size_dz", "effect_size_r",
        "effect_size_f2",
    ),
    "tails": ("tails", "tail", "tail_s", "sides", "n_tails", "nr_tails"),
    "n": (
        "n", "total_n", "total_sample_size", "sample_size", "n_total",
    ),
    "n1": (
        "n1", "n_1", "group1_n", "sample_size_group_1", "n_group1",
        "sample_size_group1",
    ),
    "n2": (
        "n2", "n_2", "group2_n", "sample_size_group_2", "n_group2",
        "sample_size_group2",
    ),
    "ratio": (
        "ratio", "allocation_ratio", "alloc_ratio", "n2_n1", "allocation",
        "allocation_ratio_n2_n1",
    ),
    "allocation_rule": ("allocation_rule", "alloc_rule", "rule"),
    "q": ("q", "beta_alpha_ratio", "beta_over_alpha", "beta_alpha"),
    "predictors": (
        "predictors", "num_predictors", "n_predictors",
        "number_of_predictors", "number_of_predictors_in_the_model",
    ),
    "df": ("df", "degrees_of_freedom", "dof"),
}

_EXTRA_KEYS = ("predictors", "df")


# G*Power prints Greek letters in its protocol headers ("α err prob",
# "Power (1-β err prob)"), and `str.isalnum()` is True for them, so they
# survive normalisation as themselves and never match an ASCII alias.
# Transliterate them instead of dropping them.
_GREEK = {
    "α": "alpha", "Α": "alpha",
    "β": "beta", "Β": "beta",
    "γ": "gamma",
    "δ": "delta", "Δ": "delta",
    "ε": "epsilon",
    "η": "eta",
    "λ": "lambda",
    "μ": "mu", "µ": "mu",
    "ρ": "rho",
    "σ": "sigma", "Σ": "sigma",
    "φ": "phi", "ϕ": "phi",
    "χ": "chi",
    "ω": "omega",
    "²": "2",
}


def _norm_col(name: str) -> str:
    out = []
    for ch in str(name).strip().lower():
        if ch in _GREEK:
            out.append("_" + _GREEK[ch] + "_")
        else:
            out.append(ch if ch.isalnum() else "_")
    token = "".join(out)
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_")


_REVERSE_ALIASES: dict[str, str] = {}
for _canon, _spellings in _COLUMN_ALIASES.items():
    for _s in _spellings:
        _REVERSE_ALIASES.setdefault(_norm_col(_s), _canon)

# Prefix fallback, longest spelling first, so that a G*Power protocol header
# like "Power (1-beta err prob)" or "Allocation ratio N2/N1" still resolves.
# Single- and two-character spellings are excluded: matching "a_b_group" to
# `alpha` would be worse than not matching at all.
_PREFIX_ALIASES: list[tuple[str, str]] = sorted(
    (
        (_norm_col(s), canon)
        for canon, spellings in _COLUMN_ALIASES.items()
        for s in spellings
        if len(_norm_col(s)) > 2
    ),
    key=lambda pair: (-len(pair[0]), pair[0]),
)


def _match_column(name: str) -> str | None:
    token = _norm_col(name)
    canon = _REVERSE_ALIASES.get(token)
    if canon is not None:
        return canon
    for spelling, canon in _PREFIX_ALIASES:
        if token.startswith(spelling + "_"):
            return canon
    return None


class UsageError(Exception):
    pass


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------
def _add_solve_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("-t", "--test", help="statistical test key or alias")
    p.add_argument(
        "-s",
        "--solve",
        "--solve-for",
        dest="solve",
        default=None,
        help="n | power | alpha | effect-size | compromise (default: n)",
    )
    p.add_argument("-a", "--alpha", type=float, help="alpha error probability")
    p.add_argument(
        "-p",
        "--power",
        dest="power",
        type=float,
        help="target power (1 - beta)",
    )
    p.add_argument(
        "-e",
        "--effect-size",
        "--es",
        dest="effect_size",
        type=float,
        help="effect size (d, dz, r, f2 or delta depending on the test)",
    )
    p.add_argument(
        "--tails",
        type=_tails_arg,
        default=None,
        help="number of tails: 1 or 2, also One/Two (default: 2)",
    )
    p.add_argument("-n", "--n", dest="n", type=int, help="total sample size")
    p.add_argument("--n1", type=int, help="sample size of group 1")
    p.add_argument("--n2", type=int, help="sample size of group 2")
    p.add_argument(
        "--ratio",
        "--allocation-ratio",
        dest="ratio",
        type=float,
        default=None,
        help="allocation ratio N2/N1 (two-group tests, default 1)",
    )
    p.add_argument(
        "--allocation-rule",
        dest="allocation_rule",
        default=None,
        choices=tuple(eng.ALLOCATION_RULES),
        help=f"integer search rule (default: {eng.DEFAULT_ALLOCATION_RULE})",
    )
    p.add_argument(
        "--q",
        "--beta-alpha-ratio",
        dest="q",
        type=float,
        default=None,
        help="beta/alpha ratio for solve=compromise",
    )
    p.add_argument("--predictors", type=int, default=None, help="regression: number of predictors")
    p.add_argument("--df", type=float, default=None, help="generic t test: degrees of freedom")
    p.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="extra test parameter (repeatable)",
    )


def _add_format_arguments(p: argparse.ArgumentParser, default: str = "text") -> None:
    p.add_argument(
        "-f",
        "--format",
        dest="fmt",
        default=default,
        choices=("text", "json", "csv", "apa"),
        help=f"output format (default: {default})",
    )
    p.add_argument(
        "--json",
        dest="fmt",
        action="store_const",
        const="json",
        help="shorthand for --format json",
    )
    p.add_argument("--digits", type=int, default=7, help="decimals in text output")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Sample size and power for the G*Power t-test family. "
            "Clean-room engine; see SPEC.md for the specification it "
            "implements."
        ),
        epilog="Full contract: docs/CLI-CONTRACT.md",
    )
    ap.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="print engine version and exit",
    )
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    p_solve = sub.add_parser("solve", help="run one power analysis (default command)")
    _add_solve_arguments(p_solve)
    _add_format_arguments(p_solve)

    p_list = sub.add_parser("list", help="list the implemented tests")
    _add_format_arguments(p_list)

    p_info = sub.add_parser("info", help="describe one test and its parameters")
    p_info.add_argument("test")
    _add_format_arguments(p_info)

    p_batch = sub.add_parser("batch", help="run a CSV/JSONL file of cases")
    p_batch.add_argument("-i", "--input", required=True, help="input file, or - for stdin")
    p_batch.add_argument("-o", "--output", default="-", help="output file, or - for stdout")
    p_batch.add_argument(
        "--format",
        dest="fmt",
        default="csv",
        choices=("csv", "jsonl", "json"),
        help="output format (default: csv)",
    )
    p_batch.add_argument(
        "--result-prefix",
        default="gp_",
        help="prefix for computed columns (default: gp_, use '' for none)",
    )
    p_batch.add_argument("--test", help="default test for rows that omit it")
    p_batch.add_argument("--solve", default=None, help="default solve target for rows that omit it")
    p_batch.add_argument("--tails", type=_tails_arg, default=None)
    p_batch.add_argument("--alpha", type=float, default=None)
    p_batch.add_argument(
        "--expect",
        default=None,
        metavar="COLUMN",
        help="column holding the expected total N; enables a match report",
    )
    p_batch.add_argument(
        "--min-match",
        type=float,
        default=None,
        metavar="FRACTION",
        help="fail (exit 5) if the exact-match rate falls below this fraction",
    )
    p_batch.add_argument(
        "--continue-on-error",
        action="store_true",
        help="record per-row errors instead of aborting",
    )

    p_curve = sub.add_parser("curve", help="power as a function of sample size")
    p_curve.add_argument("-t", "--test", required=True)
    p_curve.add_argument("-a", "--alpha", type=float, required=True)
    p_curve.add_argument(
        "-e", "--effect-size", "--es", dest="effect_size", type=float, required=True
    )
    p_curve.add_argument("--tails", type=_tails_arg, default=2)
    p_curve.add_argument("--n-from", type=int, required=True)
    p_curve.add_argument("--n-to", type=int, required=True)
    p_curve.add_argument("--n-step", type=int, default=1)
    p_curve.add_argument("--ratio", dest="ratio", type=float, default=None)
    p_curve.add_argument(
        "--allocation-rule", dest="allocation_rule", default=None,
        choices=tuple(eng.ALLOCATION_RULES),
    )
    p_curve.add_argument("--predictors", type=int, default=None)
    p_curve.add_argument(
        "--format", dest="fmt", default="csv", choices=("csv", "json"),
    )

    p_es = sub.add_parser("effect-size", help="effect-size calculators (Determine =>)")
    p_es.add_argument(
        "-c",
        "--calculator",
        required=True,
        choices=tuple(esmod.CALCULATORS),
    )
    p_es.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="calculator input (repeatable)",
    )
    _add_format_arguments(p_es, default="text")

    p_self = sub.add_parser(
        "selftest", help="run the bundled reference vectors through the engine"
    )
    p_self.add_argument(
        "--vectors",
        default=None,
        help=f"vector CSV to use (default: bundled {PUBLIC_VECTORS.name})",
    )
    p_self.add_argument("--min-match", type=float, default=1.0)
    p_self.add_argument("-v", "--verbose", action="store_true")

    sub.add_parser("version", help="print engine version")
    return ap


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _parse_params(items: Sequence[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or ():
        if "=" not in item:
            raise UsageError(f"--param expects NAME=VALUE, got {item!r}")
        key, _, val = item.partition("=")
        out[_norm_col(key)] = val.strip()
    return out


def _extra_from_args(args: argparse.Namespace) -> dict:
    extra = _parse_params(getattr(args, "param", []) or [])
    for key in _EXTRA_KEYS:
        val = getattr(args, key, None)
        if val is not None:
            extra[key] = val
    return {k: v for k, v in extra.items() if v not in (None, "")}


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=False, allow_nan=False)


def _flatten_result(result: eng.Result) -> dict:
    r = result.as_dict()
    ss = r["sample_size"]
    flat = {
        "test": r["test"],
        "solve_for": r["solve_for"],
        "tails": r["tails"],
        "alpha": r["alpha"],
        "power": r["power"],
        "effect_size_name": r["effect_size"]["name"],
        "effect_size": r["effect_size"]["value"],
        "n1": ss.get("n1", ss.get("n")),
        "n2": ss.get("n2", 0),
        "N": ss.get("total"),
        "df": r["df"],
        "ncp": r["noncentrality"],
        "crit_t": r["critical_t"],
        "target_power": r["target"].get("power"),
    }
    return flat


def _write_csv(stream, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        return
    names = fieldnames or list(rows[0])
    w = csv.DictWriter(stream, fieldnames=names, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow(row)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_solve(args: argparse.Namespace) -> int:
    if not args.test:
        raise UsageError("--test is required (see `gpower list`)")
    result = eng.solve(
        args.test,
        args.solve or "n",
        alpha=args.alpha,
        power_target=args.power,
        effect_size=args.effect_size,
        tails=2 if args.tails is None else args.tails,
        n=args.n,
        n1=args.n1,
        n2=args.n2,
        allocation_ratio=args.ratio,
        allocation_rule=args.allocation_rule,
        beta_alpha_ratio=args.q,
        extra=_extra_from_args(args),
    )
    if args.fmt == "json":
        print(_dump_json(result.as_dict()))
    elif args.fmt == "csv":
        buf = io.StringIO()
        flat = _flatten_result(result)
        _write_csv(buf, [flat])
        sys.stdout.write(buf.getvalue())
    elif args.fmt == "apa":
        print(apa_sentence(result))
    else:
        print(text_block(result))
        print()
        print(apa_sentence(result))
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    items = [p.describe() for p in PROCEDURES.values()]
    if args.fmt == "json":
        print(_dump_json({"schema": "gpower-rea/tests/1", "tests": items}))
        return EXIT_OK
    if args.fmt == "csv":
        buf = io.StringIO()
        _write_csv(
            buf,
            [
                {
                    "key": i["key"],
                    "title": i["title"],
                    "design": i["design"],
                    "effect_size": i["effect_size"]["name"],
                }
                for i in items
            ],
        )
        sys.stdout.write(buf.getvalue())
        return EXIT_OK
    print("Test family: t tests")
    print()
    for i in items:
        print(f"  {i['key']}")
        print(f"      {i['title']}")
        print(
            f"      effect size: {i['effect_size']['name']}   "
            f"design: {i['design']}   "
            f"solve: {', '.join(i['supports_solve'])}"
        )
        if i["extra_parameters"]:
            names = ", ".join(
                f"{p['name']}"
                + ("*" if p["required"] else f" (default {p['default']})")
                for p in i["extra_parameters"]
            )
            print(f"      extra parameters: {names}")
        print()
    return EXIT_OK


def cmd_info(args: argparse.Namespace) -> int:
    proc = resolve(args.test)
    desc = proc.describe()
    if args.fmt in ("json", "csv"):
        print(_dump_json(desc))
        return EXIT_OK
    print(desc["title"])
    print("=" * len(desc["title"]))
    print(f"key            : {desc['key']}")
    print(f"aliases        : {', '.join(desc['aliases']) or '-'}")
    print(f"design         : {desc['design']}")
    print(
        f"effect size    : {desc['effect_size']['name']} -- "
        f"{desc['effect_size']['label']}"
    )
    print(f"solve targets  : {', '.join(desc['supports_solve'])}")
    if desc["extra_parameters"]:
        print("extra params   :")
        for p in desc["extra_parameters"]:
            flag = "required" if p["required"] else f"default {p['default']}"
            print(f"                 {p['name']} ({p['type']}, {flag}) -- {p['label']}")
    print(f"spec findings  : {', '.join(desc['spec_refs']) or '-'}")
    if desc["notes"]:
        print(f"notes          : {desc['notes']}")
    return EXIT_OK


# ---------------------------------------------------------------- batch mode
def _read_rows(path: str) -> tuple[list[dict], list[str]]:
    if path == "-":
        text = sys.stdin.read()
        name = "<stdin>"
    else:
        p = Path(path)
        if not p.is_file():
            raise UsageError(f"input file not found: {path}")
        text = p.read_text(encoding="utf-8-sig")
        name = p.name
    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        rows = [dict(d) for d in data]
        order = list(rows[0]) if rows else []
        return rows, order
    if stripped.startswith("{"):
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append(dict(json.loads(line)))
        order = list(rows[0]) if rows else []
        return rows, order
    dialect_sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(dialect_sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [dict(r) for r in reader]
    order = list(reader.fieldnames or [])
    if not order:
        raise UsageError(f"{name}: no header row found")
    return rows, order


_DECIMAL_COMMA = re.compile(r"^[-+]?\d*,\d+$")


def _normalise_number(text: str, kind: str) -> str:
    """Accept the number formats a spreadsheet export can produce.

    A vector file written on a locale that uses the comma as the decimal
    separator -- which includes the locales G*Power itself is most used in --
    otherwise fails every row with "could not convert string to float".

    `1,200` is genuinely ambiguous in isolation, so the field's *type* breaks
    the tie rather than a digit-counting heuristic: an integer field (sample
    size, tail count, predictor count) cannot carry a fractional part, so a
    comma there is always a thousands separator.

    `0,05` -> `0.05`    `1,200` (int) -> `1200`    `1,234.5` -> `1234.5`
    """
    t = text.replace(" ", "").replace(" ", "").replace("_", "")
    if "," not in t:
        return t
    if kind == "int":
        return t.replace(",", "")
    if "." in t:  # the dot is the decimal point, so commas group thousands
        return t.replace(",", "")
    if _DECIMAL_COMMA.match(t):
        return t.replace(",", ".")
    return t.replace(",", "")


_TAILS_WORDS = {
    "1": 1, "one": 1, "onetailed": 1, "onesided": 1, "1tailed": 1, "1sided": 1,
    "2": 2, "two": 2, "twotailed": 2, "twosided": 2, "2tailed": 2, "2sided": 2,
}


def parse_tails(value: Any) -> int | None:
    """1 or 2, also from the GUI's own wording ("One", "Two") and the usual
    "one-sided" / "two-tailed" spellings."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("", "na", "nan", "null", "none", "-", "n/a"):
        return None
    token = "".join(ch for ch in text if ch.isalnum())
    if token in _TAILS_WORDS:
        return _TAILS_WORDS[token]
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        number = None
    if number in (1.0, 2.0):
        return int(number)
    raise ValidationError(f"tails must be 1 or 2 (or One/Two), got {value!r}")


def _tails_arg(value: str) -> int:
    try:
        return parse_tails(value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _coerce(value: Any, kind: str):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "" or value.lower() in ("na", "nan", "null", "none", "-", "n/a"):
            return None
        if kind in ("int", "float"):
            value = _normalise_number(value, kind)
    if kind == "int":
        return int(round(float(value)))
    if kind == "float":
        return float(value)
    return str(value)


def _canonicalise_row(row: Mapping, exclude: Sequence[str] = ()) -> dict:
    """Map a raw CSV/JSON row onto canonical parameter names.

    ``exclude`` holds normalised column names that must NOT be treated as
    inputs -- in practice the ``--expect`` column, which holds the answer.  A
    vector file whose expected-N column is literally called ``N`` would
    otherwise feed the expected answer back in as a design parameter.
    """
    skip = {_norm_col(name) for name in exclude}
    out: dict[str, Any] = {}
    for key, val in row.items():
        if _norm_col(key) in skip:
            continue
        canon = _match_column(key)
        if canon is not None and canon not in out:
            out[canon] = val
    return out


def _run_batch_row(
    fields: Mapping,
    defaults: Mapping,
) -> eng.Result:
    test = fields.get("test") or defaults.get("test")
    if not test:
        raise ValidationError(
            "no test given: add a 'test' column or pass --test"
        )
    solve_for = fields.get("solve") or defaults.get("solve") or "n"
    tails = parse_tails(fields.get("tails"))
    if tails is None:
        tails = defaults.get("tails") or 2
    alpha = _coerce(fields.get("alpha"), "float")
    if alpha is None:
        alpha = defaults.get("alpha")
    extra = {}
    for key in _EXTRA_KEYS:
        val = _coerce(fields.get(key), "float" if key == "df" else "int")
        if val is not None:
            extra[key] = val
    return eng.solve(
        str(test),
        str(solve_for),
        alpha=alpha,
        power_target=_coerce(fields.get("power"), "float"),
        effect_size=_coerce(fields.get("effect_size"), "float"),
        tails=int(tails),
        n=_coerce(fields.get("n"), "int"),
        n1=_coerce(fields.get("n1"), "int"),
        n2=_coerce(fields.get("n2"), "int"),
        allocation_ratio=_coerce(fields.get("ratio"), "float"),
        allocation_rule=fields.get("allocation_rule") or None,
        beta_alpha_ratio=_coerce(fields.get("q"), "float"),
        extra=extra,
    )


_RESULT_COLUMNS = (
    "n1",
    "n2",
    "N",
    "power",
    "alpha",
    "effect_size",
    "df",
    "ncp",
    "crit_t",
    "status",
    "message",
)


def cmd_batch(args: argparse.Namespace) -> int:
    rows, order = _read_rows(args.input)
    defaults = {
        "test": args.test,
        "solve": args.solve,
        "tails": args.tails,
        "alpha": args.alpha,
    }
    prefix = args.result_prefix
    out_rows: list[dict] = []
    matched = 0
    compared = 0
    errors = 0

    exclude = (args.expect,) if args.expect else ()
    for index, raw in enumerate(rows, start=1):
        fields = _canonicalise_row(raw, exclude)
        record = dict(raw)
        computed: dict[str, Any] = {k: None for k in _RESULT_COLUMNS}
        try:
            result = _run_batch_row(fields, defaults)
            flat = _flatten_result(result)
            computed.update(
                {
                    "n1": flat["n1"],
                    "n2": flat["n2"],
                    "N": flat["N"],
                    "power": flat["power"],
                    "alpha": flat["alpha"],
                    "effect_size": flat["effect_size"],
                    "df": flat["df"],
                    "ncp": flat["ncp"],
                    "crit_t": flat["crit_t"],
                    "status": "ok",
                    "message": "",
                }
            )
        except (ValidationError, eng.NoSolutionError, ValueError, TypeError) as exc:
            errors += 1
            computed["status"] = "error"
            computed["message"] = f"{type(exc).__name__}: {exc}"
            if not args.continue_on_error:
                sys.stderr.write(f"{PROG}: row {index}: {computed['message']}\n")
                return EXIT_VALIDATION

        if args.expect:
            expected_raw = None
            for key in raw:
                if _norm_col(key) == _norm_col(args.expect):
                    expected_raw = raw[key]
                    break
            expected = _coerce(expected_raw, "int")
            if expected is not None and computed["N"] is not None:
                compared += 1
                if int(expected) == int(computed["N"]):
                    matched += 1
                    computed_match = "yes"
                else:
                    computed_match = "no"
                computed["expected_N"] = expected
                computed["match"] = computed_match

        for key, val in computed.items():
            record[f"{prefix}{key}"] = val
        out_rows.append(record)

    field_order = list(order)
    extra_cols = [
        c for c in (list(_RESULT_COLUMNS) + ["expected_N", "match"])
        if any(f"{prefix}{c}" in r for r in out_rows)
    ]
    field_order += [f"{prefix}{c}" for c in extra_cols]
    seen: set[str] = set()
    field_order = [c for c in field_order if not (c in seen or seen.add(c))]

    sink = sys.stdout if args.output == "-" else open(
        args.output, "w", encoding="utf-8", newline=""
    )
    try:
        if args.fmt == "csv":
            _write_csv(sink, out_rows, field_order)
        elif args.fmt == "jsonl":
            for r in out_rows:
                sink.write(json.dumps(r, allow_nan=False) + "\n")
        else:
            sink.write(_dump_json(out_rows) + "\n")
    finally:
        if sink is not sys.stdout:
            sink.close()

    if args.expect:
        rate = (matched / compared) if compared else 0.0
        sys.stderr.write(
            f"{PROG}: batch summary -- rows={len(out_rows)} compared={compared} "
            f"exact_N_matches={matched} rate={rate:.4f} errors={errors}\n"
        )
        if args.min_match is not None and rate < args.min_match:
            sys.stderr.write(
                f"{PROG}: FAIL -- match rate {rate:.4f} < required "
                f"{args.min_match:.4f}\n"
            )
            return EXIT_CONFORMANCE
    elif errors:
        sys.stderr.write(f"{PROG}: batch completed with {errors} row error(s)\n")
    return EXIT_OK


def cmd_curve(args: argparse.Namespace) -> int:
    extra = {}
    if args.predictors is not None:
        extra["predictors"] = args.predictors
    rows = eng.power_curve(
        args.test,
        alpha=args.alpha,
        effect_size=args.effect_size,
        tails=args.tails,
        n_from=args.n_from,
        n_to=args.n_to,
        n_step=args.n_step,
        allocation_ratio=args.ratio,
        allocation_rule=args.allocation_rule,
        extra=extra,
    )
    if args.fmt == "json":
        print(
            _dump_json(
                {
                    "schema": "gpower-rea/curve/1",
                    "test": resolve(args.test).key,
                    "alpha": args.alpha,
                    "effect_size": args.effect_size,
                    "tails": args.tails,
                    "points": rows,
                }
            )
        )
        return EXIT_OK
    buf = io.StringIO()
    names = sorted({k for r in rows for k in r})
    preferred = [c for c in ("n", "n1", "n2", "total", "power", "df", "noncentrality", "critical_t") if c in names]
    preferred += [c for c in names if c not in preferred]
    _write_csv(buf, rows, preferred)
    sys.stdout.write(buf.getvalue())
    return EXIT_OK


def cmd_effect_size(args: argparse.Namespace) -> int:
    fn = esmod.CALCULATORS[args.calculator]
    raw = _parse_params(args.param)
    kwargs: dict[str, Any] = {}
    for key, val in raw.items():
        if key in ("equal_n",):
            kwargs[key] = val.strip().lower() in ("1", "true", "yes", "y", "on")
        elif key in ("n1", "n2"):
            kwargs[key] = int(float(val))
        else:
            kwargs[key] = float(val)
    try:
        out = fn(**kwargs)
    except TypeError as exc:
        raise UsageError(f"{args.calculator}: {exc}") from None
    if args.fmt in ("json", "csv"):
        print(_dump_json({"schema": "gpower-rea/effect-size/1", **out}))
        return EXIT_OK
    es = out["effect_size"]
    print(f"{es['name']} = {es['value']:.10g}")
    print(f"formula: {out['formula']}")
    print(f"use with: --test {out['for_test']} --effect-size {es['value']:.10g}")
    return EXIT_OK


def cmd_selftest(args: argparse.Namespace) -> int:
    path = Path(args.vectors) if args.vectors else PUBLIC_VECTORS
    if not path.is_file():
        sys.stderr.write(f"{PROG}: vector file not found: {path}\n")
        return EXIT_USAGE
    rows, _ = _read_rows(str(path))
    total = 0
    exact = 0
    failures: list[str] = []
    for index, raw in enumerate(rows, start=1):
        fields = _canonicalise_row(raw)
        expected = _coerce(raw.get("expected_N") or raw.get("expected_n"), "int")
        expected_power = _coerce(
            raw.get("expected_power") or raw.get("expected_actual_power"), "float"
        )
        try:
            result = _run_batch_row(fields, {})
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            failures.append(f"row {index}: {type(exc).__name__}: {exc}")
            total += 1
            continue
        got_n = result.sample_size.get("total")
        ok = True
        if expected is not None:
            total += 1
            if int(expected) == int(got_n):
                exact += 1
            else:
                ok = False
                failures.append(
                    f"row {index} [{result.test}]: expected N={expected}, got {got_n}"
                )
        if expected_power is not None and abs(result.power - expected_power) > 5e-4:
            ok = False
            failures.append(
                f"row {index} [{result.test}]: expected power~{expected_power}, "
                f"got {result.power:.6f}"
            )
        if args.verbose and ok:
            src = raw.get("source", "")
            print(f"  ok  row {index:>3} {result.test:<24} N={got_n:<7} {src}")

    rate = (exact / total) if total else 0.0
    print(
        f"selftest: {exact}/{total} exact N matches (rate {rate:.4f}), "
        f"{len(failures)} finding(s)"
    )
    for f in failures:
        print(f"  FAIL {f}")
    if total == 0:
        sys.stderr.write(f"{PROG}: vector file contains no expected_N column\n")
        return EXIT_USAGE
    if rate < args.min_match or failures:
        return EXIT_CONFORMANCE
    return EXIT_OK


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
_COMMANDS = {
    "solve": cmd_solve,
    "list": cmd_list,
    "info": cmd_info,
    "batch": cmd_batch,
    "curve": cmd_curve,
    "effect-size": cmd_effect_size,
    "selftest": cmd_selftest,
}

_KNOWN_COMMANDS = tuple(_COMMANDS) + ("version",)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Implicit `solve`: `gpower --test ... --solve n ...` is accepted so that
    # callers do not have to know about subcommands (CLI-CONTRACT S-2).
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help", "-V", "--version"):
        argv = ["solve", *argv]

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed a message
        return int(exc.code or EXIT_USAGE)

    if getattr(args, "version", False) or args.command == "version":
        print(f"{PROG} {eng.ENGINE_VERSION} ({eng.SPEC_VERSION})")
        return EXIT_OK
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except UsageError as exc:
        sys.stderr.write(f"{PROG}: {exc}\n")
        return EXIT_USAGE
    except ValidationError as exc:
        sys.stderr.write(f"{PROG}: invalid input: {exc}\n")
        return EXIT_VALIDATION
    except eng.NoSolutionError as exc:
        sys.stderr.write(f"{PROG}: no solution: {exc}\n")
        return EXIT_NO_SOLUTION
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            os._exit(EXIT_OK)
    except KeyboardInterrupt:
        sys.stderr.write(f"{PROG}: interrupted\n")
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
