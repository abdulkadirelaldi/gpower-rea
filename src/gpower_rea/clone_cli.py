"""``gpower-clone`` -- the course's fixed CLI contract, over the same engine.

    gpower-clone --test t2-indep --mode a-priori --tails 2 --d 0.5 \\
                 --alpha 0.05 --power 0.95 --ratio 1
    {"n1":105,"n2":105,"n_total":210,"actual_power":0.9501,"critical":1.9714,"df":208,"ncp":3.6228}

    gpower-clone --test t2-indep --mode post-hoc --tails 2 --d 0.5 \\
                 --alpha 0.05 --n1 40 --n2 40

Exactly one line of JSON on stdout, always.  On invalid input the line is
``{"error": "..."}`` and the exit code is non-zero.  Like the rest of the
package this is a thin adapter: every number comes from
``gpower_rea.engine.solve`` (docs/ARCHITECTURE.md, invariant I-3).
"""

from __future__ import annotations

import argparse
import json
import sys

from . import engine as eng
from .procedures import ValidationError

#: Contract test labels -> engine keys.  The labels are the course's
#: (t2-indep, t-paired, ...); families this engine does not implement are
#: refused by name instead of being guessed.
TESTS = {
    "t2-indep": "ttest-indep-means",
    "t-paired": "ttest-paired-means",
}
UNSUPPORTED = ("anova-oneway", "chi2-contingency", "multireg-r2")
MODES = {"a-priori": "n", "apriori": "n", "post-hoc": "power", "posthoc": "power"}

#: Decimals of the real-valued fields, as in the contract's example line.
DIGITS = 4

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_NO_SOLUTION = 4
EXIT_INTERNAL = 1


class _Parser(argparse.ArgumentParser):
    """argparse that reports its errors as the contract's JSON line."""

    def error(self, message):  # noqa: D401 -- argparse API
        raise ValidationError(message)

    def exit(self, status=0, message=None):
        if status:
            raise ValidationError((message or "invalid arguments").strip())
        raise SystemExit(status)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="gpower-clone", add_help=True,
                description="Sample size / power for the t2-indep family "
                            "(course CLI contract).")
    p.add_argument("--test", required=True)
    p.add_argument("--mode", required=True)
    p.add_argument("--tails", type=int, default=2)
    p.add_argument("--d", "--dz", "--effect-size", dest="d", type=float)
    p.add_argument("--alpha", type=float)
    p.add_argument("--power", type=float)
    p.add_argument("--ratio", type=float, default=1.0)
    p.add_argument("--n1", type=int)
    p.add_argument("--n2", type=int)
    p.add_argument("--n", "--n-total", dest="n", type=int)
    return p


def _r(x: float) -> float:
    return round(float(x), DIGITS)


def run(argv: list[str]) -> dict:
    a = build_parser().parse_args(argv)
    test = a.test.strip().lower()
    if test in UNSUPPORTED:
        raise ValidationError(
            f"test '{a.test}' is not implemented by this engine "
            f"(supported: {', '.join(TESTS)})")
    if test not in TESTS:
        raise ValidationError(
            f"unknown test '{a.test}' (supported: {', '.join(TESTS)})")
    mode = MODES.get(a.mode.strip().lower())
    if mode is None:
        raise ValidationError(f"unknown mode '{a.mode}' (use a-priori or post-hoc)")
    if a.tails not in (1, 2):
        raise ValidationError(f"tails must be 1 or 2, got {a.tails}")
    if a.d is None:
        raise ValidationError("--d is required")
    if a.alpha is None:
        raise ValidationError("--alpha is required")
    key = TESTS[test]
    two_group = key == "ttest-indep-means"

    if mode == "n":
        if a.power is None:
            raise ValidationError("--power is required in a-priori mode")
        res = eng.solve(key, "n", alpha=a.alpha, power_target=a.power,
                        effect_size=a.d, tails=a.tails,
                        allocation_ratio=a.ratio if two_group else None)
    else:
        if two_group:
            if a.n1 is None and a.n2 is None and a.n is not None:
                # n_total with the ratio, split the way a priori reports it
                res = eng.solve(key, "power", alpha=a.alpha, effect_size=a.d,
                                tails=a.tails, n=a.n, allocation_ratio=a.ratio)
            elif a.n1 is None or a.n2 is None:
                raise ValidationError("post-hoc mode needs --n1 and --n2")
            else:
                res = eng.solve(key, "power", alpha=a.alpha, effect_size=a.d,
                                tails=a.tails, n1=a.n1, n2=a.n2)
        else:
            n = a.n if a.n is not None else a.n1
            if n is None:
                raise ValidationError("post-hoc mode needs --n (number of pairs)")
            res = eng.solve(key, "power", alpha=a.alpha, effect_size=a.d,
                            tails=a.tails, n=n)

    ss = res.sample_size
    n1 = ss.get("n1", ss.get("n"))
    n2 = ss.get("n2", 0)
    return {
        "n1": int(n1),
        "n2": int(n2),
        "n_total": int(ss["total"]),
        "actual_power": _r(res.power),
        "critical": _r(res.critical_t),
        "df": int(res.df) if float(res.df).is_integer() else _r(res.df),
        "ncp": _r(res.noncentrality),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if any(x in ("-h", "--help") for x in argv):
        build_parser().print_help()
        return EXIT_OK
    try:
        out, code = run(argv), EXIT_OK
    except ValidationError as exc:
        out, code = {"error": str(exc)}, EXIT_INVALID
    except eng.NoSolutionError as exc:
        out, code = {"error": str(exc)}, EXIT_NO_SOLUTION
    except (ValueError, OverflowError) as exc:
        out, code = {"error": str(exc)}, EXIT_INVALID
    except Exception as exc:  # noqa: BLE001 -- the contract: always one JSON line
        out, code = {"error": f"internal error: {exc}"}, EXIT_INTERNAL
    sys.stdout.write(json.dumps(out, separators=(",", ":"), ensure_ascii=False,
                                allow_nan=False) + "\n")
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
