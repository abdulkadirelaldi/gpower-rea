#!/usr/bin/env python
"""Score candidate allocation rules against the recorded G*Power readings.

    python tools/fit_allocation.py

This is how SPEC F-09 was settled (evidence E-009).  Every a-priori
two-group observation is replayed under each candidate rule; a rule *fits* a
row only if it reproduces n1, n2 **and** the printed Actual power exactly.
The script uses the engine's power function and nothing else from it, so the
rules compared here are written out in full below, independently of
``engine._allocate``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from gpower_rea.engine import _power_from_ncp  # noqa: E402
from rea_report import load_observations  # noqa: E402


def _pw(n1: float, n2: float, d: float, alpha: float, tails: int) -> float:
    return _power_from_ncp(alpha, n1 + n2 - 2, abs(d) * math.sqrt(n1 * n2 / (n1 + n2)), tails)[0]


def rh(x: float) -> int:
    return int(math.floor(x + 0.5))


def split_round(N: int, R: float) -> tuple[int, int]:
    a = rh(N / (1 + R))
    return a, N - a


def _search(step: int, start: int, check, report):
    """Generic rule: walk N from ``start`` in ``step``; test ``check(N)``;
    report ``report(N)``."""
    def run(c):
        R, d, a, t, p = c["ratio"], c["es"], c["alpha"], c.get("tails", 2), c["power"]
        N = start
        while N < 200_000:
            m1, m2 = check(N, R)
            if min(m1, m2) >= 1 and _pw(m1, m2, d, a, t) >= p:
                return report(N, R)
            N += step
        raise RuntimeError("no solution")
    return run


def _n1_grid(c):
    R, d, a, t, p = c["ratio"], c["es"], c["alpha"], c.get("tails", 2), c["power"]
    n1 = 2
    while True:
        n2 = max(rh(R * n1), 2)
        if _pw(n1, n2, d, a, t) >= p:
            return n1, n2
        n1 += 1


def _ceil_each(c):
    R, d, a, t, p = c["ratio"], c["es"], c["alpha"], c.get("tails", 2), c["power"]
    lo, hi = 1.0, 1e6
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if _pw(m, R * m, d, a, t) >= p:
            hi = m
        else:
            lo = m
    return math.ceil(hi), math.ceil(R * hi)


cont = lambda N, R: (N / (1 + R), N * R / (1 + R))  # noqa: E731
floor1 = lambda N, R: (math.floor(N / (1 + R)), N - math.floor(N / (1 + R)))  # noqa: E731

CANDIDATES = {
    "even-total (SPEC v1.2)": _search(2, 4, cont, split_round),
    "n1-grid (SPEC v1.1 default)": _n1_grid,
    "total-grid (SPEC v1.1 alternative)": _search(1, 4, split_round, split_round),
    "every N, unrounded check": _search(1, 4, cont, split_round),
    "even N, rounded check": _search(2, 4, split_round, split_round),
    "every N, n1 floored": _search(1, 4, floor1, split_round),
    "ceil each group of the continuous solution": _ceil_each,
}


def main() -> int:
    rows = [r for r in load_observations()
            if r["case"]["test"] == "indep" and r["case"]["analysis"] == "a priori"]
    rows = [r for r in rows if r["case"].get("es", 0) != 0
            and not r["gui"].get("dialog")                     # refused input
            and int(r["gui"]["outputs"]["Total sample size"]) <= 10_000_000]  # F-14
    for r in rows:
        r["case"].setdefault("ratio", 1)
    print(f"{len(rows)} a-priori two-group observations "
          f"({sum(r['case']['ratio'] != 1 for r in rows)} with R != 1)\n")
    print(f"{'rule':45s} {'all rows':>10s} {'R != 1':>10s}")
    for name, rule in CANDIDATES.items():
        hit = hit_u = n_u = 0
        for r in rows:
            c = r["case"]
            out = r["gui"]["outputs"]
            n1, n2 = rule(c)
            ap = _pw(n1, n2, c["es"], c["alpha"], c.get("tails", 2))
            ok = (n1 == int(out["Sample size group 1"])
                  and n2 == int(out["Sample size group 2"])
                  and f"{ap:.7f}" == out["Actual power"])
            hit += ok
            if c["ratio"] != 1:
                n_u += 1
                hit_u += ok
        print(f"{name:45s} {hit:>4d}/{len(rows):<5d} {hit_u:>4d}/{n_u:<5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
