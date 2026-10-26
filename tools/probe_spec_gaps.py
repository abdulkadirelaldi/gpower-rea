#!/usr/bin/env python
"""Probe the regions that cleanroom/SPEC-GAPS.md flags as underspecified.

    python tools/probe_spec_gaps.py
    python tools/probe_spec_gaps.py --markdown

The clean-room implementation reported twelve points on which SPEC.md v1.0 does
not determine behaviour.  A gap only matters if the two implementations
actually diverge there, so this script goes and looks: for each gap it runs the
shipped engine and the clean-room implementation on inputs inside the
underspecified region and reports whether they agree.

Three outcomes per gap:

    AGREE       both implementations do the same thing (the gap is latent --
                real, but it happened not to bite)
    DIVERGE     they do different things (the gap is live, and SPEC.md has to
                say which behaviour is intended)
    N/A         the region is unreachable, or the question cannot be observed
                through the public surface

This is the payoff of the two-session protocol: a divergence here is a
specification defect that no amount of testing the shipped engine against
itself could have surfaced.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "cleanroom" / "src"))

from gpower_rea import solve  # noqa: E402

try:
    cr = importlib.import_module("gpower_cleanroom")
except Exception as exc:  # noqa: BLE001
    print(f"clean-room implementation unavailable: {exc}", file=sys.stderr)
    raise SystemExit(2) from exc

AGREE, DIVERGE, NA = "AGREE", "DIVERGE", "N/A"


def _call(fn, *args, **kwargs):
    """Run a callable, returning ('ok', value) or ('raise', exception name)."""
    try:
        return "ok", fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the outcome under test
        return "raise", type(exc).__name__


def _cmp(mine, theirs, extract_mine, extract_theirs):
    """Compare two _call results, projecting the success values first."""
    (sm, vm), (st, vt) = mine, theirs
    if sm == "raise" and st == "raise":
        return AGREE, f"both raise ({vm} / {vt})"
    if sm == "raise":
        return DIVERGE, f"shipped raises {vm}; cleanroom returns {extract_theirs(vt)}"
    if st == "raise":
        return DIVERGE, f"shipped returns {extract_mine(vm)}; cleanroom raises {vt}"
    a, b = extract_mine(vm), extract_theirs(vt)
    if a == b:
        return AGREE, f"both give {a}"
    return DIVERGE, f"shipped {a} vs cleanroom {b}"


def _n(res):
    return res.sample_size["total"]


def _crn(res):
    return res["total"]


def _p(res, digits=9):
    return round(res.power, digits)


def _crp(res, digits=9):
    return round(res["power"], digits)


GAPS = []


def gap(ident, title):
    def deco(fn):
        GAPS.append((ident, title, fn))
        return fn

    return deco


@gap("G-01", "sign rule of the compromise analysis (one tail, negative ES)")
def g01():
    mine = _call(
        solve, "ttest-indep-means", "compromise",
        effect_size=-0.5, tails=1, n1=40, n2=40, beta_alpha_ratio=1.0,
    )
    theirs = _call(
        cr.compromise, "ttest-indep-means",
        effect_size=-0.5, beta_alpha_ratio=1.0, tails=1, n1=40, n2=40,
    )
    return _cmp(
        mine, theirs,
        lambda r: f"alpha={r.alpha:.7f}",
        lambda r: f"alpha={r['alpha']:.7f}",
    )


@gap("G-02", "negative f-squared for the regression coefficient test")
def g02():
    mine = _call(
        solve, "ttest-regression-coef", "power",
        alpha=0.05, effect_size=-0.15, tails=2, n=60, extra={"predictors": 3},
    )
    theirs = _call(
        cr.achieved_power, "ttest-regression-coef",
        alpha=0.05, effect_size=-0.15, tails=2, n=60, predictors=3,
    )
    return _cmp(mine, theirs, _p, _crp)


@gap("G-03", "which effect size the result reports after |ES| substitution")
def g03():
    mine = _call(
        solve, "ttest-one-sample", "n",
        alpha=0.05, power_target=0.8, effect_size=-0.5, tails=1,
    )
    theirs = _call(
        cr.required_sample_size, "ttest-one-sample",
        alpha=0.05, power=0.8, effect_size=-0.5, tails=1,
    )
    return _cmp(
        mine, theirs,
        lambda r: r.effect_size["value"],
        lambda r: r["effect_size"],
    )


@gap("G-04", "sensitivity answer at the open lower end of the ES domain")
def g04():
    # A target power strictly BELOW alpha is met by an arbitrarily small
    # effect, so the answer is whatever each implementation uses as its lower
    # bracket.  Using target == alpha instead would sit on a knife edge that
    # one bit of rounding decides, which tests the float and not the rule.
    mine = _call(
        solve, "ttest-one-sample", "effect-size",
        alpha=0.20, power_target=0.15, tails=2, n=50,
    )
    theirs = _call(
        cr.detectable_effect_size, "ttest-one-sample",
        alpha=0.20, power=0.15, tails=2, n=50,
    )
    return _cmp(
        mine, theirs,
        lambda r: f"{r.effect_size['value']:.3e}",
        lambda r: f"{r['effect_size']:.3e}",
    )


@gap("G-05", "criterion analysis when the answer is a very small alpha")
def g05():
    mine = _call(
        solve, "ttest-one-sample", "alpha",
        power_target=0.05, effect_size=1.5, tails=2, n=200,
    )
    theirs = _call(
        cr.required_alpha, "ttest-one-sample",
        power=0.05, effect_size=1.5, tails=2, n=200,
    )
    return _cmp(
        mine, theirs,
        lambda r: f"{r.alpha:.3e}",
        lambda r: f"{r['alpha']:.3e}",
    )


@gap("G-06", "sign of the reported critical t for a one-tailed alpha > 0.5")
def g06():
    mine = _call(
        solve, "ttest-one-sample", "power",
        alpha=0.75, effect_size=0.3, tails=1, n=30,
    )
    theirs = _call(
        cr.achieved_power, "ttest-one-sample",
        alpha=0.75, effect_size=0.3, tails=1, n=30,
    )
    return _cmp(
        mine, theirs,
        lambda r: round(r.critical_t, 7),
        lambda r: round(r["critical_t"], 7),
    )


@gap("G-07", "inadmissible leading grid points at an extreme allocation ratio")
def g07():
    results = []
    for ratio, rule in (
        (20.0, "total-grid"),
        (20.0, "n1-grid"),
        (0.05, "total-grid"),
        (0.05, "n1-grid"),
    ):
        mine = _call(
            solve, "ttest-indep-means", "n",
            alpha=0.05, power_target=0.8, effect_size=0.8, tails=2,
            allocation_ratio=ratio, allocation_rule=rule,
        )
        theirs = _call(
            cr.required_sample_size, "ttest-indep-means",
            alpha=0.05, power=0.8, effect_size=0.8, tails=2,
            allocation_ratio=ratio, allocation_rule=rule,
        )
        results.append((f"R={ratio} {rule}", _cmp(mine, theirs, _n, _crn)))
    verdicts = {v for _, (v, _) in results}
    detail = "; ".join(f"{label} -> {note}" for label, (_, note) in results)
    return (DIVERGE if DIVERGE in verdicts else AGREE), detail


@gap("G-08", "zero effect size in a solving analysis")
def g08():
    mine = _call(
        solve, "ttest-one-sample", "n",
        alpha=0.05, power_target=0.8, effect_size=0.0, tails=2,
    )
    theirs = _call(
        cr.required_sample_size, "ttest-one-sample",
        alpha=0.05, power=0.8, effect_size=0.0, tails=2,
    )
    return _cmp(mine, theirs, _n, _crn)


@gap("G-09", "display rounding mode (half-up vs half-even) at 7 decimals")
def g09():
    return NA, (
        "both implementations keep full precision in the returned value and "
        "round only when rendering text, so the mode cannot affect any "
        "numeric comparison this harness makes"
    )


@gap("G-10", "surface for the F-09 behaviour INTERFACE.md does not name")
def g10():
    theirs = _call(
        cr.required_sample_size, "ttest-indep-means",
        alpha=0.05, power=0.9, effect_size=0.5, tails=2,
        allocation_ratio=2.0, allocation_rule="total-grid",
    )
    mine = _call(
        solve, "ttest-indep-means", "n",
        alpha=0.05, power_target=0.9, effect_size=0.5, tails=2,
        allocation_ratio=2.0, allocation_rule="total-grid",
    )
    return _cmp(mine, theirs, _n, _crn)


@gap("G-11", "an inapplicable design argument (predictors on a one-sample test)")
def g11():
    mine = _call(
        solve, "ttest-one-sample", "power",
        alpha=0.05, effect_size=0.5, tails=2, n=40, extra={"predictors": 3},
    )
    theirs = _call(
        cr.achieved_power, "ttest-one-sample",
        alpha=0.05, effect_size=0.5, tails=2, n=40, predictors=3,
    )
    return _cmp(mine, theirs, _p, _crp)


@gap("G-12", "generic t test with fractional degrees of freedom below 1")
def g12():
    mine = _call(
        solve, "ttest-generic", "power",
        alpha=0.05, effect_size=2.0, tails=2, extra={"df": 0.5},
    )
    theirs = _call(
        cr.achieved_power, "ttest-generic",
        alpha=0.05, effect_size=2.0, tails=2, df=0.5,
    )
    return _cmp(mine, theirs, lambda r: _p(r, 7), lambda r: _crp(r, 7))


def run():
    rows = []
    for ident, title, fn in GAPS:
        try:
            verdict, note = fn()
        except Exception as exc:  # noqa: BLE001 - harness bug, report it
            verdict, note = "ERROR", f"{type(exc).__name__}: {exc}"
        rows.append((ident, title, verdict, note))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    rows = run()
    counts: dict[str, int] = {}
    for _, _, verdict, _ in rows:
        counts[verdict] = counts.get(verdict, 0) + 1

    if args.markdown:
        print("| gap | underspecified point | outcome | detail |")
        print("|---|---|---|---|")
        for ident, title, verdict, note in rows:
            print(f"| `{ident}` | {title} | **{verdict}** | {note} |")
        print()
        print(", ".join(f"{v}: {c}" for v, c in sorted(counts.items())))
        return 0

    print("=" * 76)
    print("SPEC GAP DIVERGENCE PROBE")
    print("  shipped engine vs the independent clean-room implementation,")
    print("  on the regions cleanroom/SPEC-GAPS.md flags as underspecified")
    print("=" * 76)
    for ident, title, verdict, note in rows:
        print(f"[{verdict:^8}] {ident}  {title}")
        print(f"            {note}")
    print()
    print("  " + ", ".join(f"{v}: {c}" for v, c in sorted(counts.items())))
    if counts.get("DIVERGE"):
        print()
        print("  A DIVERGE row is a live specification defect: two independent")
        print("  readers of SPEC.md v1.0 behaved differently. Each one needs a")
        print("  sentence in SPEC.md, not a patch to either implementation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
