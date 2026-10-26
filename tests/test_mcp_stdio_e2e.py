"""End-to-end check of the transport the agent actually uses.

`tests/test_mcp_server.py` calls the tools through the in-process dispatcher.
This file spawns `python -m gpower_rea.mcp_server` as a real subprocess, speaks
MCP over stdio, and compares the result with the engine -- so a packaging or
entry-point regression cannot pass CI while the in-process tests stay green.

Skipped automatically when the `mcp` extra is not installed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

pytest.importorskip("mcp", reason="the 'mcp' extra is not installed")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from gpower_rea import solve  # noqa: E402

EXPECTED_TOOLS = {
    "compute_effect_size",
    "describe_test",
    "engine_provenance",
    "list_tests",
    "power_analysis",
    "power_curve",
}


def _payload(result) -> dict:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured.get("result", structured)
    for block in getattr(result, "content", None) or ():
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError(f"no parsable payload: {result!r}")


async def _session_roundtrip() -> dict:
    env = dict(os.environ)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "gpower_rea.mcp_server"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {t.name for t in listed.tools}

            canonical = await session.call_tool(
                "power_analysis",
                {
                    "test": "ttest-indep-means",
                    "solve_for": "n",
                    "alpha": 0.05,
                    "power": 0.95,
                    "effect_size": 0.5,
                    "tails": 2,
                },
            )
            provenance = await session.call_tool("engine_provenance", {})
            bad = await session.call_tool(
                "power_analysis", {"test": "manova", "solve_for": "n"}
            )
            return {
                "names": names,
                "canonical": _payload(canonical),
                "provenance": _payload(provenance),
                "bad": _payload(bad),
            }


@pytest.fixture(scope="module")
def roundtrip():
    return asyncio.run(_session_roundtrip())


def test_server_starts_as_a_subprocess_and_advertises_its_tools(roundtrip):
    assert roundtrip["names"] == EXPECTED_TOOLS


def test_tool_result_over_stdio_equals_the_engine(roundtrip):
    payload = roundtrip["canonical"]
    assert payload["ok"] is True
    ref = solve(
        "ttest-indep-means", "n",
        alpha=0.05, power_target=0.95, effect_size=0.5, tails=2,
    ).as_dict()
    assert payload["result"] == ref
    assert payload["result"]["sample_size"]["total"] == 210
    assert "apa_sentence" in payload and "report_text" in payload


def test_provenance_over_stdio(roundtrip):
    engine = roundtrip["provenance"]["engine"]
    assert engine["contains_decompiler_output"] is False
    assert engine["bundles_original_binary"] is False
    assert engine["name"] == "gpower-rea"


def test_errors_cross_the_wire_as_data(roundtrip):
    bad = roundtrip["bad"]
    assert bad["ok"] is False
    assert "unknown test" in bad["error"]["message"]
