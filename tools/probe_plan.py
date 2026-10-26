#!/usr/bin/env python
"""Generate the REA probe worksheet.

    python tools/probe_plan.py                 # write probes/probe_worksheet.{csv,md}
    python tools/probe_plan.py --hunt-boundary # also search for a sub-5e-8 margin row

Each row of the worksheet is one GUI observation that *discriminates* between
two or more candidate behaviours.  The `observed` column is deliberately
empty: an operator with a G*Power installation fills it in, then
`python tools/harvest.py` compares the observations against the engine and
stamps `probes/REA-RESULTS.md`.

Predictions are not hand-typed -- every "engine" prediction below is computed
by the engine at generation time, so the worksheet can never drift away from
the implementation it is supposed to test.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpower_rea import effectsize as esmod  # noqa: E402
from gpower_rea import solve  # noqa: E402

OUT_DIR = ROOT / "probes"
CSV_PATH = OUT_DIR / "probe_worksheet.csv"
MD_PATH = OUT_DIR / "probe_worksheet.md"

FIELDS = [
    "probe_id",
    "finding",
    "statistical_test",
    "analysis",
    "inputs",
    "read_field",
    "engine_prediction",
    "competing_prediction",
    "discriminates",
    "observed",
    "notes",
]


def _f(x: float, d: int = 7) -> str:
    return f"{x:.{d}f}"


def _apriori(test, *, alpha, power, es, tails, ratio=None, rule=None, predictors=None):
    return solve(
        test, "n",
        alpha=alpha, power_target=power, effect_size=es, tails=tails,
        allocation_ratio=ratio, allocation_rule=rule,
        extra={"predictors": predictors} if predictors is not None else None,
    )


def _post(test, *, alpha, es, tails, n=None, n1=None, n2=None, predictors=None, df=None):
    extra = {}
    if predictors is not None:
        extra["predictors"] = predictors
    if df is not None:
        extra["df"] = df
    return solve(
        test, "power",
        alpha=alpha, effect_size=es, tails=tails, n=n, n1=n1, n2=n2,
        extra=extra or None,
    )


def rows(hunt_boundary: bool = False) -> list[dict]:
    out: list[dict] = []

    def add(pid, finding, test, analysis, inputs, field, engine, competing,
            disc="yes", notes=""):
        out.append({
            "probe_id": pid,
            "finding": finding,
            "statistical_test": test,
            "analysis": analysis,
            "inputs": inputs,
            "read_field": field,
            "engine_prediction": engine,
            "competing_prediction": competing,
            "discriminates": disc,
            "observed": "",
            "notes": notes,
        })

    # ---------------------------------------------------------------- E-001
    r = _apriori("ttest-indep-means", alpha=0.05, power=0.95, es=0.5, tails=2, ratio=1.0)
    add("P-01-a", "F-01", "two independent means", "a priori",
        "d=0.5, alpha=0.05, power=0.95, tails=2, ratio=1",
        "delta / Critical t / Df / N / Actual power",
        f"{_f(r.noncentrality)} / {_f(r.critical_t)} / {int(r.df)} / "
        f"{r.sample_size['total']} / {_f(r.power)}",
        "a different ncp convention matches at most one of the five",
        notes="four printed quantities from a two-parameter model")

    # ---------------------------------------------------------------- E-002
    for pid, alpha, df in (("P-02-a", 0.20, 30), ("P-02-b", 0.05, 30), ("P-02-c", 0.20, 5)):
        p = _post("ttest-generic", alpha=alpha, es=1e-12, tails=2, df=df).power
        add(pid, "F-02", "generic t test", "post hoc",
            f"delta=0, df={df}, alpha={alpha}, tails=2", "Power",
            _f(p), _f(alpha / 2.0),
            notes="far-tail term kept vs dropped; factor of two")
    p1 = _post("ttest-generic", alpha=0.20, es=1e-12, tails=1, df=30).power
    add("P-02-d", "F-02", "generic t test", "post hoc",
        "delta=0, df=30, alpha=0.20, tails=1", "Power",
        _f(p1), _f(p1), disc="no (control)",
        notes="one-tailed formula is identical under both candidates")

    # ---------------------------------------------------------------- E-003
    a = _apriori("ttest-one-sample", alpha=0.05, power=0.95, es=0.5, tails=2)
    b = _apriori("ttest-paired-means", alpha=0.05, power=0.95, es=0.5, tails=2)
    assert a.sample_size["total"] == b.sample_size["total"]
    add("P-03-a", "F-03", "matched pairs", "a priori",
        "dz=0.5, alpha=0.05, power=0.95, tails=2", "N / Df / Actual power",
        f"{a.sample_size['total']} / {int(a.df)} / {_f(a.power)}",
        f"{a.sample_size['total'] // 2} (if the field counts observations)",
        notes="N is the number of pairs")
    add("P-03-b", "F-03", "one sample vs matched pairs", "a priori",
        "d=dz=0.5, alpha=0.05, power=0.95, tails=2", "whole output panel",
        "identical across the two menu entries",
        "different Df if one entry counted observations")

    # ---------------------------------------------------------------- E-004
    import math
    for pid, n, rr in (("P-04-a", 20, 0.5), ("P-04-b", 10, 0.6), ("P-04-c", 12, 0.3)):
        res = _post("ttest-point-biserial", alpha=0.05, es=rr, tails=2, n=n)
        alt = rr * math.sqrt((n - 2) / (1.0 - rr * rr))
        add(pid, "F-04", "point biserial", "post hoc",
            f"|r|={rr}, alpha=0.05, N={n}, tails=2", "delta",
            _f(res.noncentrality), _f(alt),
            notes="sqrt(N) vs sqrt(N-2) in the noncentrality")
    for pid, rr in (("P-04-d", 0.5), ("P-04-e", 0.7)):
        good = _apriori("ttest-point-biserial", alpha=0.05, power=0.8, es=rr, tails=2)
        n = 3
        bad = None
        from gpower_rea.engine import _power_from_ncp
        while n < 100000:
            ncp = rr * math.sqrt((n - 2) / (1.0 - rr * rr))
            if _power_from_ncp(0.05, n - 2, ncp, 2)[0] >= 0.8:
                bad = n
                break
            n += 1
        add(pid, "F-04", "point biserial", "a priori",
            f"|r|={rr}, alpha=0.05, power=0.80, tails=2", "N",
            str(good.sample_size["total"]), str(bad),
            notes="same question, visible as a different N")

    # ---------------------------------------------------------------- E-005
    for pid, d, target in (("P-05-a", 0.30, 0.80), ("P-05-b", 0.42, 0.90),
                            ("P-05-c", 0.50, 0.95), ("P-05-d", 0.62, 0.85)):
        res = _apriori("ttest-indep-means", alpha=0.05, power=target, es=d,
                       tails=2, ratio=1.0)
        n1 = res.sample_size["n1"]
        odd = _post("ttest-indep-means", alpha=0.05, es=d, tails=2, n1=n1 - 1, n2=n1)
        odd_ok = odd.power >= target
        add(pid, "F-05", "two independent means", "a priori",
            f"d={d}, alpha=0.05, power={target}, tails=2, ratio=1", "Total sample size",
            str(res.sample_size["total"]),
            str(2 * n1 - 1) if odd_ok else str(res.sample_size["total"]),
            disc="yes" if odd_ok else "no (control)",
            notes=(f"odd split ({n1-1},{n1}) reaches {_f(odd.power)}"
                   + (" -> a total-N search would return it" if odd_ok
                      else " -> insufficient, both candidates agree")))

    # ---------------------------------------------------------------- E-006
    r = _apriori("ttest-indep-means", alpha=0.05, power=0.95, es=0.5, tails=2, ratio=1.0)
    add("P-06-a", "F-06", "two independent means", "a priori",
        "d=0.5, alpha=0.05, power=0.95, tails=2, ratio=1", "Actual power",
        _f(r.power), "0.9500000 (if the target were echoed back)",
        notes="actual power is recomputed at the integer design")
    tight = _apriori("ttest-one-sample", alpha=0.05, power=0.80, es=0.162, tails=2)
    add("P-06-b", "F-06", "one sample", "a priori",
        "d=0.162, alpha=0.05, power=0.80, tails=2", "N / Actual power",
        f"{tight.sample_size['total']} / {_f(tight.power)}",
        f"{tight.sample_size['total'] + 1} (if a >1.4e-6 epsilon slack were used)",
        notes="tightest margin over d in [0.100,1.200]: "
              f"{tight.power - 0.80:.3e}")

    # ---------------------------------------------------------------- E-007
    for pid, p in (("P-07-a", 1), ("P-07-b", 5)):
        res = _post("ttest-regression-coef", alpha=0.05, es=0.15, tails=2,
                    n=100, predictors=p)
        add(pid, "F-07", "linear regression, single coefficient", "post hoc",
            f"f2=0.15, alpha=0.05, N=100, predictors={p}, tails=2",
            "delta / Df / Power",
            f"{_f(res.noncentrality)} / {int(res.df)} / {_f(res.power)}",
            "delta would move with p if p entered the noncentrality",
            notes="delta must be identical across P-07-a and P-07-b")
    for pid, p in (("P-07-c", 1), ("P-07-d", 5)):
        res = _apriori("ttest-regression-coef", alpha=0.05, power=0.8, es=0.15,
                       tails=2, predictors=p)
        add(pid, "F-07", "linear regression, single coefficient", "a priori",
            f"f2=0.15, alpha=0.05, power=0.80, predictors={p}, tails=2",
            "N / Df", f"{res.sample_size['total']} / {int(res.df)}",
            "-", disc="supporting",
            notes="N barely moves with p; Df moves one-for-one")

    # ---------------------------------------------------------------- E-008
    neg1 = _post("ttest-one-sample", alpha=0.05, es=-0.5, tails=1, n=30)
    pos1 = _post("ttest-one-sample", alpha=0.05, es=0.5, tails=1, n=30)
    add("P-08-a", "F-08", "one sample", "post hoc",
        "d=-0.5, alpha=0.05, N=30, tails=1", "Power",
        f"{neg1.power:.3e} (signed)", f"{_f(pos1.power)} (absolutised)",
        notes="third candidate: the GUI refuses the input")
    neg2 = _post("ttest-one-sample", alpha=0.05, es=-0.5, tails=2, n=30)
    add("P-08-b", "F-08", "one sample", "post hoc",
        "d=-0.5, alpha=0.05, N=30, tails=2", "Power",
        _f(neg2.power), _f(neg2.power), disc="no (control)",
        notes="two-tailed power is sign-invariant")
    apn = _apriori("ttest-one-sample", alpha=0.05, power=0.8, es=-0.5, tails=1)
    add("P-08-c", "F-08", "one sample", "a priori",
        "d=-0.5, alpha=0.05, power=0.80, tails=1", "N",
        f"{apn.sample_size['total']} (|ES| used)", "no solution (if signed)")

    # ---------------------------------------------------------------- E-009
    for pid, ratio in (("P-09-a", 0.5), ("P-09-b", 1.5), ("P-09-c", 2.0), ("P-09-d", 3.0)):
        g1 = _apriori("ttest-indep-means", alpha=0.05, power=0.95, es=0.5,
                      tails=2, ratio=ratio, rule="n1-grid")
        g2 = _apriori("ttest-indep-means", alpha=0.05, power=0.95, es=0.5,
                      tails=2, ratio=ratio, rule="total-grid")
        same = g1.sample_size["total"] == g2.sample_size["total"]
        add(pid, "F-09", "two independent means", "a priori",
            f"d=0.5, alpha=0.05, power=0.95, tails=2, ratio={ratio}",
            "n1 / n2 / N / Actual power",
            f"{g1.sample_size['n1']} / {g1.sample_size['n2']} / "
            f"{g1.sample_size['total']} / {_f(g1.power)}",
            f"{g2.sample_size['n1']} / {g2.sample_size['n2']} / "
            f"{g2.sample_size['total']} / {_f(g2.power)}",
            disc="no (control)" if same else "yes",
            notes=("n1-grid vs total-grid; under n1-grid n2/n1 is exactly "
                   f"the ratio ({g1.sample_size['n2']}/{g1.sample_size['n1']})"))

    # ---------------------------------------------------------------- E-010
    for pid, q in (("P-10-a", 1.0), ("P-10-b", 2.0), ("P-10-c", 4.0)):
        res = solve("ttest-indep-means", "compromise", effect_size=0.5, tails=2,
                    n1=40, n2=40, beta_alpha_ratio=q)
        add(pid, "F-10", "two independent means", "compromise",
            f"d=0.5, n1=n2=40, tails=2, beta/alpha={q}",
            "alpha / beta / Power / Critical t",
            f"{_f(res.alpha)} / {_f(res.target['beta'])} / {_f(res.power)} / "
            f"{_f(res.critical_t)}",
            "different alpha if the far-tail term (F-02) is dropped",
            notes="also check: feeding alpha back through post hoc reproduces Power")

    # ---------------------------------------------------------------- E-011
    rms = esmod.d_two_independent_means(10, 8, 2, 6, equal_n=True)
    pooled = esmod.d_two_independent_means(10, 8, 2, 6, equal_n=False, n1=10, n2=40)
    add("P-11-a", "F-11", "two independent means / Determine =>", "effect size",
        "mean1=10, mean2=8, sd1=2, sd2=6, option 'n1 = n2'", "Effect size d",
        _f(rms["effect_size"]["value"]), _f(pooled["effect_size"]["value"]),
        notes=f"RMS sd={_f(rms['pooled_sd'])} vs pooled sd={_f(pooled['pooled_sd'])}")
    add("P-11-b", "F-11", "two independent means / Determine =>", "effect size",
        "mean1=10, mean2=8, sd1=2, sd2=6, n1=10, n2=40, option 'n1 != n2'",
        "Effect size d",
        _f(pooled["effect_size"]["value"]), _f(rms["effect_size"]["value"]),
        notes="the claim is the only candidate under which P-11-a and P-11-b differ")
    ctrl = esmod.d_two_independent_means(5, 3, 4, 4, equal_n=True)
    add("P-11-c", "F-11", "two independent means / Determine =>", "effect size",
        "mean1=5, mean2=3, sd1=sd2=4 (either option)", "Effect size d",
        _f(ctrl["effect_size"]["value"]), _f(ctrl["effect_size"]["value"]),
        disc="no (control)", notes="options coincide when the SDs are equal")

    # ---------------------------------------------------------------- E-012
    tight = _apriori("ttest-one-sample", alpha=0.05, power=0.80, es=0.162, tails=2)
    add("P-12-a", "F-12", "one sample", "a priori",
        "d=0.162, alpha=0.05, power=0.80, tails=2", "N / Actual power",
        f"{tight.sample_size['total']} / {_f(tight.power)}",
        f"{tight.sample_size['total'] - 1} (epsilon slack > 1.4e-6)",
        notes="no epsilon slack, comparison on the unrounded double")
    if hunt_boundary:
        found = _hunt_boundary()
        if found:
            d, n, pw = found
            add("P-12-b", "F-12", "one sample", "a priori",
                f"d={d:.6f}, alpha=0.05, power=0.80, tails=2", "N / Actual power",
                f"{n} / {_f(pw)}", f"{n + 1} (if power were rounded to 7 dp first)",
                notes=f"margin {pw - 0.80:.3e} < 5e-8")
        else:
            add("P-12-b", "F-12", "one sample", "a priori",
                "(none found in the searched range)", "-", "-", "-",
                disc="not found", notes="re-run with a wider --hunt-steps")
    return out


def _hunt_boundary(steps: int = 400_000):
    """Look for an a-priori case whose margin over the target is < 5e-8."""
    best = None
    for i in range(steps):
        d = 0.10 + i * 1e-6
        if d > 1.20:
            break
        res = solve("ttest-one-sample", "n", alpha=0.05, power_target=0.80,
                    effect_size=d, tails=2)
        margin = res.power - 0.80
        if best is None or margin < best[0]:
            best = (margin, d, res.sample_size["total"], res.power)
        if margin < 5e-8:
            return d, res.sample_size["total"], res.power
    return None


def render_markdown(data: list[dict]) -> str:
    lines = [
        "# REA probe worksheet",
        "",
        "Generated by `python tools/probe_plan.py`. **Do not hand-edit the",
        "prediction columns** -- they are computed from the engine, so editing",
        "them would decouple the worksheet from the implementation it tests.",
        "",
        "## How to use it",
        "",
        "1. Open G\\*Power 3.1.9.x on a machine where you are licensed to run it.",
        "2. For each row, follow `statistical_test` + `analysis` + `inputs`,",
        "   press **Calculate**, and copy the value of `read_field` verbatim",
        "   (all printed decimals) into the `observed` column of",
        "   `probes/probe_worksheet.csv`.",
        "3. Run `python tools/harvest.py`. It compares every observation with",
        "   the engine prediction and the competing prediction, and writes",
        "   `probes/REA-RESULTS.md` with one verdict per finding.",
        "",
        "Rows marked `discriminates = no (control)` cannot separate the",
        "candidates; they exist to catch setup mistakes. A control row that",
        "disagrees means the probe was run wrong, not that a finding is false.",
        "",
        f"{len(data)} rows, covering findings "
        f"{', '.join(sorted({r['finding'] for r in data}))}.",
        "",
    ]
    for r in data:
        lines.append(f"### {r['probe_id']} — {r['finding']}")
        lines.append("")
        lines.append(f"- **test**: {r['statistical_test']}")
        lines.append(f"- **analysis**: {r['analysis']}")
        lines.append(f"- **inputs**: `{r['inputs']}`")
        lines.append(f"- **read**: {r['read_field']}")
        lines.append(f"- **engine predicts**: `{r['engine_prediction']}`")
        lines.append(f"- **competing candidate**: `{r['competing_prediction']}`")
        lines.append(f"- **discriminates**: {r['discriminates']}")
        if r["notes"]:
            lines.append(f"- **notes**: {r['notes']}")
        lines.append("- **observed**: _______________________")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hunt-boundary", action="store_true")
    args = ap.parse_args()

    data = rows(hunt_boundary=args.hunt_boundary)
    OUT_DIR.mkdir(exist_ok=True)

    if CSV_PATH.is_file():
        # Preserve observations that have already been entered.
        existing = {}
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("observed"):
                    existing[row["probe_id"]] = row["observed"]
        for row in data:
            if row["probe_id"] in existing:
                row["observed"] = existing[row["probe_id"]]
        if existing:
            print(f"carried over {len(existing)} existing observation(s)")

    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(data)
    MD_PATH.write_text(render_markdown(data), encoding="utf-8", newline="\n")

    disc = sum(1 for r in data if r["discriminates"] == "yes")
    print(f"wrote {CSV_PATH} and {MD_PATH}")
    print(f"  {len(data)} rows, {disc} of them discriminating")
    print("  fill in the 'observed' column, then run: python tools/harvest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
