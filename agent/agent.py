"""Natural-language power-analysis agent.

Architecture (invariant I-3 -- see docs/ARCHITECTURE.md):

    user prose  ->  Claude  ->  MCP tools  ->  gpower_rea.engine
                                               ^
                                               |
                 the CLI calls the SAME function

The agent owns **no** statistics.  Its system prompt forbids arithmetic: every
number it reports must come back from a tool call, which is what makes its
answers reproducible against `gpower solve`.

Usage
-----
    export ANTHROPIC_API_KEY=...            # or: ant auth login
    pip install "gpower-rea[mcp,agent]"
    python agent/agent.py                               # interactive
    python agent/agent.py "40 kişilik iki grubum var, d=0.6 ile gücüm ne?"
    python agent/agent.py --json "n for d=0.5, power .95"
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import shlex
import sys
from typing import Any, Sequence

try:
    from anthropic import AsyncAnthropic
    from anthropic.lib.tools.mcp import async_mcp_tool
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "This agent needs the Anthropic SDK with MCP helpers.\n"
        "Install with:  pip install 'gpower-rea[agent]'"
    ) from exc

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "This agent needs the 'mcp' package.\n"
        "Install with:  pip install 'gpower-rea[mcp]'"
    ) from exc

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16_000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
You are a statistical power-analysis consultant for clinical and behavioural
researchers. You have tools that wrap a validated engine for the G*Power 3.1
"t tests" family.

Hard rules:
1. Never compute, estimate, or recall a sample size, power value, critical
   value, or noncentrality parameter yourself. Every number you state must come
   from a tool result in this conversation. If a tool fails, say so and say
   why -- do not substitute a guess.
2. Pick the design from what the user describes, and name it back to them:
     - two independent groups / between-subjects / parallel-arm
       -> ttest-indep-means (effect size d)
     - same participants measured twice / pre-post / matched pairs
       -> ttest-paired-means (effect size dz)
     - one group against a fixed reference value
       -> ttest-one-sample (effect size d)
     - correlation between a binary grouping and a continuous outcome
       -> ttest-point-biserial (effect size r)
     - one predictor's coefficient inside a multiple regression
       -> ttest-regression-coef (effect size f2, plus `predictors`)
3. If the user gives raw descriptives (means, SDs, a pre-post correlation, an
   R-squared) instead of a standardised effect size, call compute_effect_size
   first and show the intermediate value.
4. State the assumptions you had to make, and use these defaults when the user
   is silent: alpha = 0.05, power = 0.80, tails = 2, allocation ratio = 1.
   Say plainly which values you defaulted.
5. Ask a clarifying question only when the answer would materially change the
   design (for example one- vs two-tailed on a directional hypothesis, or
   paired vs independent). Otherwise proceed under stated assumptions.
6. Answer in the user's language. Lead with the number they asked for, then
   the assumptions, then one sentence they can paste into a methods section
   (the tools return one as `apa_sentence`).
7. For a required sample size, always report the per-group sizes and the total,
   plus the achieved power at that size -- it slightly exceeds the target
   because sample sizes are integers.
8. If asked how trustworthy the numbers are, call engine_provenance and answer
   from it. Do not claim to be G*Power; you are an independent engine built to
   a documented specification.
"""


def _server_command(explicit: str | None) -> StdioServerParameters:
    """Resolve how to launch the MCP server."""
    if explicit:
        parts = shlex.split(explicit)
        return StdioServerParameters(command=parts[0], args=parts[1:])
    # Prefer the current interpreter so a venv install is always found.
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "gpower_rea.mcp_server"],
        env=dict(os.environ),
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _text_of(message: Any) -> str:
    chunks = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text" and getattr(block, "text", ""):
            chunks.append(block.text)
    return "\n".join(chunks).strip()


def _tool_calls_of(message: Any) -> list[tuple[str, dict]]:
    out = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "tool_use":
            out.append((block.name, dict(block.input or {})))
    return out


def _is_fallback_rejection(exc: Exception) -> bool:
    """True when the failure is the account/SDK declining the fallbacks beta."""
    text = f"{type(exc).__name__}: {exc}".lower()
    return isinstance(exc, TypeError) or (
        "fallback" in text or "server-side-fallback" in text
    )


class PowerAgent:
    """One conversation with the model, with the MCP session held open.

    ``client`` is injectable so that the loop can be exercised without an API
    key -- see tests/test_agent_offline.py, which drives it with a stub and
    checks history mirroring, the tool transcript, refusal handling and the
    fallback-degradation path.
    """

    def __init__(
        self,
        session: ClientSession,
        tools: Sequence[Any],
        *,
        verbose: bool,
        client: Any | None = None,
    ):
        self.client = client if client is not None else AsyncAnthropic()
        self.session = session
        self.tools = list(tools)
        self.verbose = verbose
        self.messages: list[dict] = []
        self.transcript: list[dict] = []
        # Server-side refusal fallbacks are recommended for Opus 5.5, but the
        # beta may not be enabled on every account -- so request them, and
        # drop them permanently the first time they are refused.
        self._use_fallbacks = True

    def _runner(self, *, use_fallbacks: bool):
        params: dict[str, Any] = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=self.tools,
            messages=self.messages,
        )
        if use_fallbacks:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return self.client.beta.messages.tool_runner(**params)

    async def _drive(self, *, use_fallbacks: bool) -> str:
        runner = self._runner(use_fallbacks=use_fallbacks)
        final = ""
        async for message in runner:
            if getattr(message, "stop_reason", None) == "refusal":
                details = getattr(message, "stop_details", None)
                category = getattr(details, "category", None) or "unknown"
                return (
                    "The request was declined by the model's safety classifiers "
                    f"(category: {category}). Rephrase the statistical question "
                    "and try again."
                )
            for name, args in _tool_calls_of(message):
                self.transcript.append({"tool": name, "input": args})
                if self.verbose:
                    print(
                        f"  · {name}({json.dumps(args, ensure_ascii=False)})",
                        file=sys.stderr,
                    )
            text = _text_of(message)
            if text:
                final = text
            # Mirror the runner's history so the next turn keeps full context.
            self.messages.append({"role": "assistant", "content": message.content})
            tool_response = await _maybe_await(runner.generate_tool_call_response())
            if tool_response is not None:
                self.messages.append(tool_response)
        return final

    async def ask(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        snapshot = len(self.messages)
        try:
            return await self._drive(use_fallbacks=self._use_fallbacks)
        except Exception as exc:  # noqa: BLE001 - narrowed immediately below
            if self._use_fallbacks and _is_fallback_rejection(exc):
                if self.verbose:
                    print(
                        f"[agent] refusal fallbacks unavailable ({exc}); "
                        "retrying without them",
                        file=sys.stderr,
                    )
                self._use_fallbacks = False
                del self.messages[snapshot:]  # discard the partial turn
                return await self._drive(use_fallbacks=False)
            raise


async def _run(args: argparse.Namespace) -> int:
    server = _server_command(args.server)
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = [async_mcp_tool(t, session) for t in listed.tools]
            if args.verbose:
                names = ", ".join(t.name for t in listed.tools)
                print(f"[mcp] {len(tools)} tool(s): {names}", file=sys.stderr)

            agent = PowerAgent(session, tools, verbose=args.verbose)

            if args.prompt:
                answer = await agent.ask(" ".join(args.prompt))
                if args.json:
                    print(
                        json.dumps(
                            {
                                "prompt": " ".join(args.prompt),
                                "answer": answer,
                                "tool_calls": agent.transcript,
                            },
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                else:
                    print(answer)
                return 0

            print("gpower agent -- ask a power-analysis question (Ctrl-D to quit).")
            print("Engine tools are called for every number; nothing is guessed.\n")
            while True:
                try:
                    line = input("you> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return 0
                if not line:
                    continue
                if line.lower() in ("exit", "quit", ":q"):
                    return 0
                answer = await agent.ask(line)
                print(f"\n{answer}\n")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="gpower-agent",
        description="Natural-language power analysis over the gpower-rea MCP server.",
    )
    ap.add_argument("prompt", nargs="*", help="one-shot question; omit for a REPL")
    ap.add_argument(
        "--server",
        default=None,
        help="command used to launch the MCP server "
        "(default: this interpreter running gpower_rea.mcp_server)",
    )
    ap.add_argument("--json", action="store_true", help="emit answer + tool trace as JSON")
    ap.add_argument("-v", "--verbose", action="store_true", help="log tool calls to stderr")
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
