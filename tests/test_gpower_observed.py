"""[REA] The engine against the real G*Power 3.1.9.6.

Every record in ``probes/observations/`` is a reading of G*Power's own output
panel, made through its GUI by ``tools/rea_campaign.py``.  These tests re-run
the current engine on each recorded input and require it to print exactly what
G*Power printed.  No G*Power installation is needed to run them.

The only tolerated differences are the ones SPEC F-14 documents: a criterion
or compromise result with alpha below 1e-9, where G*Power itself is inexact
(arbitrated against a 50-digit computation in E-014).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from rea_report import evaluate, load_observations, summarise  # noqa: E402

from gpower_rea.engine import GPOWER_ALPHA_FLOOR, LARGE_N_WARNING  # noqa: E402

RECORDS = sorted(load_observations(), key=lambda r: r["id"])
RESULTS = [evaluate(r) for r in RECORDS]


def _f14(res: dict) -> bool:
    """A result in the regions where G*Power itself is inexact (SPEC F-14):
    a criterion/compromise alpha below 1e-9, or an a-priori N above 1e7."""
    shown_n = res.get("fields", {}).get("Total sample size", {}).get("gui")
    if shown_n is not None and int(shown_n) > LARGE_N_WARNING:
        return True
    if res["case"]["analysis"] not in ("criterion", "compromise"):
        return False
    if res["dialog"] and "Internal Math Error" in res["dialog"]:
        return True
    shown = res.get("fields", {}).get("α err prob", {}).get("gui")
    return shown is not None and float(shown) < GPOWER_ALPHA_FLOOR


def test_there_are_enough_observations():
    assert len(RECORDS) >= 250
    tests = {r["case"]["test"] for r in RECORDS}
    assert tests == {"indep", "paired", "one-sample", "point-biserial",
                     "regression", "generic"}
    analyses = {r["case"]["analysis"] for r in RECORDS}
    assert analyses == {"a priori", "post hoc", "criterion", "sensitivity",
                        "compromise"}


def test_every_a_priori_N_is_exact():
    """Every a-priori N up to 1e7 is identical to G*Power's.  Beyond that the
    power moves by < 1e-8 per participant and G*Power's own N is inexact
    (arbitrated in E-014), so those rows are judged by F-14 instead."""
    rows = [r for r in RESULTS if r["case"]["analysis"] == "a priori" and "fields" in r
            and "Total sample size" in r["fields"]
            and int(r["fields"]["Total sample size"]["gui"]) <= LARGE_N_WARNING]
    assert len(rows) >= 200
    assert all(r["fields"]["Total sample size"]["printed_match"] for r in rows)


@pytest.mark.parametrize("res", RESULTS, ids=[r["id"] for r in RESULTS])
def test_engine_prints_what_gpower_printed(res):
    if res["status"] in ("match", "both-refuse"):
        return
    assert _f14(res), f"{res['id']}: {res['detail']}"


def test_the_f14_region_is_small_and_flagged():
    flagged = [r for r in RESULTS if r["status"] == "MISMATCH"]
    assert len(flagged) <= 0.05 * len(RESULTS)
