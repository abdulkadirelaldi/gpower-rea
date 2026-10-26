#!/usr/bin/env python
"""Judge an independent clean-room implementation against the frozen contract.

    python tools/judge_cleanroom.py                 # human-readable report
    python tools/judge_cleanroom.py --markdown      # paste-ready for SESSION-LOG
    python tools/judge_cleanroom.py --strict        # exit 1 on any divergence

This is the *verification* half of docs/CLEANROOM-PROTOCOL.md.  Session B
produced `cleanroom/src/gpower_cleanroom/` from SPEC.md alone; this script
checks it the only way that is meaningful:

  * against the SAME 401 conformance vectors the shipped engine is held to,
    with the SAME tolerances (exact integer N, 5e-7 on power);
  * against the three cross-entry identities of SPEC F-03 / F-04 / F-07;
  * against the two-sided-size property of SPEC F-02;
  * for round-tripping between the five analysis types.

It deliberately does NOT diff the two implementations.  They are allowed --
expected -- to differ internally; only the specified behaviour is contractual.

A second check runs too: `--similarity` reports lexical overlap with the
shipped engine, so a clean-room claim can be sanity-checked rather than
trusted.  High overlap would suggest the boundary leaked.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEANROOM_SRC = ROOT / "cleanroom" / "src"
SHIPPED_SRC = ROOT / "src" / "gpower_rea"

sys.path.insert(0, str(ROOT / "src"))

from gpower_rea import solve  # noqa: E402
from gpower_rea.cli import PUBLIC_VECTORS  # noqa: E402

POWER_TOL = 5e-7


# --------------------------------------------------------------------------
def load_cleanroom():
    if not CLEANROOM_SRC.is_dir():
        return None, f"{CLEANROOM_SRC} does not exist"
    sys.path.insert(0, str(CLEANROOM_SRC))
    try:
        mod = importlib.import_module("gpower_cleanroom")
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        return None, f"import failed: {type(exc).__name__}: {exc}"
    missing = [
        name
        for name in (
            "required_sample_size",
            "achieved_power",
            "required_alpha",
            "detectable_effect_size",
            "compromise",
            "TESTS",
        )
        if not hasattr(mod, name)
    ]
    if missing:
        return None, f"missing public names: {missing}"
    return mod, None


def _vectors() -> list[dict]:
    with Path(PUBLIC_VECTORS).open(encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


# --------------------------------------------------------------------------
def check_vectors(cr) -> dict:
    rows = _vectors()
    exact = 0
    power_ok = 0
    errors: list[str] = []
    per_test: Counter = Counter()
    per_test_total: Counter = Counter()

    for row in rows:
        test = row["test"]
        per_test_total[test] += 1
        kwargs = dict(
            alpha=float(row["alpha"]),
            power=float(row["power"]),
            effect_size=float(row["effect_size"]),
            tails=int(row["tails"]),
        )
        if row["ratio"]:
            kwargs["allocation_ratio"] = float(row["ratio"])
        if row["predictors"]:
            kwargs["predictors"] = int(row["predictors"])
        try:
            got = cr.required_sample_size(test, **kwargs)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{row['id']} [{test}]: {type(exc).__name__}: {exc}")
            continue
        want_n = int(row["expected_N"])
        want_p = float(row["expected_power"])
        if int(got.get("total", -1)) == want_n:
            exact += 1
            per_test[test] += 1
        else:
            errors.append(
                f"{row['id']} [{test}]: N {got.get('total')} != {want_n}"
            )
        if abs(float(got.get("power", float("nan"))) - want_p) <= POWER_TOL:
            power_ok += 1

    return {
        "rows": len(rows),
        "exact_n": exact,
        "power_within_tol": power_ok,
        "errors": errors,
        "per_test": {
            t: (per_test[t], per_test_total[t]) for t in sorted(per_test_total)
        },
    }


def check_identities(cr) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    # F-03: one sample == matched pairs
    ok, detail = True, []
    for d in (0.2, 0.5, 0.9):
        for tails in (1, 2):
            a = cr.required_sample_size(
                "ttest-one-sample", alpha=0.05, power=0.9, effect_size=d, tails=tails
            )["total"]
            b = cr.required_sample_size(
                "ttest-paired-means", alpha=0.05, power=0.9, effect_size=d, tails=tails
            )["total"]
            if a != b:
                ok = False
                detail.append(f"d={d} tails={tails}: {a} vs {b}")
    out.append(("F-03  one sample == matched pairs", ok, "; ".join(detail)))

    # F-04: point biserial == balanced two group
    ok, detail = True, []
    for r in (0.2, 0.3, 0.4):
        d = 2.0 * r / math.sqrt(1.0 - r * r)
        a = cr.achieved_power(
            "ttest-point-biserial", alpha=0.05, effect_size=r, tails=2, n=80
        )
        b = cr.achieved_power(
            "ttest-indep-means", alpha=0.05, effect_size=d, tails=2, n1=40, n2=40
        )
        if abs(a["ncp"] - b["ncp"]) > 1e-10 or abs(a["power"] - b["power"]) > 1e-10:
            ok = False
            detail.append(
                f"r={r}: ncp {a['ncp']:.10f} vs {b['ncp']:.10f}, "
                f"power {a['power']:.10f} vs {b['power']:.10f}"
            )
    out.append(("F-04  point biserial == balanced two group", ok, "; ".join(detail)))

    # F-07: regression with 1 predictor == point biserial
    ok, detail = True, []
    for r in (0.15, 0.3, 0.45):
        f2 = r * r / (1.0 - r * r)
        a = cr.required_sample_size(
            "ttest-point-biserial", alpha=0.05, power=0.9, effect_size=r, tails=2
        )
        b = cr.required_sample_size(
            "ttest-regression-coef", alpha=0.05, power=0.9, effect_size=f2,
            tails=2, predictors=1,
        )
        if a["total"] != b["total"] or abs(a["df"] - b["df"]) > 1e-9:
            ok = False
            detail.append(
                f"r={r}: N {a['total']} vs {b['total']}, df {a['df']} vs {b['df']}"
            )
    out.append(("F-07  regression(p=1) == point biserial", ok, "; ".join(detail)))

    # F-02: two-sided size at the null is alpha, not alpha/2
    ok, detail = True, []
    for alpha in (0.05, 0.10, 0.20):
        for df in (5, 30):
            p = cr.achieved_power(
                "ttest-generic", alpha=alpha, effect_size=1e-12, tails=2, df=df
            )["power"]
            if abs(p - alpha) > 1e-7:
                ok = False
                detail.append(
                    f"alpha={alpha} df={df}: got {p:.8f} "
                    f"({'looks like alpha/2' if abs(p - alpha / 2) < 1e-6 else 'neither'})"
                )
    out.append(("F-02  two-sided size at the null == alpha", ok, "; ".join(detail)))

    # F-05: balanced a-priori total is always even
    ok, detail = True, []
    for d in (0.2, 0.33, 0.5, 0.77, 1.1):
        for pw in (0.8, 0.9, 0.95):
            total = cr.required_sample_size(
                "ttest-indep-means", alpha=0.05, power=pw, effect_size=d, tails=2,
                allocation_ratio=1.0,
            )["total"]
            if total % 2:
                ok = False
                detail.append(f"d={d} power={pw}: N={total} is odd")
    out.append(("F-05  balanced a-priori total is even", ok, "; ".join(detail)))

    # F-09 (v1.2, observed): even totals at every ratio, split by
    # round_half_up(N/(1+R)) -- and the four pre-registered G*Power rows.
    ok, detail = True, []
    for ratio in (0.5, 1.5, 2.0, 2.5, 3.0, 4.0):
        for d in (0.3, 0.5, 0.8):
            res = cr.required_sample_size(
                "ttest-indep-means", alpha=0.05, power=0.9, effect_size=d, tails=2,
                allocation_ratio=ratio,
            )
            n_tot = res["n1"] + res["n2"]
            want_n1 = int(math.floor(n_tot / (1.0 + ratio) + 0.5))
            if n_tot % 2 or res["n1"] != want_n1:
                ok = False
                detail.append(f"R={ratio} d={d}: {res['n1']}/{res['n2']}")
    for ratio, want in ((0.5, (157, 79)), (1.5, (88, 132)), (2.0, (79, 157)), (3.0, (70, 210))):
        res = cr.required_sample_size(
            "ttest-indep-means", alpha=0.05, power=0.95, effect_size=0.5, tails=2,
            allocation_ratio=ratio,
        )
        if (res["n1"], res["n2"]) != want:
            ok = False
            detail.append(f"P-09 R={ratio}: {res['n1']}/{res['n2']} != {want[0]}/{want[1]}")
    out.append(("F-09  even-total grid and observed split", ok, "; ".join(detail)))

    # F-08 (v1.2, observed): the sign is a direction
    ok, detail = True, []
    neg = cr.achieved_power("ttest-one-sample", alpha=0.05, effect_size=-0.5, tails=1, n=30)
    if abs(neg["power"] - 0.8482542) > POWER_TOL or not neg["critical_t"] < 0 or not neg["ncp"] < 0:
        ok = False
        detail.append(f"P-08-a: power={neg['power']:.7f} t={neg['critical_t']:.4f}")
    crit = cr.required_alpha("ttest-one-sample", power=0.8, effect_size=-0.5, tails=1, n=30)
    if not crit["critical_t"] > 0 or abs(crit["alpha"] - 0.0345321) > POWER_TOL:
        ok = False
        detail.append(f"N-01: alpha={crit['alpha']:.7f} t={crit['critical_t']:.4f}")
    out.append(("F-08  sign is a direction; criterion t stays positive", ok, "; ".join(detail)))

    # F-15 (observed): refuse what G*Power refuses, accept what it accepts
    ok, detail = True, []
    refusals = (
        ("r = 0.9999995", lambda: cr.achieved_power("ttest-point-biserial", alpha=0.05, effect_size=0.9999995, n=50)),
        ("r = -0.3", lambda: cr.achieved_power("ttest-point-biserial", alpha=0.05, effect_size=-0.3, n=50)),
        ("N = 2 post hoc", lambda: cr.achieved_power("ttest-one-sample", alpha=0.05, effect_size=0.5, n=2)),
        ("power < alpha", lambda: cr.required_sample_size("ttest-one-sample", alpha=0.05, power=0.04, effect_size=0.5)),
        ("q = 1e-4", lambda: cr.compromise("ttest-indep-means", effect_size=0.5, beta_alpha_ratio=1e-4, n1=40, n2=40)),
        ("a priori d = 9e-6", lambda: cr.required_sample_size("ttest-one-sample", alpha=0.05, power=0.8, effect_size=9e-6)),
        ("f2 = 50", lambda: cr.required_sample_size("ttest-regression-coef", alpha=0.05, power=0.8, effect_size=50, predictors=3)),
    )
    for label, call in refusals:
        try:
            call()
        except ValueError:
            continue
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail.append(f"{label}: raised {type(exc).__name__}, not ValueError")
            continue
        ok = False
        detail.append(f"{label}: accepted")
    for label, call, want_total in (
        ("matched pairs d = 20 -> N = 2", lambda: cr.required_sample_size("ttest-paired-means", alpha=0.05, power=0.8, effect_size=20), 2),
        ("q = 100 accepted", lambda: cr.compromise("ttest-indep-means", effect_size=0.5, beta_alpha_ratio=100, n1=40, n2=40), 80),
        ("n1 = 1, n2 = 2 accepted", lambda: cr.achieved_power("ttest-indep-means", alpha=0.05, effect_size=0.5, n1=1, n2=2), 3),
    ):
        try:
            got = call()["total"]
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail.append(f"{label}: refused ({exc})")
            continue
        if got != want_total:
            ok = False
            detail.append(f"{label}: total={got}")
    try:
        big = cr.required_sample_size("ttest-one-sample", alpha=0.05, power=0.95, effect_size=1e-4)
        if not 1_299_470_900 <= big["total"] <= 1_299_470_960:
            ok = False
            detail.append(f"d = 1e-4: N={big['total']}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        detail.append(f"d = 1e-4 refused: {exc}")
    out.append(("F-15  observed input domain", ok, "; ".join(detail)))

    # F-06 / F-12: minimal and sufficient, no epsilon slack
    ok, detail = True, []
    tight = cr.required_sample_size(
        "ttest-one-sample", alpha=0.05, power=0.80, effect_size=0.162, tails=2
    )
    if tight["total"] != 301:
        ok = False
        detail.append(f"tightest-margin case: N={tight['total']} (expected 301)")
    canon = cr.required_sample_size(
        "ttest-indep-means", alpha=0.05, power=0.95, effect_size=0.5, tails=2
    )
    if canon["total"] != 210 or abs(canon["power"] - 0.9501287) > POWER_TOL:
        ok = False
        detail.append(
            f"published example: N={canon['total']}, power={canon['power']:.7f}"
        )
    out.append(("F-06/F-12  minimality and recomputed power", ok, "; ".join(detail)))

    return out


def check_round_trips(cr) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    a = cr.required_sample_size(
        "ttest-indep-means", alpha=0.05, power=0.9, effect_size=0.5, tails=2
    )
    b = cr.achieved_power(
        "ttest-indep-means", alpha=0.05, effect_size=0.5, tails=2,
        n1=a["n1"], n2=a["n2"],
    )
    ok = abs(a["power"] - b["power"]) < 1e-10
    out.append(("a priori -> post hoc", ok,
                "" if ok else f"{a['power']:.12f} vs {b['power']:.12f}"))

    c = cr.required_alpha(
        "ttest-one-sample", power=0.85, effect_size=0.5, tails=2, n=50
    )
    d = cr.achieved_power(
        "ttest-one-sample", alpha=c["alpha"], effect_size=0.5, tails=2, n=50
    )
    ok = abs(d["power"] - 0.85) < 1e-8
    out.append(("criterion -> post hoc", ok,
                "" if ok else f"power {d['power']:.10f} != 0.85"))

    e = cr.detectable_effect_size(
        "ttest-one-sample", alpha=0.05, power=0.85, tails=2, n=50
    )
    f = cr.achieved_power(
        "ttest-one-sample", alpha=0.05, effect_size=e["effect_size"], tails=2, n=50
    )
    ok = abs(f["power"] - 0.85) < 1e-8
    out.append(("sensitivity -> post hoc", ok,
                "" if ok else f"power {f['power']:.10f} != 0.85"))

    detail = []
    ok = True
    for q in (0.5, 1.0, 2.0, 4.0):
        g = cr.compromise(
            "ttest-indep-means", effect_size=0.5, beta_alpha_ratio=q, tails=2,
            n1=40, n2=40,
        )
        if abs(g["beta"] / g["alpha"] - q) > 1e-6:
            ok = False
            detail.append(f"q={q}: ratio {g['beta'] / g['alpha']:.8f}")
        if abs(g["power"] - (1.0 - g["beta"])) > 1e-12:
            ok = False
            detail.append(f"q={q}: power != 1-beta")
    out.append(("compromise satisfies beta/alpha = q", ok, "; ".join(detail)))

    return out


def check_gpower_observations(cr) -> dict:
    """The clean room against the real program: every recorded a-priori
    G*Power reading with N <= 1e7 (above that, F-14), exact N."""
    sys.path.insert(0, str(ROOT / "tools"))
    from rea_report import load_observations  # noqa: PLC0415

    keymap = {"indep": "ttest-indep-means", "paired": "ttest-paired-means",
              "one-sample": "ttest-one-sample", "point-biserial": "ttest-point-biserial",
              "regression": "ttest-regression-coef"}
    rows = same = 0
    diffs = []
    for rec in load_observations():
        c, out = rec["case"], rec["gui"]["outputs"]
        if rec["gui"].get("dialog"):
            continue  # refused: the output panel still shows the previous run
        if c["analysis"] != "a priori" or "Total sample size" not in out:
            continue
        if int(out["Total sample size"]) > 10_000_000:
            continue
        kw = dict(alpha=c["alpha"], power=c["power"], effect_size=c["es"],
                  tails=c.get("tails", 2))
        if "ratio" in c:
            kw["allocation_ratio"] = float(c["ratio"])
        if "predictors" in c:
            kw["predictors"] = c["predictors"]
        rows += 1
        try:
            got = cr.required_sample_size(keymap[c["test"]], **kw)["total"]
        except Exception as exc:  # noqa: BLE001
            diffs.append(f"{rec['id']}: raised {exc}")
            continue
        if got == int(out["Total sample size"]):
            same += 1
        else:
            diffs.append(f"{rec['id']}: {got} vs G*Power {out['Total sample size']}")
    return {"rows": rows, "same": same, "diffs": diffs}


def check_divergence_against_shipped(cr) -> dict:
    """Where do the two implementations differ, across a wide grid?"""
    grid = []
    for test, es, extra in (
        ("ttest-indep-means", 0.45, {}),
        ("ttest-one-sample", 0.37, {}),
        ("ttest-paired-means", 0.52, {}),
        ("ttest-point-biserial", 0.27, {}),
        ("ttest-regression-coef", 0.11, {"predictors": 7}),
    ):
        for alpha in (0.001, 0.01, 0.05, 0.10, 0.20):
            for pw in (0.70, 0.80, 0.85, 0.90, 0.95, 0.99):
                for tails in (1, 2):
                    grid.append((test, es, alpha, pw, tails, extra))

    same = 0
    diffs: list[str] = []
    for test, es, alpha, pw, tails, extra in grid:
        mine = solve(
            test, "n", alpha=alpha, power_target=pw, effect_size=es, tails=tails,
            extra=extra or None,
        ).sample_size["total"]
        kw = dict(alpha=alpha, power=pw, effect_size=es, tails=tails)
        kw.update(extra)
        try:
            theirs = cr.required_sample_size(test, **kw)["total"]
        except Exception as exc:  # noqa: BLE001
            diffs.append(f"{test} a={alpha} p={pw} t={tails}: {type(exc).__name__}")
            continue
        if mine == theirs:
            same += 1
        else:
            diffs.append(
                f"{test} alpha={alpha} power={pw} tails={tails}: "
                f"shipped {mine} vs cleanroom {theirs}"
            )
    return {"cases": len(grid), "same": same, "diffs": diffs}


# --------------------------------------------------------------------------
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def similarity() -> dict:
    """Lexical overlap between the two implementations.

    A clean-room implementation should share the *vocabulary of the domain*
    (alpha, power, noncentrality) and little else.  Shared private helper
    names or shared comment phrasing would be a red flag.
    """

    def tokens(path: Path) -> Counter:
        c: Counter = Counter()
        for f in sorted(path.rglob("*.py")):
            c.update(_IDENT.findall(f.read_text(encoding="utf-8")))
        return c

    def comments(path: Path) -> set[str]:
        out = set()
        for f in sorted(path.rglob("*.py")):
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("#") and len(s) > 25:
                    out.add(s.lstrip("# ").rstrip())
        return out

    if not (CLEANROOM_SRC / "gpower_cleanroom").is_dir():
        return {}
    a = tokens(SHIPPED_SRC)
    b = tokens(CLEANROOM_SRC / "gpower_cleanroom")
    shared = set(a) & set(b)
    jaccard = len(shared) / max(1, len(set(a) | set(b)))

    def _is_meaningful_private(name: str) -> bool:
        """A private helper name, excluding language and lexer artefacts.

        `__all__`, `__future__` and friends are language, not authorship, and
        `_000_000` is what the identifier regex makes of `10_000_000`.
        """
        if not name.startswith("_") or name.startswith("__"):
            return False
        if name.lstrip("_").replace("_", "").isdigit():
            return False
        return len(name) > 5

    private_shared = sorted(t for t in shared if _is_meaningful_private(t))

    # Shared private names whose *concept* the handover artefacts do not name.
    # SPEC.md and INTERFACE.md were legitimately visible to Session B, so a
    # name built from words they use (`round_half_up`, `allocation_ratio`,
    # `Stirling`) is expected to recur and says nothing about authorship.
    handover = ""
    for doc in (ROOT / "SPEC.md", CLEANROOM_SRC.parent / "INTERFACE.md"):
        if doc.is_file():
            handover += doc.read_text(encoding="utf-8").lower()

    def _explained(name: str) -> bool:
        parts = [p for p in name.lower().strip("_").split("_") if len(p) > 2]
        return bool(parts) and all(p in handover for p in parts)

    unexplained = sorted(
        t for t in shared if _is_meaningful_private(t) and not _explained(t)
    )

    shared_comments = sorted(
        comments(SHIPPED_SRC) & comments(CLEANROOM_SRC / "gpower_cleanroom")
    )
    return {
        "shipped_identifiers": len(a),
        "cleanroom_identifiers": len(b),
        "shared": len(shared),
        "jaccard": jaccard,
        "shared_private_helpers": private_shared,
        "unexplained_by_handover": unexplained,
        "identical_comment_lines": shared_comments,
    }


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--markdown", action="store_true", help="markdown report")
    ap.add_argument("--strict", action="store_true", help="exit 1 on divergence")
    ap.add_argument("--similarity", action="store_true", help="only the overlap report")
    args = ap.parse_args()

    cr, why = load_cleanroom()
    if cr is None:
        print(f"clean-room implementation not available: {why}")
        print("See docs/CLEANROOM-PROTOCOL.md section 6.")
        return 2

    if args.similarity:
        sim = similarity()
        for k, v in sim.items():
            print(f"{k}: {v}")
        return 0

    vec = check_vectors(cr)
    ids = check_identities(cr)
    rts = check_round_trips(cr)
    div = check_divergence_against_shipped(cr)
    obs = check_gpower_observations(cr)
    sim = similarity()

    rate = vec["exact_n"] / max(1, vec["rows"])
    all_ok = (
        vec["exact_n"] == vec["rows"]
        and all(ok for _, ok, _ in ids)
        and all(ok for _, ok, _ in rts)
        and div["same"] == div["cases"]
        and obs["same"] == obs["rows"]
    )

    if args.markdown:
        print("### Clean-room conformance (Session B)")
        print()
        print(f"- conformance vectors: **{vec['exact_n']}/{vec['rows']}** exact "
              f"integer `N` (rate {rate:.4f}); "
              f"{vec['power_within_tol']}/{vec['rows']} powers within 5e-7")
        print(f"- cross-implementation grid: **{div['same']}/{div['cases']}** "
              f"identical required `N`")
        print(f"- **against the real G\\*Power 3.1.9.6**: **{obs['same']}/{obs['rows']}** "
              f"recorded a-priori results reproduced exactly")
        print()
        print("| property | result |")
        print("|---|---|")
        for label, ok, detail in ids + rts:
            print(f"| {label} | {'PASS' if ok else 'FAIL — ' + detail} |")
        if sim:
            print()
            print(f"- lexical overlap with the shipped engine: Jaccard "
                  f"**{sim['jaccard']:.3f}** "
                  f"({sim['shared']} shared identifiers of "
                  f"{sim['shipped_identifiers']}/{sim['cleanroom_identifiers']})")
            print(f"- shared private helper names: "
                  f"{sim['shared_private_helpers'] or 'none'}")
            print(f"- identical comment lines: "
                  f"{len(sim['identical_comment_lines'])}")
        if vec["errors"]:
            print()
            print("<details><summary>divergences</summary>")
            print()
            for e in vec["errors"][:40]:
                print(f"- {e}")
            print()
            print("</details>")
        return 0 if (all_ok or not args.strict) else 1

    print("=" * 72)
    print("CLEAN-ROOM CONFORMANCE REPORT")
    print("=" * 72)
    print(f"conformance vectors : {vec['exact_n']}/{vec['rows']} exact N "
          f"(rate {rate:.4f})")
    print(f"power within 5e-7   : {vec['power_within_tol']}/{vec['rows']}")
    print(f"per test            :")
    for t, (ok, tot) in vec["per_test"].items():
        print(f"    {t:<26} {ok}/{tot}")
    print()
    print("SPEC properties")
    for label, ok, detail in ids:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if detail:
            print(f"         {detail}")
    print()
    print("Analysis-type round trips")
    for label, ok, detail in rts:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if detail:
            print(f"         {detail}")
    print()
    print(f"Against G*Power 3.1.9.6 : {obs['same']}/{obs['rows']} recorded a-priori N exact")
    for d in obs["diffs"][:20]:
        print(f"    {d}")
    print(f"Cross-implementation grid: {div['same']}/{div['cases']} identical")
    for d in div["diffs"][:20]:
        print(f"    {d}")
    if sim:
        print()
        print("Independence check (lexical overlap with the shipped engine)")
        print(f"  Jaccard                  : {sim['jaccard']:.3f}")
        print(f"  shared identifiers       : {sim['shared']} "
              f"(of {sim['shipped_identifiers']} / {sim['cleanroom_identifiers']})")
        print(f"  shared private helpers   : {sim['shared_private_helpers'] or 'none'}")
        print(f"  not named in the handover: "
              f"{sim['unexplained_by_handover'] or 'none'}")
        print(f"  identical comment lines  : {len(sim['identical_comment_lines'])}")
    if vec["errors"]:
        print()
        print(f"Divergences ({len(vec['errors'])}):")
        for e in vec["errors"][:40]:
            print(f"  - {e}")
    print()
    print("VERDICT:", "CONFORMING" if all_ok else "DIVERGENT")
    return 0 if (all_ok or not args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
