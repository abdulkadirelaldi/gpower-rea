#!/usr/bin/env python
"""Scale oracle: 500+ t2-indep vectors from statsmodels, against the engine.

    python tools/statsmodels_oracle.py      # writes oracle/statsmodels_t2_indep.csv

statsmodels' ``TTestIndPower.solve_power`` returns a *fractional* n1 for a
continuous ratio.  G*Power reports integers, and not by a plain ceil: it
searches even totals and splits by ``round_half_up(N/(1+R))`` (SPEC F-09).
This script records, for every vector, statsmodels' fractional n1, the three
naive integerisations, and the engine's (= G*Power's) answer, so the
difference is measured rather than asserted.
"""

from __future__ import annotations

import csv
import itertools
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpower_rea import solve  # noqa: E402

OUT = ROOT / "oracle" / "statsmodels_t2_indep.csv"


def main() -> int:
    from statsmodels.stats.power import TTestIndPower  # test-only oracle

    sm = TTestIndPower()
    D = [0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2]
    P = [0.8, 0.9, 0.95]
    A = [0.01, 0.05, 0.1]
    R = [0.5, 1, 1.5, 2, 3]
    T = [1, 2]
    rows = []
    for d, pw, a, r, t in itertools.product(D, P, A, R, T):
        alt = "two-sided" if t == 2 else "larger"
        n1f = float(sm.solve_power(effect_size=d, alpha=a, power=pw, ratio=r,
                                   alternative=alt))
        e = solve("ttest-indep-means", "n", alpha=a, power_target=pw,
                  effect_size=d, tails=t, allocation_ratio=r)
        ss = e.sample_size
        ceil1 = math.ceil(n1f)
        ceil_each = ceil1 + math.ceil(r * n1f)
        ceil_total = math.ceil(n1f * (1 + r))
        rows.append({
            "d": d, "power": pw, "alpha": a, "ratio": r, "tails": t,
            "statsmodels_n1": f"{n1f:.6f}",
            "statsmodels_n_total": f"{n1f * (1 + r):.6f}",
            "ceil_n1_times_1plusR": math.ceil(ceil1 * (1 + r)),
            "ceil_each_group": ceil_each,
            "ceil_total": ceil_total,
            "engine_n1": ss["n1"], "engine_n2": ss["n2"], "engine_n_total": ss["total"],
            "engine_actual_power": f"{e.power:.7f}",
            "statsmodels_power_at_engine_design": f"{float(sm.power(effect_size=d, nobs1=ss['n1'], alpha=a, ratio=ss['n2'] / ss['n1'], alternative=alt)):.7f}",
        })
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    agree = {k: sum(int(r[k]) == r["engine_n_total"] for r in rows)
             for k in ("ceil_total", "ceil_each_group", "ceil_n1_times_1plusR")}
    pw_agree = sum(abs(float(r["statsmodels_power_at_engine_design"])
                       - float(r["engine_actual_power"])) < 1e-4 for r in rows)
    print(f"{n} vectors -> {OUT.relative_to(ROOT)}")
    for k, v in agree.items():
        print(f"  {k:<22} gives G*Power's N in {v}/{n} ({v / n:.1%})")
    print(f"  power at the engine's design agrees with statsmodels (1e-4): {pw_agree}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
