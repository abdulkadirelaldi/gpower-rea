#!/usr/bin/env python
"""Measure the GUI path against the MCP path on the same 10 questions.

    python tools/gui_token_eval.py           # needs G*Power + Screen Recording

The MCP path is measured by ``tools/agent_eval.py``.  For the GUI path, an
agent that can only see the screen must at minimum *read* G*Power's result
off a screenshot.  This script measures that minimum, for real:

1. it enters each question's inputs in the running G*Power GUI and saves a
   screenshot of the window after *Calculate* (``agent/eval/gui/Qnn.png``);
2. it hands that screenshot to the same model (Claude Code headless, only the
   Read tool allowed) with the question "what does G*Power report?";
3. it records the tokens, wall time and whether the number read is right.

A real GUI agent needs more than one screenshot per question -- one after
every action that changes the screen (test menu, analysis menu, each input
field, Calculate) -- so the report gives both the measured one-screenshot
lower bound and the cost scaled by the number of screen-changing actions the
question requires, which ``tools/gpower_ax.py`` counts exactly.

Writes ``agent/eval/gui/results.json`` and appends to ``agent/eval/REPORT.md``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gpower_ax  # noqa: E402
from oracle_screenshots import _window_rect  # noqa: E402
from rea_campaign import agent_eval_cases, gui_settings  # noqa: E402

EVAL = ROOT / "agent" / "eval"
GUI = EVAL / "gui"


def _ask(png: Path, question: str, model: str) -> dict:
    prompt = (f"Read the image file {png.name}. It is a G*Power window after "
              f"Calculate, for this question: {question}\n"
              "Reply with one line of JSON only: "
              '{"n_total": <int or null>, "power": <float or null>}, taken from '
              "the Output parameters panel.")
    t0 = time.time()
    p = subprocess.run(["claude", "-p", prompt, "--model", model,
                        "--allowedTools", "Read", "--output-format", "json"],
                       capture_output=True, text=True, cwd=str(png.parent),
                       stdin=subprocess.DEVNULL)
    wall = time.time() - t0
    res = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
    m = re.search(r"\{.*\}", res.get("result", ""), re.S)
    try:
        answer = json.loads(m.group(0)) if m else {}
    except ValueError:
        answer = {}
    return {"answer": answer, "usage": res.get("usage"), "cost_usd": res.get("total_cost_usd"),
            "wall_seconds": round(wall, 1)}


def main(model: str = "claude-opus-5-5") -> int:
    qs = {q["id"]: q for q in json.loads((EVAL / "questions.json").read_text(encoding="utf-8"))}
    GUI.mkdir(parents=True, exist_ok=True)
    out = []
    for case in agent_eval_cases():
        qid = case["id"][2:]
        q = qs[qid]
        settings = gui_settings(case)
        gpower_ax.run(case["test"], case["analysis"], settings)
        png = GUI / f"{qid}.png"
        r = subprocess.run(["screencapture", "-x", "-o", "-R", _window_rect(), str(png)],
                           capture_output=True, text=True)
        if r.returncode or not png.exists():
            print("screenshot failed: grant Screen Recording and restart the terminal")
            return 2
        actions = 3 + len(settings)          # test menu, analysis menu, Calculate, fields
        m = _ask(png, q["question"], model)
        exp = q["expected"]
        if "power" in q["expected_parameters"]:
            ok = m["answer"].get("n_total") == exp["n_total"]
        else:
            ok = m["answer"].get("power") is not None and abs(m["answer"]["power"] - exp["power"]) < 5e-4
        u = m.get("usage") or {}
        tok = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
               + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0))
        out.append({"id": qid, "screen_actions": actions, "read_correct": ok,
                    "tokens_one_screenshot": tok, "tokens_scaled": tok * actions,
                    "wall_one_screenshot": m["wall_seconds"],
                    "cost_one_screenshot": m.get("cost_usd"), "raw": m})
        print(qid, ok, tok, "tokens x", actions, "actions")
    (GUI / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    runs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (EVAL / "runs").glob("Q*.json")}
    L = ["", "## GUI path vs MCP path (same questions, same model)", "",
         "| id | MCP tokens | MCP s | MCP correct | GUI: 1 screenshot tokens | GUI s | GUI read correct | screen actions | GUI tokens, scaled |",
         "|---|---|---|---|---|---|---|---|---|"]
    for g in out:
        r = runs.get(g["id"], {})
        u = r.get("usage") or {}
        mt = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
              + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0))
        L.append(f"| {g['id']} | {mt} | {r.get('wall_seconds')} | {'✔' if r.get('score', {}).get('answer') else '✘'} | "
                 f"{g['tokens_one_screenshot']} | {g['wall_one_screenshot']} | {'✔' if g['read_correct'] else '✘'} | "
                 f"{g['screen_actions']} | {g['tokens_scaled']} |")
    with (EVAL / "REPORT.md").open("a", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
