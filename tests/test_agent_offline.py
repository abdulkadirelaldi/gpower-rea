"""The agent's loop, tested without an API key.

What can be tested offline is everything except the model itself: tool-call
extraction, conversation-history mirroring between turns, the refusal
short-circuit, and the degradation path when the server-side refusal-fallback
beta is unavailable.  The model's *judgement* is governed by the system
prompt, which no unit test can check -- but the plumbing around it can, and
plumbing is where silent breakage lives.

What this file deliberately does NOT claim: that the agent has been run
against the live API.  docs/SESSION-LOG.md records that as unverified.

Skipped automatically when the `agent` extra is not installed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("anthropic", reason="the 'agent' extra is not installed")
pytest.importorskip("mcp", reason="the 'mcp' extra is not installed")

ROOT = Path(__file__).resolve().parents[1]
AGENT_PY = ROOT / "agent" / "agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("gpower_agent_under_test", AGENT_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ag = _load_agent_module()


# --------------------------------------------------------------------------
# stubs
# --------------------------------------------------------------------------
def _text(s: str):
    return SimpleNamespace(type="text", text=s)


def _tool_use(name: str, **kwargs):
    return SimpleNamespace(type="tool_use", name=name, input=kwargs, id="toolu_1")


def _thinking():
    return SimpleNamespace(type="thinking", thinking="")


def _msg(content, stop_reason="end_turn", stop_details=None):
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, stop_details=stop_details
    )


class _StubRunner:
    """Yields a canned sequence of messages, like the real BetaAsyncToolRunner."""

    def __init__(self, messages, tool_responses=None):
        self._messages = list(messages)
        self._tool_responses = list(tool_responses or [])

    def __aiter__(self):
        async def gen():
            for m in self._messages:
                yield m

        return gen()

    async def generate_tool_call_response(self):
        if self._tool_responses:
            return self._tool_responses.pop(0)
        return None


class _StubClient:
    """Minimal stand-in for AsyncAnthropic.

    ``fail_on_fallbacks`` reproduces an account without the beta enabled: the
    first call that passes ``fallbacks`` raises, as the API would.
    """

    def __init__(self, runners, *, fail_on_fallbacks=False):
        self._runners = list(runners)
        self.fail_on_fallbacks = fail_on_fallbacks
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(tool_runner=self._runner))

    def _runner(self, **params):
        self.calls.append(params)
        if self.fail_on_fallbacks and "fallbacks" in params:
            raise RuntimeError(
                "fallbacks: beta server-side-fallback-2026-07-01 is not enabled "
                "for this organization"
            )
        return self._runners.pop(0)


def _agent(runners, *, fail_on_fallbacks=False, verbose=False):
    client = _StubClient(runners, fail_on_fallbacks=fail_on_fallbacks)
    agent = ag.PowerAgent(session=None, tools=[], verbose=verbose, client=client)
    return agent, client


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------
def test_text_extraction_skips_non_text_blocks():
    msg = _msg([_thinking(), _text("first"), _tool_use("x"), _text("second")])
    assert ag._text_of(msg) == "first\nsecond"


def test_text_extraction_on_an_empty_message():
    assert ag._text_of(_msg([])) == ""


def test_tool_call_extraction():
    msg = _msg(
        [
            _text("calling"),
            _tool_use("power_analysis", test="ttest-indep-means", solve_for="n"),
            _tool_use("engine_provenance"),
        ]
    )
    assert ag._tool_calls_of(msg) == [
        ("power_analysis", {"test": "ttest-indep-means", "solve_for": "n"}),
        ("engine_provenance", {}),
    ]


def test_server_command_defaults_to_this_interpreter():
    params = ag._server_command(None)
    assert params.command == sys.executable
    assert params.args == ["-m", "gpower_rea.mcp_server"]


def test_server_command_respects_an_override():
    params = ag._server_command("gpower-mcp --flag value")
    assert params.command == "gpower-mcp"
    assert params.args == ["--flag", "value"]


@pytest.mark.parametrize(
    "exc,expected",
    [
        (TypeError("unexpected keyword argument 'fallbacks'"), True),
        (RuntimeError("beta server-side-fallback-2026-07-01 not enabled"), True),
        (RuntimeError("fallbacks must be a list"), True),
        (RuntimeError("rate limit exceeded"), False),
        (ValueError("connection reset"), False),
    ],
)
def test_fallback_rejection_detection(exc, expected):
    assert ag._is_fallback_rejection(exc) is expected


# --------------------------------------------------------------------------
# the loop
# --------------------------------------------------------------------------
def test_single_turn_returns_the_final_text():
    runner = _StubRunner([_msg([_text("You need 210 participants.")])])
    agent, client = _agent([runner])
    answer = asyncio.run(agent.ask("how many?"))
    assert answer == "You need 210 participants."
    assert len(client.calls) == 1


def test_tool_calls_are_recorded_in_the_transcript():
    runner = _StubRunner(
        [
            _msg([_tool_use("power_analysis", test="indep", solve_for="n")]),
            _msg([_text("210 total.")]),
        ],
        tool_responses=[{"role": "user", "content": [{"type": "tool_result"}]}],
    )
    agent, _ = _agent([runner])
    answer = asyncio.run(agent.ask("how many?"))
    assert answer == "210 total."
    assert agent.transcript == [
        {"tool": "power_analysis", "input": {"test": "indep", "solve_for": "n"}}
    ]


def test_history_is_mirrored_so_a_follow_up_keeps_context():
    first = _StubRunner(
        [
            _msg([_tool_use("power_analysis", test="indep")]),
            _msg([_text("210 total.")]),
        ],
        tool_responses=[{"role": "user", "content": "tool result"}],
    )
    second = _StubRunner([_msg([_text("With 90% power, 172.")])])
    agent, client = _agent([first, second])

    asyncio.run(agent.ask("how many at 95%?"))
    asyncio.run(agent.ask("and at 90%?"))

    roles = [m["role"] for m in agent.messages]
    # user, assistant(tool_use), user(tool_result), assistant(text),
    # user(follow-up), assistant(text)
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]
    assert agent.messages[0]["content"] == "how many at 95%?"
    assert agent.messages[4]["content"] == "and at 90%?"
    # The second request carried the whole history.
    assert client.calls[1]["messages"] is agent.messages


def test_a_refusal_is_reported_not_crashed_on():
    runner = _StubRunner(
        [
            _msg(
                [],
                stop_reason="refusal",
                stop_details=SimpleNamespace(category="cyber"),
            )
        ]
    )
    agent, _ = _agent([runner])
    answer = asyncio.run(agent.ask("something declined"))
    assert "declined" in answer.lower()
    assert "cyber" in answer


def test_a_refusal_without_details_still_reports():
    runner = _StubRunner([_msg([], stop_reason="refusal", stop_details=None)])
    agent, _ = _agent([runner])
    answer = asyncio.run(agent.ask("x"))
    assert "unknown" in answer


# --------------------------------------------------------------------------
# refusal-fallback degradation
# --------------------------------------------------------------------------
def test_fallbacks_are_requested_by_default():
    runner = _StubRunner([_msg([_text("ok")])])
    agent, client = _agent([runner])
    asyncio.run(agent.ask("hi"))
    assert client.calls[0]["fallbacks"] == "default"
    assert client.calls[0]["betas"] == [ag.FALLBACK_BETA]


def test_model_and_thinking_configuration():
    runner = _StubRunner([_msg([_text("ok")])])
    agent, client = _agent([runner])
    asyncio.run(agent.ask("hi"))
    params = client.calls[0]
    assert params["model"] == "claude-opus-5-5"
    assert params["thinking"] == {"type": "adaptive"}
    assert params["output_config"] == {"effort": "high"}
    assert "statistical power-analysis consultant" in params["system"]


def test_an_unavailable_fallback_beta_degrades_and_retries_cleanly():
    """The retry must not leave the first, failed turn in the history."""
    runner = _StubRunner([_msg([_text("ok without fallbacks")])])
    agent, client = _agent([runner], fail_on_fallbacks=True)
    answer = asyncio.run(agent.ask("hi"))

    assert answer == "ok without fallbacks"
    assert len(client.calls) == 2
    assert "fallbacks" in client.calls[0]
    assert "fallbacks" not in client.calls[1]
    # one user turn + one assistant turn, with no duplicate of either
    assert [m["role"] for m in agent.messages] == ["user", "assistant"]
    assert agent._use_fallbacks is False


def test_degradation_is_remembered_for_later_turns():
    first = _StubRunner([_msg([_text("a")])])
    second = _StubRunner([_msg([_text("b")])])
    agent, client = _agent([first, second], fail_on_fallbacks=True)
    asyncio.run(agent.ask("one"))
    asyncio.run(agent.ask("two"))
    # 1st attempt (with) + 1st retry (without) + 2nd turn (without) = 3
    assert len(client.calls) == 3
    assert "fallbacks" not in client.calls[2]


def test_an_unrelated_error_is_not_swallowed():
    class _Boom(_StubClient):
        def _runner(self, **params):
            self.calls.append(params)
            raise RuntimeError("rate limit exceeded")

    client = _Boom([])
    agent = ag.PowerAgent(session=None, tools=[], verbose=False, client=client)
    with pytest.raises(RuntimeError, match="rate limit"):
        asyncio.run(agent.ask("hi"))


# --------------------------------------------------------------------------
# the no-arithmetic rule
# --------------------------------------------------------------------------
def test_the_system_prompt_forbids_the_agent_doing_arithmetic():
    prompt = ag.SYSTEM_PROMPT
    assert "Never compute, estimate, or recall" in prompt
    assert "must come" in prompt and "from a tool result" in prompt
    # and it must not claim to be G*Power
    assert "Do not claim to be G*Power" in prompt
    # the documented defaults must be stated, so the agent can declare them
    for token in ("alpha = 0.05", "power = 0.80", "tails = 2", "allocation ratio = 1"):
        assert token in prompt, f"prompt no longer states the default {token!r}"


def test_the_agent_source_contains_no_arithmetic():
    """Duplicates tools/compliance_check.py rule C-3, kept here so the
    property fails as a test and not only as a CI script."""
    import re

    text = AGENT_PY.read_text(encoding="utf-8")
    assert not re.search(r"\bmath\.", text)
    assert "nct_cdf(" not in text
    assert "sqrt(" not in text
