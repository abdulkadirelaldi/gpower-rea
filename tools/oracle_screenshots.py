#!/usr/bin/env python
"""Screenshot evidence for the oracle: re-run vectors in G*Power and capture.

    python tools/oracle_screenshots.py              # the default 32 vectors
    python tools/oracle_screenshots.py --ids P-01-a A-022

For each vector of ``oracle/gpower_t2_indep.csv`` this re-enters the inputs
in the running G*Power GUI (tools/gpower_ax.py), presses Calculate, saves a
screenshot of the G*Power window to ``oracle/screenshots/<id>.png``, and
checks that what the GUI prints now is what the CSV recorded.  A mismatch is
reported, never silently overwritten.

Needs macOS Accessibility *and* Screen Recording permission for the terminal
(System Settings -> Privacy & Security); the latter takes effect only after
the terminal app is restarted.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gpower_ax  # noqa: E402
from rea_campaign import gui_settings  # noqa: E402

CSV = ROOT / "oracle" / "gpower_t2_indep.csv"
SHOTS = ROOT / "oracle" / "screenshots"

DEFAULT = [
    "P-01-a", "P-05-a", "P-05-b", "P-05-c", "P-05-d", "P-09-a", "P-09-b", "P-09-c",
    "P-09-d", "P-10-a", "A-002", "A-007", "A-016", "A-022", "A-033", "A-047",
    "S-000", "S-012", "S-019", "S-024", "N-09", "N-10", "D-06", "D-14", "D-15",
    "D-22", "D-27", "D-28", "X-G2-02", "X-G2-11a", "X-G2-14", "X-G3-01a",
]


def _case(row: dict) -> dict:
    c = {"id": row["id"], "test": "indep", "tails": int(row["tails"]),
         "es": float(row["d"]), "alpha": float(row["alpha"])}
    if row["mode"] == "a-priori":
        c.update(analysis="a priori", power=float(row["power"]), ratio=float(row["ratio"]))
    else:
        c.update(analysis="post hoc", n1=int(row["n1_in"]), n2=int(row["n2_in"]))
    return c


def _window_rect() -> str:
    out = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to tell process "G*Power" '
                            'to get {position, size} of window "G*Power 3.1"'],
        capture_output=True, text=True, check=True).stdout
    x, y, w, h = (int(v) for v in out.replace(" ", "").strip().split(","))
    return f"{x},{y},{w},{h}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", default=DEFAULT)
    a = ap.parse_args(argv)
    rows = {r["id"]: r for r in csv.DictReader(CSV.open(encoding="utf-8"))}
    SHOTS.mkdir(parents=True, exist_ok=True)
    bad = 0
    for vid in a.ids:
        row = rows[vid]
        case = _case(row)
        gui = gpower_ax.run("indep", case["analysis"], gui_settings(case))
        out = gui["outputs"]
        if row["gpower_error"]:
            same = bool(gui.get("dialog"))
        else:
            same = (out.get("Total sample size", row["n_total"]) == row["n_total"]
                    and out.get("Critical t") == row["critical"])
        png = SHOTS / f"{vid}.png"
        p = subprocess.run(["screencapture", "-x", "-o", "-R", _window_rect(), str(png)],
                           capture_output=True, text=True)
        if p.returncode != 0 or not png.exists():
            print(f"{vid}: screenshot failed ({p.stderr.strip()}) -- is Screen "
                  "Recording permission granted and the terminal restarted?")
            return 2
        bad += not same
        print(f"{vid}: {'ok' if same else 'DIFFERS FROM CSV'} -> {png.relative_to(ROOT)}")
    print(f"{len(a.ids)} screenshots, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
