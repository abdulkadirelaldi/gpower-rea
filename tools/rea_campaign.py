#!/usr/bin/env python
"""Run an observation campaign against a live G*Power GUI.

    python tools/rea_campaign.py --set probes      # the pre-registered probe rows
    python tools/rea_campaign.py --set grid        # seeded random conformance grid
    python tools/rea_campaign.py --set all

Each case is run twice: once through the G*Power GUI (``tools/gpower_ax.py``,
black-box, Accessibility API) and once through ``gpower_rea.engine.solve``.
Every printed output field is compared at the GUI's own printed precision.
One JSON object per case is appended to
``probes/observations/gpower-<version>-<platform>.jsonl``; that file is the
raw ``[GÖZLEM]`` evidence and is never edited by hand.

The file holds only numbers read off the GUI's output panel — no binary,
no code, no screenshots of protected material.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import gpower_ax  # noqa: E402
from gpower_rea import solve  # noqa: E402
from gpower_rea.engine import ValidationError  # noqa: E402

OBS_DIR = ROOT / "probes" / "observations"
GPOWER_VERSION = "3.1.9.6"

ENGINE_TEST = {
    "indep": "indep", "paired": "paired", "one-sample": "one-sample",
    "point-biserial": "point-biserial", "regression": "regression-coef",
    "generic": "generic",
}
ENGINE_MODE = {"a priori": "n", "post hoc": "power", "criterion": "alpha",
               "sensitivity": "effect-size", "compromise": "compromise"}


# --------------------------------------------------------------------------
# case → GUI settings


def gui_settings(c: dict) -> list[tuple[str, str]]:
    s: list[tuple[str, str]] = [("Tail(s)", "Two" if c.get("tails", 2) == 2 else "One")]
    if c["test"] == "generic":
        s.append(("Df", _num(c["df"])))
        if "es" in c:
            s.append(("Noncentrality parameter δ", _num(c["es"])))
    else:
        if "es" in c:
            s.append(("Effect size", _num(c["es"])))
    if "predictors" in c:
        s.append(("Number of predictors", str(c["predictors"])))
    if "alpha" in c:
        s.append(("α err prob", _num(c["alpha"])))
    if "power" in c:
        s.append(("Power (1-β err prob)", _num(c["power"])))
    if "ratio" in c:
        s.append(("Allocation ratio", _num(c["ratio"])))
    if "n" in c:
        s.append(("Total sample size", str(c["n"])))
    if "n1" in c:
        s.append(("Sample size group 1", str(c["n1"])))
        s.append(("Sample size group 2", str(c["n2"])))
    if "q" in c:
        s.append(("β/α ratio", _num(c["q"])))
    return s


def _num(x) -> str:
    return repr(float(x)).rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


# --------------------------------------------------------------------------
# case → engine


def engine_result(c: dict, rule: str | None = None) -> dict:
    extra = {}
    if "predictors" in c:
        extra["predictors"] = c["predictors"]
    if "df" in c:
        extra["df"] = c["df"]
    r = solve(
        ENGINE_TEST[c["test"]], ENGINE_MODE[c["analysis"]],
        alpha=c.get("alpha"), power_target=c.get("power"),
        effect_size=c.get("es"), tails=c.get("tails", 2),
        n=c.get("n"), n1=c.get("n1"), n2=c.get("n2"),
        allocation_ratio=c.get("ratio"), allocation_rule=rule,
        beta_alpha_ratio=c.get("q"), extra=extra or None,
    )
    return r.as_dict()


def engine_fields(d: dict) -> dict[str, float]:
    ss = d.get("sample_size") or {}
    out = {
        "Noncentrality parameter δ": d.get("noncentrality"),
        "Critical t": d.get("critical_t"),
        "Df": d.get("df"),
        "Total sample size": ss.get("total"),
        "Sample size group 1": ss.get("n1"),
        "Sample size group 2": ss.get("n2"),
        "Actual power": d.get("power"),
        "Power (1-β err prob)": d.get("power"),
        "α err prob": d.get("alpha"),
        "β err prob": (1 - d["power"]) if d.get("power") is not None else None,
    }
    es = (d.get("effect_size") or {}).get("value")
    out["Effect size"] = es
    return {k: v for k, v in out.items() if v is not None}


def _canon(shown: str) -> str:
    """G*Power trims trailing zeros of a mantissa (1.32816e-12)."""
    if "e" in shown:
        m, x = shown.split("e")
        m = m.rstrip("0").rstrip(".") if "." in m else m
        return f"{m}e{int(x):+03d}"
    return shown


def _as_printed(value: float, shown: str) -> str:
    """Format ``value`` the way G*Power printed ``shown``."""
    if "e" in shown:
        digits = len(shown.split("e")[0].replace("-", "").replace(".", "")) - 1
        return _canon(f"{value:.{max(digits, 6)}e}") if digits < 6 else _canon(f"{value:.{digits}e}")
    if "." in shown:
        return f"{value:.{len(shown.split('.')[1])}f}"
    return str(int(round(value)))


def compare(gui_out: dict[str, str], eng: dict[str, float]) -> dict:
    fields = {}
    for label, shown in gui_out.items():
        key = "Effect size" if label.startswith("Effect size") else label
        if key not in eng:
            continue
        try:
            g = float(shown)
        except ValueError:
            continue
        e = eng[key]
        fields[label] = {"gui": shown, "engine": _as_printed(e, shown),
                         "abs_diff": abs(g - e)}
        fields[label]["printed_match"] = fields[label]["engine"] == _canon(shown)
    return fields


# --------------------------------------------------------------------------
# case sets


def probe_cases() -> list[dict]:
    """The pre-registered rows of probes/probe_worksheet.csv, as structured cases."""
    C = []

    def add(pid, **kw):
        C.append({"id": pid, **kw})

    add("P-01-a", test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.95, ratio=1)
    add("P-02-a", test="generic", analysis="post hoc", es=0, df=30, alpha=0.2)
    add("P-02-b", test="generic", analysis="post hoc", es=0, df=30, alpha=0.05)
    add("P-02-c", test="generic", analysis="post hoc", es=0, df=5, alpha=0.2)
    add("P-02-d", test="generic", analysis="post hoc", es=0, df=30, alpha=0.2, tails=1)
    add("P-03-a", test="paired", analysis="a priori", es=0.5, alpha=0.05, power=0.95)
    add("P-03-b", test="one-sample", analysis="a priori", es=0.5, alpha=0.05, power=0.95)
    add("P-04-a", test="point-biserial", analysis="post hoc", es=0.5, alpha=0.05, n=20)
    add("P-04-b", test="point-biserial", analysis="post hoc", es=0.6, alpha=0.05, n=10)
    add("P-04-c", test="point-biserial", analysis="post hoc", es=0.3, alpha=0.05, n=12)
    add("P-04-d", test="point-biserial", analysis="a priori", es=0.5, alpha=0.05, power=0.8)
    add("P-04-e", test="point-biserial", analysis="a priori", es=0.7, alpha=0.05, power=0.8)
    add("P-05-a", test="indep", analysis="a priori", es=0.3, alpha=0.05, power=0.8, ratio=1)
    add("P-05-b", test="indep", analysis="a priori", es=0.42, alpha=0.05, power=0.9, ratio=1)
    add("P-05-c", test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.95, ratio=1)
    add("P-05-d", test="indep", analysis="a priori", es=0.62, alpha=0.05, power=0.85, ratio=1)
    add("P-06-a", test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.95, ratio=1)
    add("P-06-b", test="one-sample", analysis="a priori", es=0.162, alpha=0.05, power=0.8)
    add("P-07-a", test="regression", analysis="post hoc", es=0.15, alpha=0.05, n=100, predictors=1)
    add("P-07-b", test="regression", analysis="post hoc", es=0.15, alpha=0.05, n=100, predictors=5)
    add("P-07-c", test="regression", analysis="a priori", es=0.15, alpha=0.05, power=0.8, predictors=1)
    add("P-07-d", test="regression", analysis="a priori", es=0.15, alpha=0.05, power=0.8, predictors=5)
    add("P-08-a", test="one-sample", analysis="post hoc", es=-0.5, alpha=0.05, n=30, tails=1)
    add("P-08-b", test="one-sample", analysis="post hoc", es=-0.5, alpha=0.05, n=30)
    add("P-08-c", test="one-sample", analysis="a priori", es=-0.5, alpha=0.05, power=0.8, tails=1)
    for pid, r in (("P-09-a", 0.5), ("P-09-b", 1.5), ("P-09-c", 2.0), ("P-09-d", 3.0)):
        add(pid, test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.95, ratio=r)
    for pid, q in (("P-10-a", 1.0), ("P-10-b", 2.0), ("P-10-c", 4.0)):
        add(pid, test="indep", analysis="compromise", es=0.5, n1=40, n2=40, q=q)
    add("P-12-a", test="one-sample", analysis="a priori", es=0.162, alpha=0.05, power=0.8)
    return C


def alloc_cases() -> list[dict]:
    """An allocation-ratio sweep for F-09: the one finding that needs many
    observations because its candidates differ by only one participant."""
    C = []
    i = 0
    for d in (0.3, 0.5, 0.8):
        for pw in (0.8, 0.95):
            for r in (0.3, 0.5, 1.25, 1.5, 2, 2.5, 3, 4):
                C.append({"id": f"A-{i:03d}", "test": "indep", "analysis": "a priori",
                          "es": d, "alpha": 0.05, "power": pw, "ratio": r})
                i += 1
    return C


def sweep_cases() -> list[dict]:
    """A fine power sweep at one unbalanced design.  The staircase of N(power)
    exposes the stopping test itself: every total in it is even (F-09)."""
    return [{"id": f"S-{i:03d}", "test": "indep", "analysis": "a priori",
             "es": 0.5, "alpha": 0.05, "power": round(0.940 + i * 0.0005, 4),
             "ratio": 1.5} for i in range(41)]


def sign_cases() -> list[dict]:
    """Negative effect sizes across tests and analyses (F-08)."""
    return [
        {"id": "N-01", "test": "one-sample", "analysis": "criterion", "es": -0.5, "power": 0.8, "n": 30, "tails": 1},
        {"id": "N-02", "test": "one-sample", "analysis": "criterion", "es": -0.5, "power": 0.8, "n": 30, "tails": 2},
        {"id": "N-03", "test": "indep", "analysis": "compromise", "es": -0.5, "n1": 40, "n2": 40, "q": 1, "tails": 1},
        {"id": "N-04", "test": "indep", "analysis": "compromise", "es": -0.5, "n1": 40, "n2": 40, "q": 2, "tails": 2},
        {"id": "N-05", "test": "generic", "analysis": "post hoc", "es": -2.5, "df": 30, "alpha": 0.05, "tails": 1},
        {"id": "N-06", "test": "generic", "analysis": "post hoc", "es": -2.5, "df": 30, "alpha": 0.05, "tails": 2},
        {"id": "N-07", "test": "point-biserial", "analysis": "post hoc", "es": -0.3, "n": 50, "alpha": 0.05, "tails": 1},
        {"id": "N-08", "test": "paired", "analysis": "post hoc", "es": -0.4, "n": 40, "alpha": 0.05, "tails": 1},
        {"id": "N-09", "test": "indep", "analysis": "post hoc", "es": -0.5, "n1": 30, "n2": 30, "alpha": 0.05, "tails": 1},
        {"id": "N-10", "test": "indep", "analysis": "a priori", "es": -0.5, "alpha": 0.05, "power": 0.8, "ratio": 2, "tails": 1},
        {"id": "N-11", "test": "one-sample", "analysis": "post hoc", "es": 0, "n": 30, "alpha": 0.05, "tails": 2},
        {"id": "N-12", "test": "generic", "analysis": "criterion", "es": -2.5, "df": 30, "power": 0.8, "tails": 1},
    ]


def domain_cases() -> list[dict]:
    """Edges of the input domain (F-15): what G*Power accepts, refuses, and
    what it prints at the boundary."""
    D = [
        dict(test="point-biserial", analysis="post hoc", es=0.999999, n=50, alpha=0.05),
        dict(test="point-biserial", analysis="post hoc", es=0.9999995, n=50, alpha=0.05),
        dict(test="point-biserial", analysis="post hoc", es=1, n=50, alpha=0.05),
        dict(test="point-biserial", analysis="post hoc", es=-0.3, n=50, alpha=0.05, tails=1),
        dict(test="one-sample", analysis="a priori", es=0, alpha=0.05, power=0.8),
        dict(test="indep", analysis="post hoc", es=0, n1=20, n2=20, alpha=0.05),
        dict(test="one-sample", analysis="post hoc", es=0.3, n=30, alpha=0.75, tails=1),
        dict(test="one-sample", analysis="post hoc", es=0.5, n=2, alpha=0.05),
        dict(test="one-sample", analysis="post hoc", es=0.5, n=1, alpha=0.05),
        dict(test="generic", analysis="post hoc", es=1, df=0.5, alpha=0.05),
        dict(test="regression", analysis="post hoc", es=0, n=50, predictors=1, alpha=0.05),
        dict(test="regression", analysis="a priori", es=0, predictors=1, alpha=0.05, power=0.8),
        dict(test="one-sample", analysis="a priori", es=0.5, alpha=0.05, power=0.04),
        dict(test="indep", analysis="a priori", es=0.8, alpha=0.05, power=0.8, ratio=0.05),
        dict(test="indep", analysis="a priori", es=0.8, alpha=0.05, power=0.8, ratio=20),
        dict(test="regression", analysis="post hoc", es=0.15, n=6, predictors=5, alpha=0.05),
        dict(test="indep", analysis="post hoc", es=0.5, n1=1, n2=1, alpha=0.05),
        dict(test="one-sample", analysis="a priori", es=0.1, alpha=0.05, power=0.999),
        dict(test="indep", analysis="compromise", es=0.5, n1=40, n2=40, q=0.0001),
        dict(test="one-sample", analysis="sensitivity", n=30, alpha=0.05, power=0.04),
        dict(test="paired", analysis="a priori", es=5, alpha=0.05, power=0.8),
        dict(test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.8, ratio=1.5, tails=1),
        dict(test="paired", analysis="a priori", es=20, alpha=0.05, power=0.8),
        dict(test="indep", analysis="post hoc", es=0.5, n1=1, n2=2, alpha=0.05),
        dict(test="point-biserial", analysis="post hoc", es=0.5, n=3, alpha=0.05),
        dict(test="point-biserial", analysis="post hoc", es=0.5, n=4, alpha=0.05),
        dict(test="indep", analysis="a priori", es=20, alpha=0.05, power=0.8),
        dict(test="indep", analysis="a priori", es=20, alpha=0.05, power=0.8, ratio=3),
        dict(test="point-biserial", analysis="a priori", es=0.99, alpha=0.05, power=0.8),
        dict(test="regression", analysis="a priori", es=50, predictors=3, alpha=0.05, power=0.8),
        dict(test="one-sample", analysis="a priori", es=0.00001, alpha=0.05, power=0.8),
        dict(test="one-sample", analysis="a priori", es=0.5, alpha=0.05, power=0.05),
        dict(test="indep", analysis="compromise", es=0.5, n1=40, n2=40, q=0.01),
        dict(test="indep", analysis="compromise", es=0.5, n1=40, n2=40, q=100),
        dict(test="one-sample", analysis="criterion", es=0.000001, n=30, power=0.8),
        dict(test="one-sample", analysis="post hoc", es=0.5, n=30, alpha=0.9999),
        dict(test="regression", analysis="post hoc", es=-0.15, n=50, predictors=1, alpha=0.05),
        dict(test="regression", analysis="post hoc", es=-0.15, n=50, predictors=1, alpha=0.05, tails=1),
        dict(test="regression", analysis="post hoc", es=19.99, n=10, predictors=1, alpha=0.05),
        dict(test="one-sample", analysis="a priori", es=0.000009, alpha=0.05, power=0.8),
        dict(test="paired", analysis="post hoc", es=0.5, n=2, alpha=0.05),
        dict(test="regression", analysis="a priori", es=-0.15, predictors=1, alpha=0.05, power=0.8),
        dict(test="one-sample", analysis="a priori", es=0.0001, alpha=0.05, power=0.95),
        dict(test="indep", analysis="a priori", es=0.001, alpha=0.05, power=0.8, ratio=2),
        dict(test="point-biserial", analysis="sensitivity", n=50, alpha=0.05, power=0.8),
        dict(test="regression", analysis="sensitivity", n=50, predictors=2, alpha=0.05, power=0.8),
    ]
    return [{"id": f"D-{i + 1:02d}", "tails": 2, **c} for i, c in enumerate(D)]


def gap_cases() -> list[dict]:
    """The points the second clean-room session reported SPEC v1.2 left open
    (cleanroom/SPEC-GAPS-v1.2.md), put to G*Power instead of decided."""
    X = [
        ("G2-04", dict(test="indep", analysis="a priori", es=8, alpha=0.05, power=0.8, ratio=3)),
        ("G2-14", dict(test="indep", analysis="a priori", es=1.11, alpha=0.05, power=0.8, ratio=7.8)),
        ("G2-06", dict(test="point-biserial", analysis="post hoc", es=0, n=10, alpha=0.05)),
        ("G2-11a", dict(test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.8, ratio=0.001)),
        ("G2-11b", dict(test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.8, ratio=1000)),
        ("G2-11c", dict(test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.8, ratio=0.01)),
        ("G2-11d", dict(test="indep", analysis="a priori", es=0.5, alpha=0.05, power=0.8, ratio=100)),
        ("G2-17", dict(test="regression", analysis="post hoc", es=0.15, n=20, predictors=0, alpha=0.05)),
        ("G2-08a", dict(test="point-biserial", analysis="a priori", es=0.000005, alpha=0.05, power=0.8)),
        ("G2-08b", dict(test="regression", analysis="a priori", es=0.000005, predictors=1, alpha=0.05, power=0.8)),
        ("G2-02", dict(test="indep", analysis="post hoc", es=0.5, n1=0, n2=3, alpha=0.05)),
        ("G2-07", dict(test="regression", analysis="sensitivity", n=4, predictors=2, alpha=0.001, power=0.99)),
        ("G3-01a", dict(test="indep", analysis="a priori", es=20, alpha=0.05, power=0.8, ratio=100)),
        ("G3-01b", dict(test="indep", analysis="a priori", es=20, alpha=0.05, power=0.8, ratio=0.01)),
        ("G3-03", dict(test="point-biserial", analysis="a priori", es=0, alpha=0.05, power=0.8)),
    ]
    return [{"id": f"X-{gid}", "tails": 2, **c} for gid, c in X]


def agent_eval_cases() -> list[dict]:
    """The numeric questions of agent/eval/questions.json, so their expected
    answers are G*Power's, not the engine's."""
    import json as _json
    qs = _json.loads((ROOT / "agent" / "eval" / "questions.json").read_text(encoding="utf-8"))
    C = []
    for q in qs:
        p = q["expected_parameters"]
        if q["expected_family"] == "t2-indep":
            c = {"test": "indep", "es": p["d"], "alpha": p["alpha"], "tails": p["tails"]}
            if "power" in p:
                c.update(analysis="a priori", power=p["power"], ratio=p["ratio"])
            else:
                c.update(analysis="post hoc", n1=p["n1"], n2=p["n2"])
        elif q["expected_family"] == "t-paired":
            c = {"test": "paired", "es": p["dz"], "alpha": p["alpha"], "tails": p["tails"]}
            if "power" in p:
                c.update(analysis="a priori", power=p["power"])
            else:
                c.update(analysis="post hoc", n=p["n"])
        else:
            continue
        C.append({"id": f"E-{q['id']}", **c})
    return C


def grid_cases(n: int = 240, seed: int = 20261026) -> list[dict]:
    """A seeded random conformance grid, weighted towards a priori (N)."""
    rnd = random.Random(seed)
    tests = ["indep", "paired", "one-sample", "point-biserial", "regression", "generic"]
    C = []
    for i in range(n):
        t = tests[i % len(tests)]
        analyses = ["a priori"] * 4 + ["post hoc", "criterion", "sensitivity", "compromise"]
        if t == "generic":
            analyses = ["post hoc", "criterion", "sensitivity", "compromise"]
        a = rnd.choice(analyses)
        c: dict = {"id": f"G-{i:03d}", "test": t, "analysis": a,
                   "tails": rnd.choice([1, 2, 2])}
        alpha = rnd.choice([0.01, 0.025, 0.05, 0.05, 0.1])
        power = rnd.choice([0.8, 0.8, 0.85, 0.9, 0.95, 0.99])
        if t == "point-biserial":
            es = round(rnd.uniform(0.1, 0.7), 2)
        elif t == "regression":
            es = round(rnd.uniform(0.02, 0.4), 3)
            c["predictors"] = rnd.randint(1, 10)
        elif t == "generic":
            es = round(rnd.uniform(0.5, 4.0), 2)
            c["df"] = rnd.randint(5, 120)
        else:
            es = round(rnd.uniform(0.15, 1.2), 2)
        if a == "a priori":
            c.update(es=es, alpha=alpha, power=power)
            if t == "indep":
                c["ratio"] = rnd.choice([1, 1, 1, 0.5, 1.5, 2, 2.5, 3, 0.75, 1.25])
        else:
            if t == "indep":
                c["n1"] = rnd.randint(8, 150)
                c["n2"] = rnd.choice([c["n1"], rnd.randint(8, 150)])
            elif t != "generic":
                lo = (c.get("predictors", 0) + 3) if t == "regression" else 6
                c["n"] = rnd.randint(lo, 250)
            if a == "post hoc":
                c.update(es=es, alpha=alpha)
            elif a == "criterion":
                c.update(es=es, power=power)
            elif a == "sensitivity":
                c.update(alpha=alpha, power=power)
            elif a == "compromise":
                c.update(es=es, q=rnd.choice([0.5, 1, 2, 4]))
        C.append(c)
    return C


# --------------------------------------------------------------------------


def echo_mismatch(settings: list[tuple[str, str]], echoed: dict[str, str]) -> list:
    """Inputs the GUI did not take. The GUI echoes its input panel back, so a
    keystroke that was swallowed is detected rather than silently recorded."""
    bad = []
    for label, want in settings:
        got = [v for k, v in echoed.items() if k.startswith(label)]
        if not got:
            bad.append((label, want, None))
            continue
        try:
            if abs(float(got[0]) - float(want.replace(",", "."))) > 1e-12:
                bad.append((label, want, got[0]))
        except ValueError:
            if got[0] != want:
                bad.append((label, want, got[0]))
    return bad


def run_case(c: dict) -> dict:
    rec = {"id": c["id"], "case": c, "observed_at": dt.datetime.now().isoformat(timespec="seconds")}
    settings = gui_settings(c)
    try:
        for _attempt in range(3):
            gui = gpower_ax.run(c["test"], c["analysis"], settings)
            bad = echo_mismatch(settings, gui["inputs"])
            if not bad:
                break
        rec["gui"] = gui
        if bad:
            rec["gui_error"] = f"input echo mismatch after 3 attempts: {bad}"
            return rec
    except Exception as e:  # noqa: BLE001 — record, don't stop the campaign
        rec["gui_error"] = str(e)[:400]
        return rec
    rules = [None]
    if c["test"] == "indep" and c["analysis"] == "a priori" and c.get("ratio", 1) != 1:
        rules = ["n1-grid", "total-grid"]
    rec["engine"] = {}
    for rule in rules:
        try:
            d = engine_result(c, rule)
            rec["engine"][rule or "default"] = {
                "result": d, "fields": compare(gui["outputs"], engine_fields(d))}
        except Exception as e:  # noqa: BLE001 — engine is re-evaluated by rea_report.py
            rec["engine"][rule or "default"] = {"error": str(e)}
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["none", "probes", "alloc", "sweep", "sign", "domain", "gaps", "eval", "grid", "all"], default="all")
    ap.add_argument("--grid-size", type=int, default=240)
    ap.add_argument("--only", nargs="*", help="case ids to (re)run")
    ap.add_argument("--cases", type=Path, help="JSON list of extra cases")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    cases = []
    if a.set == "none":
        pass
    if a.set in ("probes", "all"):
        cases += probe_cases()
    if a.set in ("alloc", "all"):
        cases += alloc_cases()
    if a.set in ("sweep", "all"):
        cases += sweep_cases()
    if a.set in ("sign", "all"):
        cases += sign_cases()
    if a.set in ("domain", "all"):
        cases += domain_cases()
    if a.set in ("gaps", "all"):
        cases += gap_cases()
    if a.set in ("eval", "all"):
        cases += agent_eval_cases()
    if a.set in ("grid", "all"):
        cases += grid_cases(a.grid_size)
    if a.cases:
        cases += json.loads(a.cases.read_text(encoding="utf-8"))
    if a.only:
        cases = [c for c in cases if c["id"] in set(a.only)]
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    out = a.out or OBS_DIR / f"gpower-{GPOWER_VERSION}-macos.jsonl"
    meta = {"gpower_version": GPOWER_VERSION, "platform": platform.platform(),
            "instrument": "tools/gpower_ax.py (macOS Accessibility, black box)"}
    with out.open("a", encoding="utf-8") as fh:
        for i, c in enumerate(cases, 1):
            rec = run_case(c)
            rec["meta"] = meta
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            status = "GUI-ERR" if "gui_error" in rec else (
                "DIALOG" if rec["gui"].get("dialog") else "ok")
            print(f"[{i}/{len(cases)}] {c['id']} {status}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
