"""SPEC.md §6 is executable: every Gherkin ``Examples:`` row runs here.

The expected values in SPEC.md are G*Power 3.1.9.6 readings (oracle/), so
this test holds the CLI to the specification *and* to the reference program
in one step.  A row added to SPEC.md is a test added here, with no code change.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest

from gpower_rea.clone_cli import main

SPEC = Path(__file__).resolve().parents[1] / "SPEC.md"
BASE = ["--test", "t2-indep"]


def _gherkin() -> str:
    text = SPEC.read_text(encoding="utf-8")
    m = re.search(r"## 6\. Acceptance criteria.*?```gherkin\n(.*?)```", text, re.S)
    assert m, "SPEC.md §6 Gherkin block not found"
    return m.group(1)


def _outlines():
    """(scenario title, step template, [row dicts]) per Scenario Outline."""
    out = []
    for block in re.split(r"\n  Scenario Outline: ", _gherkin())[1:]:
        title = block.splitlines()[0].strip()
        when = re.search(r'When I run "(.*?)"', block).group(1)
        table = [ln.strip() for ln in block.split("Examples:")[1].splitlines()
                 if ln.strip().startswith("|")]
        head = [c.strip() for c in table[0].strip("|").split("|")]
        rows = [dict(zip(head, (c.strip() for c in ln.strip("|").split("|"))))
                for ln in table[1:]]
        out.append((title, when, rows))
    return out


OUTLINES = _outlines()


def _run(argv, capsys):
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def _params(kind):
    for title, when, rows in OUTLINES:
        if title.startswith(kind):
            for r in rows:
                yield pytest.param(when, r, id=r.get("id") or r.get("case"))


def test_spec_has_the_three_outlines():
    titles = [t for t, _, _ in OUTLINES]
    assert titles == ["a priori sample size", "post hoc power", "invalid input"]
    assert sum(len(r) for _, _, r in OUTLINES) >= 35


@pytest.mark.parametrize("when,row", list(_params("a priori")))
def test_a_priori_examples(when, row, capsys):
    argv = BASE + shlex.split(re.sub(r"<(\w+)>", lambda m: row[m.group(1)], when))
    code, got = _run(argv, capsys)
    assert code == 0, got
    for k in ("n1", "n2", "n_total", "df"):
        assert got[k] == int(row[k]), k
    for k in ("actual_power", "critical", "ncp"):
        assert f"{got[k]:.4f}" == row[k], k


@pytest.mark.parametrize("when,row", list(_params("post hoc")))
def test_post_hoc_examples(when, row, capsys):
    argv = BASE + shlex.split(re.sub(r"<(\w+)>", lambda m: row[m.group(1)], when))
    code, got = _run(argv, capsys)
    assert code == 0, got
    assert got["df"] == int(row["df"])
    for k in ("actual_power", "critical", "ncp"):
        assert f"{got[k]:.4f}" == row[k], k


@pytest.mark.parametrize("when,row", list(_params("invalid")))
def test_invalid_examples(when, row, capsys):
    code, got = _run(BASE + shlex.split(row["args"]), capsys)
    assert code != 0
    assert list(got) == ["error"] and got["error"]


def test_scenario_actual_power_below_target(capsys):
    code, got = _run(BASE + shlex.split(
        "--mode a-priori --tails 2 --d 0.5 --alpha 0.05 --power 0.9495 --ratio 1.5"), capsys)
    assert (got["n1"], got["n2"]) == (87, 131)
    assert got["actual_power"] == 0.9494 < 0.9495


def test_scenario_empty_group(capsys):
    code, got = _run(BASE + shlex.split(
        "--mode a-priori --tails 2 --d 20 --alpha 0.05 --power 0.8 --ratio 100"), capsys)
    assert (got["n1"], got["n2"], got["actual_power"]) == (0, 6, 0.05)
