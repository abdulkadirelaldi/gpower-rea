#!/usr/bin/env python
"""Regenerate the bundled reference-vector file.

    python tools/make_vectors.py            # rewrite src/gpower_rea/data/public_vectors.csv
    python tools/make_vectors.py --check    # fail if the file is stale

The vectors are engine output.  They are NOT self-certifying: the independent
check lives in tests/test_reference_scipy.py, which re-derives every
``expected_N`` with a SciPy implementation written straight from the formulas
in SPEC.md, and in docs/VALIDATION.md, which records the result.  Rows whose
`source` says `literature` additionally match a published G*Power output; see
docs/EVIDENCE/ for the provenance of each one.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gpower_rea import solve  # noqa: E402

OUT = ROOT / "src" / "gpower_rea" / "data" / "public_vectors.csv"

FIELDS = [
    "id",
    "test",
    "solve",
    "tails",
    "alpha",
    "power",
    "effect_size",
    "ratio",
    "predictors",
    "n",
    "expected_N",
    "expected_power",
    "source",
]


def _row(
    vid: str,
    test: str,
    *,
    tails: int,
    alpha: float,
    power: float,
    effect_size: float,
    ratio: float | None = None,
    predictors: int | None = None,
    source: str = "cross-validated",
) -> dict:
    res = solve(
        test,
        "n",
        alpha=alpha,
        power_target=power,
        effect_size=effect_size,
        tails=tails,
        allocation_ratio=ratio,
        extra={"predictors": predictors} if predictors is not None else None,
    )
    return {
        "id": vid,
        "test": test,
        "solve": "n",
        "tails": tails,
        "alpha": alpha,
        "power": power,
        "effect_size": effect_size,
        "ratio": "" if ratio is None else ratio,
        "predictors": "" if predictors is None else predictors,
        "n": "",
        "expected_N": res.sample_size["total"],
        "expected_power": f"{res.power:.7f}",
        "source": source,
    }


def generate() -> list[dict]:
    rows: list[dict] = []
    k = 0

    def nxt(prefix: str) -> str:
        nonlocal k
        k += 1
        return f"{prefix}-{k:03d}"

    # -- the canonical published example (Faul et al. 2007, Fig. 4) ----------
    rows.append(
        _row(
            "LIT-001",
            "ttest-indep-means",
            tails=2,
            alpha=0.05,
            power=0.95,
            effect_size=0.5,
            ratio=1.0,
            source="literature: G*Power 3 canonical two-group example",
        )
    )

    # -- two independent means, balanced -----------------------------------
    for d in (0.2, 0.3, 0.4, 0.5, 0.65, 0.8, 1.0, 1.2):
        for alpha in (0.01, 0.05, 0.10):
            for pw in (0.80, 0.90, 0.95):
                for tails in (1, 2):
                    rows.append(
                        _row(
                            nxt("IND"),
                            "ttest-indep-means",
                            tails=tails,
                            alpha=alpha,
                            power=pw,
                            effect_size=d,
                            ratio=1.0,
                        )
                    )

    # -- two independent means, unbalanced ---------------------------------
    for ratio in (0.5, 1.5, 2.0, 3.0):
        for d in (0.3, 0.5, 0.8):
            for pw in (0.80, 0.95):
                rows.append(
                    _row(
                        nxt("ALLOC"),
                        "ttest-indep-means",
                        tails=2,
                        alpha=0.05,
                        power=pw,
                        effect_size=d,
                        ratio=ratio,
                    )
                )

    # -- one sample and matched pairs --------------------------------------
    for key, prefix in (
        ("ttest-one-sample", "ONE"),
        ("ttest-paired-means", "PAIR"),
    ):
        for d in (0.2, 0.3, 0.5, 0.8, 1.0):
            for alpha in (0.01, 0.05):
                for pw in (0.80, 0.90, 0.95):
                    for tails in (1, 2):
                        rows.append(
                            _row(
                                nxt(prefix),
                                key,
                                tails=tails,
                                alpha=alpha,
                                power=pw,
                                effect_size=d,
                            )
                        )

    # -- point biserial correlation ----------------------------------------
    for r in (0.1, 0.2, 0.3, 0.4, 0.5, 0.7):
        for alpha in (0.01, 0.05):
            for pw in (0.80, 0.95):
                for tails in (1, 2):
                    rows.append(
                        _row(
                            nxt("PBS"),
                            "ttest-point-biserial",
                            tails=tails,
                            alpha=alpha,
                            power=pw,
                            effect_size=r,
                        )
                    )

    # -- single regression coefficient -------------------------------------
    for f2 in (0.02, 0.05, 0.15, 0.35):
        for p in (1, 2, 5, 10):
            for pw in (0.80, 0.95):
                for tails in (1, 2):
                    rows.append(
                        _row(
                            nxt("REG"),
                            "ttest-regression-coef",
                            tails=tails,
                            alpha=0.05,
                            power=pw,
                            effect_size=f2,
                            predictors=p,
                        )
                    )
    return rows


def render(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify freshness, write nothing")
    args = ap.parse_args()

    text = render(generate())
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current.replace("\r\n", "\n") != text:
            print(f"STALE: {OUT} differs from freshly generated vectors", file=sys.stderr)
            return 1
        print(f"fresh: {OUT} ({text.count(chr(10)) - 1} vectors)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({text.count(chr(10)) - 1} vectors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
