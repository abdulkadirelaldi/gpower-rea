"""The MCP layer must be a pass-through, not a second implementation."""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp", reason="the 'mcp' extra is not installed")

from gpower_rea import solve  # noqa: E402
from gpower_rea.mcp_server import mcp  # noqa: E402


def _call(name: str, arguments: dict) -> dict:
    """Invoke a tool through the real MCP dispatcher and parse its payload.

    The SDK's return shape differs across versions: mcp 2.x returns a
    ``CallToolResult``, newer 1.x returns ``(content_blocks, structured)`` and
    older 1.x a bare list of content blocks.  Handle all three so the test
    pins the behaviour, not the SDK release.
    """
    result = asyncio.run(mcp.call_tool(name, arguments))

    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is None and isinstance(result, tuple) and len(result) > 1:
        structured = result[1]
    if isinstance(structured, dict):
        return structured.get("result", structured)

    blocks = getattr(result, "content", None)
    if blocks is None:
        blocks = result[0] if isinstance(result, tuple) else result
    for block in blocks or ():
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError(f"no parsable payload from {name}: {result!r}")


def test_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "list_tests",
        "describe_test",
        "power_analysis",
        "compute_effect_size",
        "power_curve",
        "engine_provenance",
    }
    for t in tools:
        assert t.description, f"{t.name} has no description"
        # mcp 1.x spells it inputSchema, mcp 2.x input_schema.
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)
        assert schema is not None, f"{t.name} has no input schema"


def test_list_tests_matches_the_engine():
    payload = _call("list_tests", {})
    from gpower_rea.procedures import PROCEDURES

    keys = {t["key"] for t in payload["tests"]}
    assert keys == set(PROCEDURES)


def test_power_analysis_delegates_to_the_engine():
    payload = _call(
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
    ref = solve(
        "ttest-indep-means", "n",
        alpha=0.05, power_target=0.95, effect_size=0.5, tails=2,
    ).as_dict()
    assert payload["result"] == ref
    assert "apa_sentence" in payload and "report_text" in payload


def test_power_analysis_accepts_underscored_solve_for():
    payload = _call(
        "power_analysis",
        {
            "test": "ttest-one-sample",
            "solve_for": "effect_size",
            "alpha": 0.05,
            "power": 0.8,
            "n": 50,
        },
    )
    assert payload["result"]["solve_for"] == "effect-size"


def test_errors_come_back_as_data_not_exceptions():
    payload = _call("power_analysis", {"test": "manova", "solve_for": "n"})
    assert payload["ok"] is False
    assert payload["error"]["type"] == "ValidationError"
    assert "unknown test" in payload["error"]["message"]


def test_effect_size_tool():
    payload = _call(
        "compute_effect_size",
        {
            "calculator": "d-two-independent-means",
            "parameters": {"mean1": 10, "mean2": 8, "sd1": 4, "sd2": 4},
        },
    )
    assert payload["effect_size"]["value"] == pytest.approx(0.5)


def test_effect_size_unknown_calculator():
    payload = _call(
        "compute_effect_size", {"calculator": "nope", "parameters": {}}
    )
    assert payload["ok"] is False


def test_power_curve_tool():
    payload = _call(
        "power_curve",
        {
            "test": "ttest-one-sample",
            "alpha": 0.05,
            "effect_size": 0.5,
            "n_from": 20,
            "n_to": 24,
            "n_step": 2,
        },
    )
    assert [p["total"] for p in payload["points"]] == [20, 22, 24]


def test_provenance_declares_compliance():
    payload = _call("engine_provenance", {})
    assert payload["engine"]["contains_decompiler_output"] is False
    assert payload["engine"]["bundles_original_binary"] is False
    assert payload["default_allocation_rule"] == "n1-grid"
