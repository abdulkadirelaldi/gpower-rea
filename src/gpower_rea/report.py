"""Human-readable renderings of a :class:`~gpower_rea.engine.Result`.

Two formats:

* ``text_block``  -- a protocol-style block mirroring the layout of the
  "Output Parameters" panel in the G*Power GUI, so a researcher can compare
  the two side by side.
* ``apa_sentence`` -- one sentence that can be pasted into a methods section.
"""

from __future__ import annotations

from .engine import Result

__all__ = ["text_block", "apa_sentence"]

_ANALYSIS_LABEL = {
    "n": "A priori: Compute required sample size",
    "power": "Post hoc: Compute achieved power",
    "alpha": "Criterion: Compute required alpha",
    "effect-size": "Sensitivity: Compute required effect size",
    "compromise": "Compromise: Compute implied alpha & power",
}


def _fmt(value, digits: int = 7) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def text_block(result: Result) -> str:
    r = result.as_dict()
    es = r["effect_size"]
    ss = r["sample_size"]
    lines: list[str] = []
    lines.append("t tests - " + r["test_title"])
    lines.append("")
    lines.append("Analysis:          " + _ANALYSIS_LABEL.get(r["solve_for"], r["solve_for"]))
    lines.append("Input Parameters")
    lines.append(f"  Tail(s)                        = {r['tails']}")
    lines.append(
        f"  Effect size {es['name']:<18} = {_fmt(es['value'])}"
    )
    for key, val in (es.get("parameters") or {}).items():
        lines.append(f"  {key:<30} = {_fmt(val)}")
    if r["solve_for"] != "alpha":
        lines.append(f"  alpha err prob                 = {_fmt(r['alpha'])}")
    if r["target"].get("power") is not None:
        lines.append(f"  Power (1-beta err prob)        = {_fmt(r['target']['power'])}")
    if r["target"].get("beta_alpha_ratio") is not None:
        lines.append(
            f"  beta/alpha ratio               = {_fmt(r['target']['beta_alpha_ratio'])}"
        )
    if "allocation_ratio" in ss and ss["allocation_ratio"] is not None:
        lines.append(f"  Allocation ratio N2/N1         = {_fmt(ss['allocation_ratio'])}")
    lines.append("Output Parameters")
    lines.append(f"  Noncentrality parameter delta  = {_fmt(r['noncentrality'])}")
    lines.append(f"  Critical t                     = {_fmt(r['critical_t'])}")
    lines.append(f"  Df                             = {_fmt(r['df'])}")
    if "n1" in ss:
        lines.append(f"  Sample size group 1            = {ss['n1']}")
        lines.append(f"  Sample size group 2            = {ss['n2']}")
    lines.append(f"  Total sample size              = {ss['total']}")
    if r["solve_for"] == "alpha":
        lines.append(f"  alpha err prob                 = {_fmt(r['alpha'])}")
    if r["target"].get("beta") is not None:
        lines.append(f"  beta err prob                  = {_fmt(r['target']['beta'])}")
    label = "Power (1-beta err prob)" if r["solve_for"] != "n" else "Actual power"
    lines.append(f"  {label:<30} = {_fmt(r['power'])}")
    if r["warnings"]:
        lines.append("Warnings")
        for w in r["warnings"]:
            lines.append(f"  ! {w}")
    lines.append("")
    lines.append(
        f"[engine {r['engine']['name']} {r['engine']['version']}, {r['engine']['spec']}"
        + (
            f", allocation rule '{r['engine']['allocation_rule']}'"
            if "allocation_rule" in r["engine"]
            else ""
        )
        + "]"
    )
    return "\n".join(lines)


def apa_sentence(result: Result) -> str:
    r = result.as_dict()
    es = r["effect_size"]
    ss = r["sample_size"]
    tails = "two-tailed" if r["tails"] == 2 else "one-tailed"
    if "n1" in ss:
        size = (
            f"n1 = {ss['n1']} and n2 = {ss['n2']} "
            f"(total N = {ss['total']})"
        )
    else:
        size = f"N = {ss['total']}"

    if r["solve_for"] == "n":
        return (
            f"An a priori power analysis for a {tails} {r['test_title'].lower()} "
            f"({es['name']} = {es['value']:.4g}, alpha = {r['alpha']:g}, "
            f"target power = {r['target'].get('power'):g}) indicated that "
            f"{size} is required; the achieved power at that sample size is "
            f"{r['power']:.4f}."
        )
    if r["solve_for"] == "power":
        return (
            f"A post hoc power analysis for a {tails} {r['test_title'].lower()} "
            f"with {size}, {es['name']} = {es['value']:.4g} and "
            f"alpha = {r['alpha']:g} yielded a power of {r['power']:.4f}."
        )
    if r["solve_for"] == "alpha":
        return (
            f"To reach a power of {r['target'].get('power'):g} with {size} and "
            f"{es['name']} = {es['value']:.4g} in a {tails} "
            f"{r['test_title'].lower()}, the significance criterion must be "
            f"relaxed to alpha = {r['alpha']:.6g}."
        )
    if r["solve_for"] == "effect-size":
        return (
            f"With {size}, alpha = {r['alpha']:g} and a target power of "
            f"{r['target'].get('power'):g}, the smallest effect detectable by a "
            f"{tails} {r['test_title'].lower()} is "
            f"{es['name']} = {es['value']:.4g}."
        )
    return (
        f"A compromise power analysis for a {tails} {r['test_title'].lower()} "
        f"with {size}, {es['name']} = {es['value']:.4g} and a beta/alpha ratio "
        f"of {r['target'].get('beta_alpha_ratio'):g} implies "
        f"alpha = {r['alpha']:.6g} and power = {r['power']:.4f}."
    )
