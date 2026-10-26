"""The course's fixed CLI contract (``gpower-clone``), locked.

1. the example line of the assignment, byte for byte;
2. every recorded G*Power 3.1.9.6 t2-indep reading, through this CLI;
3. invalid input -> one ``{"error": ...}`` line and a non-zero exit;
4. CLI and MCP server give the same output for the same input.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from gpower_rea.clone_cli import main

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from rea_report import load_observations  # noqa: E402

EXAMPLE = ("--test t2-indep --mode a-priori --tails 2 --d 0.5 "
           "--alpha 0.05 --power 0.95 --ratio 1").split()
EXAMPLE_LINE = ('{"n1":105,"n2":105,"n_total":210,"actual_power":0.9501,'
                '"critical":1.9714,"df":208,"ncp":3.6228}')


def run(argv, capsys):
    code = main(argv)
    out = capsys.readouterr().out
    assert out.count("\n") == 1, "exactly one line on stdout"
    return code, json.loads(out), out.strip()


def test_the_assignment_example_byte_for_byte(capsys):
    code, _, line = run(EXAMPLE, capsys)
    assert code == 0
    assert line == EXAMPLE_LINE


def test_the_installed_console_script(tmp_path):
    exe = Path(sys.executable).with_name("gpower-clone")
    if not exe.exists():
        pytest.skip("console script not installed (pip install -e .)")
    p = subprocess.run([str(exe), *EXAMPLE], capture_output=True, text=True)
    assert p.returncode == 0
    assert p.stdout.strip() == EXAMPLE_LINE


# --------------------------------------------------------------------------
# every t2-indep G*Power reading, through the contract CLI
# --------------------------------------------------------------------------
def _gpower_rows():
    rows = []
    for rec in load_observations():
        c, g = rec["case"], rec["gui"]
        if c["test"] != "indep" or c["analysis"] not in ("a priori", "post hoc"):
            continue
        out = g["outputs"]
        if g.get("dialog") or int(out.get("Total sample size", 0) or 0) > 10_000_000:
            continue
        rows.append(rec)
    return sorted(rows, key=lambda r: r["id"])


ROWS = _gpower_rows()


def _argv(c):
    a = ["--test", "t2-indep", "--tails", str(c.get("tails", 2)),
         "--d", repr(c["es"]), "--alpha", repr(c["alpha"])]
    if c["analysis"] == "a priori":
        a += ["--mode", "a-priori", "--power", repr(c["power"]),
              "--ratio", repr(float(c.get("ratio", 1)))]
    else:
        a += ["--mode", "post-hoc", "--n1", str(c["n1"]), "--n2", str(c["n2"])]
    return a


def test_there_are_enough_gpower_rows():
    assert len(ROWS) >= 120


@pytest.mark.parametrize("rec", ROWS, ids=[r["id"] for r in ROWS])
def test_clone_cli_reproduces_gpower(rec, capsys):
    """N, n1, n2 exact; the rest to the 4 decimals the contract prints."""
    code, got, _ = run(_argv(rec["case"]), capsys)
    assert code == 0, got
    out = rec["gui"]["outputs"]
    if rec["case"]["analysis"] == "a priori":
        assert got["n1"] == int(out["Sample size group 1"])
        assert got["n2"] == int(out["Sample size group 2"])
        assert got["n_total"] == int(out["Total sample size"])
        assert got["actual_power"] == round(float(out["Actual power"]), 4)
    else:
        assert got["actual_power"] == round(float(out["Power (1-β err prob)"]), 4)
    assert got["df"] == int(out["Df"])
    assert got["critical"] == round(float(out["Critical t"]), 4)
    assert got["ncp"] == round(float(out["Noncentrality parameter δ"]), 4)


# --------------------------------------------------------------------------
# invalid input
# --------------------------------------------------------------------------
@pytest.mark.parametrize("argv", [
    [],
    ["--test", "t2-indep"],
    ["--test", "t2-indep", "--mode", "sideways", "--d", "0.5", "--alpha", "0.05"],
    ["--test", "anova-oneway", "--mode", "a-priori", "--d", "0.5", "--alpha", "0.05", "--power", "0.8"],
    EXAMPLE[:-2] + ["--ratio", "1000"],                          # outside [0.01, 100]
    ["--test", "t2-indep", "--mode", "a-priori", "--tails", "3", "--d", "0.5", "--alpha", "0.05", "--power", "0.8"],
    ["--test", "t2-indep", "--mode", "a-priori", "--d", "0", "--alpha", "0.05", "--power", "0.8"],
    ["--test", "t2-indep", "--mode", "a-priori", "--d", "0.5", "--alpha", "0.05", "--power", "0.04"],
    ["--test", "t2-indep", "--mode", "a-priori", "--d", "0.5", "--alpha", "1.5", "--power", "0.8"],
    ["--test", "t2-indep", "--mode", "post-hoc", "--d", "0.5", "--alpha", "0.05", "--n1", "0", "--n2", "3"],
    ["--test", "t2-indep", "--mode", "a-priori", "--d", "abc", "--alpha", "0.05", "--power", "0.8"],
])
def test_invalid_input_is_one_error_line_and_nonzero_exit(argv, capsys):
    code, got, _ = run(argv, capsys)
    assert code != 0
    assert set(got) == {"error"} and got["error"]


# --------------------------------------------------------------------------
# CLI == MCP
# --------------------------------------------------------------------------
CASES = [
    dict(mode="a-priori", d=0.5, alpha=0.05, power=0.95, ratio=1, tails=2),
    dict(mode="a-priori", d=0.3, alpha=0.01, power=0.8, ratio=2.5, tails=1),
    dict(mode="a-priori", d=0.8, alpha=0.05, power=0.9, ratio=0.5, tails=2),
    dict(mode="post-hoc", d=0.5, alpha=0.05, n1=40, n2=60, tails=2),
    dict(mode="post-hoc", d=-0.4, alpha=0.05, n1=30, n2=30, tails=1),
]


@pytest.mark.parametrize("case", CASES)
def test_cli_and_mcp_give_the_same_output(case, capsys):
    pytest.importorskip("mcp")
    from test_mcp_server import _call  # noqa: PLC0415

    argv = ["--test", "t2-indep", "--mode", case["mode"], "--tails", str(case["tails"]),
            "--d", str(case["d"]), "--alpha", str(case["alpha"])]
    args = {"test": "ttest-indep-means", "alpha": case["alpha"],
            "effect_size": case["d"], "tails": case["tails"]}
    if case["mode"] == "a-priori":
        argv += ["--power", str(case["power"]), "--ratio", str(case["ratio"])]
        args.update(solve_for="n", power=case["power"], allocation_ratio=case["ratio"])
    else:
        argv += ["--n1", str(case["n1"]), "--n2", str(case["n2"])]
        args.update(solve_for="power", n1=case["n1"], n2=case["n2"])
    _, cli, _ = run(argv, capsys)
    payload = _call("power_analysis", args)
    m = payload["result"] if "result" in payload else payload
    ss = m["sample_size"]
    assert cli == {
        "n1": ss["n1"], "n2": ss["n2"], "n_total": ss["total"],
        "actual_power": round(m["power"], 4), "critical": round(m["critical_t"], 4),
        "df": int(m["df"]), "ncp": round(m["noncentrality"], 4),
    }
