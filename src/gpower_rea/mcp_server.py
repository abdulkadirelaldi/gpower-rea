"""MCP server exposing the gpower-rea engine over stdio.

Run directly::

    gpower-mcp
    python -m gpower_rea.mcp_server

Register with an MCP client (Claude Desktop / Claude Code `.mcp.json`)::

    {
      "mcpServers": {
        "gpower": { "command": "gpower-mcp", "args": [] }
      }
    }

The server is a *thin* adapter: every tool below forwards to
:mod:`gpower_rea.engine` and returns its JSON verbatim (invariant I-3).  It
performs no arithmetic of its own.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

# The Python MCP SDK renamed FastMCP to MCPServer in 2.0; the decorator and
# runtime surface we use (`.tool()`, `.run()`, `.list_tools()`, `.call_tool()`)
# is the same, so support both rather than pinning users to one major version.
try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server

    MCP_FLAVOUR = "mcp>=2 (MCPServer)"
except ModuleNotFoundError:  # pragma: no cover - exercised by whichever is installed
    try:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as _Server

        MCP_FLAVOUR = "mcp 1.x (FastMCP)"
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "The MCP server needs the 'mcp' package. "
            "Install it with:  pip install 'gpower-rea[mcp]'",
            name="mcp",
        ) from exc

from . import effectsize as esmod
from . import engine as eng
from .procedures import PROCEDURES, ValidationError, resolve
from .report import apa_sentence, text_block

SERVER_INSTRUCTIONS = """\
Statistical power analysis for the G*Power 3.1 "t tests" family, backed by a
clean-room engine (see SPEC.md in the gpower-rea repository).

Workflow for a natural-language request:
  1. `list_tests` if you are unsure which design the user is describing.
  2. If the user gives raw means / SDs / correlations rather than a
     standardised effect size, call `compute_effect_size` first.
  3. Call `power_analysis` with solve_for = "n" (how many participants?),
     "power" (how much power do I have?), "alpha", "effect_size"
     (what can I detect?) or "compromise".
  4. Quote `report_text` or `apa_sentence` back to the user; they are already
     formatted for a methods section.

Conventions: alpha and power are probabilities in (0,1); `tails` is 1 or 2
(default 2); `allocation_ratio` is N2/N1 and only applies to the two-group
test. Effect-size metric per test: d (independent / one sample), dz (matched
pairs), r (point biserial), f2 (regression coefficient), delta (generic).
"""

mcp = _Server("gpower-rea", instructions=SERVER_INSTRUCTIONS)

SolveFor = Literal["n", "power", "alpha", "effect_size", "effect-size", "compromise"]


def _err(exc: Exception) -> dict:
    return {
        "ok": False,
        "error": {"type": type(exc).__name__, "message": str(exc)},
        "hint": "Call list_tests / describe_test to see the required parameters.",
    }


@mcp.tool()
def list_tests() -> dict:
    """List every statistical test this engine implements, with its effect-size
    metric, design (one- or two-group) and supported analysis types."""
    return {
        "ok": True,
        "family": "t tests",
        "engine": {"version": eng.ENGINE_VERSION, "spec": eng.SPEC_VERSION},
        "tests": [p.describe() for p in PROCEDURES.values()],
    }


@mcp.tool()
def describe_test(test: str) -> dict:
    """Describe one test: its exact G*Power menu title, effect-size metric,
    extra parameters, and which analysis types it supports."""
    try:
        return {"ok": True, **resolve(test).describe()}
    except ValidationError as exc:
        return _err(exc)


@mcp.tool()
def power_analysis(
    test: str,
    solve_for: SolveFor = "n",
    alpha: Optional[float] = None,
    power: Optional[float] = None,
    effect_size: Optional[float] = None,
    tails: int = 2,
    n: Optional[int] = None,
    n1: Optional[int] = None,
    n2: Optional[int] = None,
    allocation_ratio: Optional[float] = None,
    allocation_rule: Optional[str] = None,
    beta_alpha_ratio: Optional[float] = None,
    predictors: Optional[int] = None,
    df: Optional[float] = None,
) -> dict:
    """Run one power analysis and return the full numeric result plus
    ready-to-paste prose.

    solve_for:
      "n"            -> smallest sample size reaching `power` (a priori)
      "power"        -> achieved power of an explicit design (post hoc)
      "alpha"        -> alpha needed to reach `power` (criterion)
      "effect_size"  -> smallest detectable effect (sensitivity)
      "compromise"   -> alpha and power implied by `beta_alpha_ratio`

    Supply `n1`+`n2` or `n`(+`allocation_ratio`) for the two-group test and `n`
    otherwise.  `predictors` applies to ttest-regression-coef; `df` to
    ttest-generic.
    """
    extra: dict[str, Any] = {}
    if predictors is not None:
        extra["predictors"] = predictors
    if df is not None:
        extra["df"] = df
    try:
        result = eng.solve(
            test,
            str(solve_for).replace("_", "-"),
            alpha=alpha,
            power_target=power,
            effect_size=effect_size,
            tails=tails,
            n=n,
            n1=n1,
            n2=n2,
            allocation_ratio=allocation_ratio,
            allocation_rule=allocation_rule,
            beta_alpha_ratio=beta_alpha_ratio,
            extra=extra,
        )
    except (ValidationError, eng.NoSolutionError, ValueError, TypeError) as exc:
        return _err(exc)
    return {
        "ok": True,
        "result": result.as_dict(),
        "report_text": text_block(result),
        "apa_sentence": apa_sentence(result),
    }


@mcp.tool()
def compute_effect_size(calculator: str, parameters: dict) -> dict:
    """Convert raw descriptive statistics into the standardised effect size a
    test needs.

    Calculators:
      d-two-independent-means     mean1, mean2, sd1, sd2 [, equal_n, n1, n2]
      dz-matched-pairs            mean1, mean2, sd1, sd2, correlation
      dz-from-difference          mean_difference, sd_difference
      d-one-sample                mean, reference, sd
      f2-from-r-squared           r_squared
      f2-from-partial-r-squared   partial_r_squared
      r-from-d-balanced           d
    """
    fn = esmod.CALCULATORS.get(calculator)
    if fn is None:
        return _err(
            ValidationError(
                f"unknown calculator {calculator!r}; choose from "
                f"{sorted(esmod.CALCULATORS)}"
            )
        )
    try:
        return {"ok": True, **fn(**dict(parameters or {}))}
    except (ValidationError, TypeError, ValueError) as exc:
        return _err(exc)


@mcp.tool()
def power_curve(
    test: str,
    alpha: float,
    effect_size: float,
    n_from: int,
    n_to: int,
    n_step: int = 1,
    tails: int = 2,
    allocation_ratio: Optional[float] = None,
    predictors: Optional[int] = None,
) -> dict:
    """Tabulate power against sample size -- useful for showing a user the
    trade-off instead of a single number. Capped at 500 rows."""
    extra: dict[str, Any] = {}
    if predictors is not None:
        extra["predictors"] = predictors
    try:
        points = eng.power_curve(
            test,
            alpha=alpha,
            effect_size=effect_size,
            tails=tails,
            n_from=n_from,
            n_to=n_to,
            n_step=n_step,
            allocation_ratio=allocation_ratio,
            extra=extra,
        )
    except (ValidationError, eng.NoSolutionError, ValueError) as exc:
        return _err(exc)
    return {"ok": True, "test": resolve(test).key, "points": points}


@mcp.tool()
def engine_provenance() -> dict:
    """Report engine version, the specification it implements, and the
    documented behavioural findings it encodes. Use this when a user asks how
    trustworthy the numbers are or where they come from."""
    return {
        "ok": True,
        "engine": {
            "name": "gpower-rea",
            "version": eng.ENGINE_VERSION,
            "spec": eng.SPEC_VERSION,
            "mcp_sdk": MCP_FLAVOUR,
            "contains_decompiler_output": False,
            "bundles_original_binary": False,
        },
        "method": (
            "Behavioural (black-box) reverse engineering of G*Power 3.1.9.7 "
            "plus differential testing. Findings are catalogued in SPEC.md and "
            "docs/EVIDENCE/; the implementation was written in a separate "
            "session from SPEC.md alone (docs/CLEANROOM-PROTOCOL.md)."
        ),
        "allocation_rules": sorted(eng.ALLOCATION_RULES),
        "default_allocation_rule": eng.DEFAULT_ALLOCATION_RULE,
        "tests": sorted(PROCEDURES),
    }


def main() -> None:
    """Console-script entry point: serve over stdio."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
