#!/usr/bin/env python
"""Run the 10-question Turkish evaluation set through an agent over MCP.

    python tools/agent_eval.py                # all questions
    python tools/agent_eval.py --only Q03

Each question in ``agent/eval/questions.json`` is put to a model whose ONLY
tools are the six ``gpower`` MCP tools (Claude Code headless as the harness,
``--strict-mcp-config``), with the system prompt of ``agent/agent.py``.
Everything is logged: every tool call and result, the final answer, tokens,
cost and wall time.  Scoring is mechanical and uses the expected values in
the question file, which are G*Power readings (``E-Qnn`` in
``probes/observations/``):

* family  -- the test the agent called (or, for unsupported / ambiguous
  questions, that it called no analysis and gave no number);
* params  -- every expected parameter appears in the tool call;
* answer  -- the expected N (or power) appears in the final answer.

Outputs ``agent/eval/runs/<id>.json`` and ``agent/eval/REPORT.md``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "agent" / "eval"
KEY = {"t2-indep": "ttest-indep-means", "t-paired": "ttest-paired-means"}


def system_prompt() -> str:
    src = (ROOT / "agent" / "agent.py").read_text(encoding="utf-8")
    return re.search(r'SYSTEM_PROMPT = """\\\n(.*?)"""', src, re.S).group(1)


def run_one(q: dict, mcp_bin: str, model: str) -> dict:
    cfg = {"mcpServers": {"gpower": {"command": mcp_bin, "args": []}}}
    with tempfile.TemporaryDirectory() as td:
        cfgp = Path(td) / "mcp.json"
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")
        t0 = time.time()
        p = subprocess.run(
            ["claude", "-p", q["question"], "--model", model,
             "--mcp-config", str(cfgp), "--strict-mcp-config",
             "--allowedTools", "mcp__gpower__*",
             "--append-system-prompt", system_prompt(),
             "--output-format", "stream-json", "--verbose"],
            capture_output=True, text=True, cwd=td, stdin=subprocess.DEVNULL)
        wall = time.time() - t0
    events = [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")]
    calls, pending, final = [], {}, ""
    for e in events:
        if e.get("type") == "assistant":
            for b in e["message"]["content"]:
                if b["type"] == "tool_use" and b["name"].startswith("mcp__gpower"):
                    pending[b["id"]] = {"tool": b["name"].split("__")[-1], "input": b["input"]}
                elif b["type"] == "text":
                    final = b["text"]
        elif e.get("type") == "user":
            for b in e["message"]["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b["tool_use_id"] in pending:
                    c = pending.pop(b["tool_use_id"])
                    txt = b["content"][0]["text"] if isinstance(b["content"], list) else b["content"]
                    try:
                        c["output"] = json.loads(txt)
                    except (ValueError, TypeError):
                        c["output"] = txt
                    calls.append(c)
    res = next((e for e in events if e.get("type") == "result"), {})
    return {"id": q["id"], "question": q["question"], "tool_calls": calls,
            "final_answer": final, "wall_seconds": round(wall, 1),
            "usage": res.get("usage"), "cost_usd": res.get("total_cost_usd"),
            "num_turns": res.get("num_turns"), "model": model, "exit_code": p.returncode}


def _num_in(text: str, value) -> bool:
    if isinstance(value, int):
        return re.search(rf"(?<![\d.,]){value}(?![\d.,]\d)", text) is not None
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    variants = {s, s.replace(".", ","), f"{value:.3f}", f"{value:.3f}".replace(".", ",")}
    return any(v in text for v in variants)


def score(q: dict, run: dict) -> dict:
    fam = q["expected_family"]
    analyses = [c for c in run["tool_calls"] if c["tool"] == "power_analysis"]
    ok = [c for c in analyses if isinstance(c.get("output"), dict) and c["output"].get("ok")]
    if fam in ("unsupported", "ambiguous"):
        no_number = not ok
        return {"family": no_number, "params": no_number, "answer": no_number,
                "note": "no analysis called, no number given" if no_number else "gave a number"}
    p, exp = q["expected_parameters"], q["expected"]
    fam_ok = any(c["input"].get("test", "").lower() in (KEY[fam], fam) or
                 KEY[fam].endswith(c["input"].get("test", "").lower()) for c in ok)
    def matches(c):
        i = c["input"]
        es = p.get("d", p.get("dz"))
        good = abs(float(i.get("effect_size", -1)) - es) < 1e-9
        good &= abs(float(i.get("alpha", 0.05)) - p["alpha"]) < 1e-9
        good &= int(i.get("tails", 2)) == p["tails"]
        if "power" in p:
            good &= abs(float(i.get("power", -1)) - p["power"]) < 1e-9
            good &= abs(float(i.get("allocation_ratio") or 1.0) - p.get("ratio", 1)) < 1e-9
        else:
            if "n1" in p:
                good &= (i.get("n1"), i.get("n2")) == (p["n1"], p["n2"])
            else:
                good &= i.get("n") == p["n"]
        return good
    params_ok = any(matches(c) for c in ok)
    text = run["final_answer"]
    if "power" in p:
        ans_ok = _num_in(text, exp["n_total"])
    else:
        ans_ok = _num_in(text, exp["power"])
    return {"family": fam_ok, "params": params_ok, "answer": ans_ok}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--mcp-bin", default=str(Path(sys.executable).with_name("gpower-mcp")))
    a = ap.parse_args(argv)
    qs = json.loads((EVAL / "questions.json").read_text(encoding="utf-8"))
    if a.only:
        qs = [q for q in qs if q["id"] in set(a.only)]
    (EVAL / "runs").mkdir(parents=True, exist_ok=True)
    for q in qs:
        r = run_one(q, a.mcp_bin, a.model)
        r["score"] = score(q, r)
        (EVAL / "runs" / f"{q['id']}.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(q["id"], r["score"], r["wall_seconds"], "s", r["cost_usd"])
    render()
    return 0


def render() -> None:
    qs = json.loads((EVAL / "questions.json").read_text(encoding="utf-8"))
    runs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (EVAL / "runs").glob("Q*.json")}
    L = ["# Agent evaluation — 10 Turkish clinical questions over MCP", "",
         "Generated by `python tools/agent_eval.py`. Expected values are G\\*Power 3.1.9.6",
         "readings (`E-Qnn` in `probes/observations/`), not engine output. The model's",
         "only tools were the six `gpower` MCP tools; it was told never to compute a",
         "number itself. Full logs: [`runs/`](runs/).", "",
         "| id | expected | tool calls | family | params | answer | tokens in / out | s | $ |",
         "|---|---|---|---|---|---|---|---|---|"]
    tot = {"family": 0, "params": 0, "answer": 0}
    tin = tout = cost = secs = 0
    for q in qs:
        r = runs.get(q["id"])
        if not r:
            L.append(f"| {q['id']} | {q['expected_family']} | — | not run | | | | | |")
            continue
        s = r["score"]
        for k in tot:
            tot[k] += bool(s[k])
        u = r.get("usage") or {}
        i = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
             + u.get("cache_creation_input_tokens", 0))
        o = u.get("output_tokens", 0)
        tin += i; tout += o; cost += r.get("cost_usd") or 0; secs += r["wall_seconds"]
        exp = q["expected"]
        want = (f"N={exp['n_total']}" if exp and "power" in q["expected_parameters"]
                else f"power={exp['power']}" if exp else q["expected_family"])
        calls = ", ".join(c["tool"] for c in r["tool_calls"]) or "none"
        L.append(f"| {q['id']} | {q['expected_family']}: {want} | {calls} | "
                 f"{'✔' if s['family'] else '✘'} | {'✔' if s['params'] else '✘'} | "
                 f"{'✔' if s['answer'] else '✘'} | {i} / {o} | {r['wall_seconds']} | "
                 f"{(r.get('cost_usd') or 0):.3f} |")
    n = len(runs)
    L += ["", "| | result |", "|---|---|",
          f"| questions run | {n} / {len(qs)} |",
          f"| correct test family (incl. refusing unsupported / ambiguous) | **{tot['family']} / {n}** |",
          f"| correct parameters in the tool call | **{tot['params']} / {n}** |",
          f"| correct final number (= G\\*Power) | **{tot['answer']} / {n}** |",
          f"| tokens, total in / out | {tin} / {tout} |",
          f"| mean wall time per question | {secs / max(n, 1):.1f} s |",
          f"| cost, total | ${cost:.2f} |", ""]
    (EVAL / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
