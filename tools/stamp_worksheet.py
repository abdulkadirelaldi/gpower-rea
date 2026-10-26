#!/usr/bin/env python
"""Fill the ``observed`` column of the pre-registered probe worksheet.

    python tools/stamp_worksheet.py         # then: python tools/harvest.py

The predictions in ``probes/probe_worksheet.csv`` were generated and committed
*before* any observation was made (commit ``aad154e``).  This script writes
only the ``observed`` column, from the raw GUI readings in
``probes/observations/``, and leaves every prediction byte-for-byte as it was
registered.  That is the point of a pre-registration: the engine that made the
predictions has since been corrected where the observations refuted it, but
the worksheet still shows what it predicted.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from rea_report import load_observations  # noqa: E402

WORKSHEET = ROOT / "probes" / "probe_worksheet.csv"

#: read_field token → G*Power output label
LABEL = {
    "delta": "Noncentrality parameter δ",
    "Critical t": "Critical t",
    "Df": "Df",
    "N": "Total sample size",
    "Total sample size": "Total sample size",
    "Actual power": "Actual power",
    "Power": "Power (1-β err prob)",
    "n1": "Sample size group 1",
    "n2": "Sample size group 2",
    "alpha": "α err prob",
    "beta": "β err prob",
    "Effect size d": "Effect size d",
}


def observed_string(row: dict, obs: dict[str, dict]) -> str | None:
    pid = row["probe_id"]
    if pid == "P-03-b":
        a, b = obs.get("P-03-a"), obs.get("P-03-b")
        if not (a and b):
            return None
        same = a["gui"]["outputs"] == b["gui"]["outputs"]
        return ("identical across the two menu entries" if same
                else f"differ: {a['gui']['outputs']} vs {b['gui']['outputs']}")
    rec = obs.get(pid)
    if rec is None:
        return None
    out = rec["gui"]["outputs"]
    if rec["gui"].get("dialog"):
        return "refused: " + rec["gui"]["dialog"].lstrip(": ")
    parts = []
    for token in (t.strip() for t in row["read_field"].split("/")):
        label = LABEL.get(token, token)
        if label not in out:
            return None
        parts.append(out[label])
    return " / ".join(parts)


def main() -> int:
    obs = {r["id"]: r for r in load_observations()}
    raw = WORKSHEET.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(raw)))
    fields = list(rows[0].keys())
    stamped = 0
    for row in rows:
        val = observed_string(row, obs)
        if val is not None:
            row["observed"] = val
            stamped += 1
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    WORKSHEET.write_text(buf.getvalue(), encoding="utf-8")
    print(f"stamped {stamped}/{len(rows)} rows of {WORKSHEET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
